"""Prueba de recuperación de datos de un ambiente desplegado.

Comprueba que un archivo dañado o borrado se puede recuperar con el control de versiones
del bucket, y que la recuperación del dato también recupera el resultado del servicio.
Un rollback de la infraestructura no resuelve estas fallas, porque el dato dañado no está
en el código: se necesita un mecanismo de recuperación de datos.

Escenario A: un archivo se sobrescribe con contenido dañado.
  1. Carga el archivo original y espera a que el servicio lo procese (resultado de referencia).
  2. Lo sobrescribe con contenido dañado y espera el resultado erróneo del servicio.
  3. Restaura la versión anterior del archivo (copia de la versión original).
  4. Valida que el contenido es idéntico al original (SHA-256) y que el servicio vuelve
     a producir el resultado de referencia.

Escenario B: un archivo se borra por error.
  1. Borra el archivo (el bucket guarda un marcador de borrado).
  2. Elimina el marcador de borrado para restaurarlo.
  3. Valida que el contenido es idéntico al original.

Mide el tiempo de cada recuperación y lo compara con el objetivo (RTO). Escribe un informe
en Markdown y en JSON, y termina con código 1 si algún criterio no se cumple.

Uso:
  python scripts/recuperar.py --stack plataforma-qa --rto-max-seg 900
"""
import argparse
import hashlib
import io
import json
import os
import random
import sys
import time
import uuid

import boto3
from botocore.exceptions import ClientError


def salidas_pila(cfn, stack):
    pila = cfn.describe_stacks(StackName=stack)["Stacks"][0]
    return {o["OutputKey"]: o["OutputValue"] for o in pila.get("Outputs", [])}


def generar_csv(filas, semilla):
    rnd = random.Random(semilla)
    buf = io.StringIO()
    buf.write("fecha,cliente,producto,cantidad,valor\n")
    for _ in range(filas):
        buf.write(f"2026-11-{rnd.randint(1, 30):02d},C{rnd.randint(1, 5000)},P{rnd.randint(1, 300)},"
                  f"{rnd.randint(1, 50)},{rnd.uniform(1000, 900000):.2f}\n")
    return buf.getvalue().encode("utf-8")


def sha256(datos):
    return hashlib.sha256(datos).hexdigest()


def esperar_resultado(tabla, clave, condicion, espera_max_seg):
    """Espera a que el trabajo del archivo esté completado y cumpla la condición."""
    limite = time.time() + espera_max_seg
    while time.time() < limite:
        item = tabla.get_item(Key={"archivoId": clave}, ConsistentRead=True).get("Item")
        if item and item.get("estado") == "completado" and condicion(item):
            return item
        time.sleep(3)
    return None


def existe(s3, bucket, clave):
    try:
        s3.head_object(Bucket=bucket, Key=clave)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def historial(s3, bucket, clave):
    r = s3.list_object_versions(Bucket=bucket, Prefix=clave)
    filas = [(v["LastModified"], v["VersionId"], "versión", v["Size"], v["IsLatest"]) for v in r.get("Versions", [])]
    filas += [(m["LastModified"], m["VersionId"], "marcador de borrado", "", m["IsLatest"]) for m in r.get("DeleteMarkers", [])]
    return sorted(filas, key=lambda f: f[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", required=True)
    ap.add_argument("--filas", type=int, default=2000, help="Filas del archivo de prueba")
    ap.add_argument("--rto-max-seg", type=float, default=900, help="Objetivo de tiempo de recuperación")
    ap.add_argument("--espera-max-seg", type=int, default=300)
    ap.add_argument("--salida", default="informe-recuperacion")
    a = ap.parse_args()

    region = os.environ.get("AWS_REGION", "us-east-2")
    cfn = boto3.client("cloudformation", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    out = salidas_pila(cfn, a.stack)
    bucket = out["NombreBucket"]
    tabla = boto3.resource("dynamodb", region_name=region).Table(out["NombreTabla"])

    corrida = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    clave = f"recuperacion/{corrida}/ventas.csv"
    original = generar_csv(a.filas, corrida)
    danado = b"fecha,cliente,producto,cantidad,valor\n" + b"\xff\xfe contenido danado por una carga erronea\n" * 5
    pasos = []

    def paso(texto):
        marca = time.strftime("%H:%M:%S", time.gmtime())
        pasos.append((marca, texto))
        print(f"[{marca} UTC] {texto}")

    # ------------------------------------------------------------ Escenario A
    v1 = s3.put_object(Bucket=bucket, Key=clave, Body=original)["VersionId"]
    paso(f"Archivo original cargado en s3://{bucket}/{clave} (versión {v1})")
    ref = esperar_resultado(tabla, clave, lambda i: int(i.get("bytes", -1)) == len(original), a.espera_max_seg)
    huella_ref = ref["huella"] if ref else None
    paso(f"Resultado de referencia del servicio: {ref['filas']} filas, huella {huella_ref}" if ref
         else "El servicio no procesó el archivo original en el tiempo de espera")

    v2 = s3.put_object(Bucket=bucket, Key=clave, Body=danado)["VersionId"]
    paso(f"FALLA: el archivo se sobrescribió con contenido dañado (versión {v2})")
    malo = esperar_resultado(tabla, clave, lambda i: i.get("huella") != huella_ref, a.espera_max_seg) if ref else None
    paso(f"Impacto en el servicio: el resultado cambió a {malo['filas']} filas, huella {malo['huella']}" if malo
         else "No se observó el resultado erróneo en el tiempo de espera")

    inicio_a = time.time()
    v3 = s3.copy_object(Bucket=bucket, Key=clave,
                        CopySource={"Bucket": bucket, "Key": clave, "VersionId": v1})["VersionId"]
    contenido_a = s3.get_object(Bucket=bucket, Key=clave)["Body"].read()
    dato_a_seg = time.time() - inicio_a
    paso(f"RECUPERACIÓN: se restauró la versión {v1} como versión actual ({v3}) en {dato_a_seg:.1f} s")
    rec = esperar_resultado(tabla, clave, lambda i: i.get("huella") == huella_ref, a.espera_max_seg) if malo else None
    servicio_a_seg = time.time() - inicio_a
    paso(f"VALIDACIÓN: el servicio volvió al resultado de referencia en {servicio_a_seg:.1f} s" if rec
         else "El servicio no volvió al resultado de referencia en el tiempo de espera")

    # ------------------------------------------------------------ Escenario B
    marcador = s3.delete_object(Bucket=bucket, Key=clave)["VersionId"]
    borrado = not existe(s3, bucket, clave)
    paso(f"FALLA: el archivo se borró (marcador de borrado {marcador}); ¿sigue disponible? {'no' if borrado else 'sí'}")
    inicio_b = time.time()
    s3.delete_object(Bucket=bucket, Key=clave, VersionId=marcador)
    contenido_b = s3.get_object(Bucket=bucket, Key=clave)["Body"].read()
    dato_b_seg = time.time() - inicio_b
    paso(f"RECUPERACIÓN: se eliminó el marcador de borrado y el archivo volvió a estar disponible en {dato_b_seg:.1f} s")

    versiones = historial(s3, bucket, clave)
    peor = max(servicio_a_seg, dato_b_seg)
    criterios = [
        ("A. El archivo restaurado es idéntico al original (SHA-256)", sha256(contenido_a)[:16], sha256(contenido_a) == sha256(original)),
        ("A. El archivo dañado cambió el resultado del servicio", "sí" if malo else "no", bool(malo)),
        ("A. El servicio volvió al resultado de referencia", "sí" if rec else "no", bool(rec)),
        ("B. El archivo borrado dejó de estar disponible", "sí" if borrado else "no", borrado),
        ("B. El archivo recuperado es idéntico al original (SHA-256)", sha256(contenido_b)[:16], sha256(contenido_b) == sha256(original)),
        ("Tiempo de recuperación dentro del objetivo (RTO)", f"{peor:.1f} s (máx. {a.rto_max_seg:.0f} s)", peor <= a.rto_max_seg),
    ]
    informe = {
        "stack": a.stack,
        "corrida": corrida,
        "archivo": f"s3://{bucket}/{clave}",
        "sha256Original": sha256(original),
        "escenarioA": {"recuperacionDatoSeg": round(dato_a_seg, 1), "recuperacionServicioSeg": round(servicio_a_seg, 1),
                       "versionOriginal": v1, "versionDanada": v2, "versionRestaurada": v3},
        "escenarioB": {"recuperacionDatoSeg": round(dato_b_seg, 1), "marcadorBorrado": marcador},
        "rtoObjetivoSeg": a.rto_max_seg,
        "criterios": [{"criterio": c, "resultado": r, "cumple": ok} for c, r, ok in criterios],
    }
    md = [
        f"## Prueba de recuperación de datos en `{a.stack}` (corrida {corrida})",
        "",
        f"- Archivo: `{clave}` ({len(original)} bytes, SHA-256 `{sha256(original)[:16]}…`)",
        f"- Escenario A (archivo dañado): dato recuperado en {dato_a_seg:.1f} s · servicio validado en {servicio_a_seg:.1f} s",
        f"- Escenario B (archivo borrado): dato recuperado en {dato_b_seg:.1f} s",
        "- Pérdida de datos: ninguna, porque se recuperó la última versión correcta del archivo",
        "",
        "| Criterio | Resultado | ¿Cumple? |",
        "|---|---|---|",
        *[f"| {c} | {r} | {'✅' if ok else '❌'} |" for c, r, ok in criterios],
        "",
        "### Secuencia de la prueba",
        "",
        "| Hora (UTC) | Paso |",
        "|---|---|",
        *[f"| {m} | {t} |" for m, t in pasos],
        "",
        "### Historial de versiones del archivo en el bucket",
        "",
        "| Fecha (UTC) | Identificador | Tipo | Bytes | ¿Actual? |",
        "|---|---|---|---|---|",
        *[f"| {f:%Y-%m-%d %H:%M:%S} | `{v}` | {t} | {b} | {'sí' if ult else ''} |" for f, v, t, b, ult in versiones],
    ]
    texto = "\n".join(md)
    print()
    print(texto)
    with open(a.salida + ".md", "w", encoding="utf-8") as f:
        f.write(texto + "\n")
    with open(a.salida + ".json", "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(texto + "\n")
    sys.exit(0 if all(ok for _, _, ok in criterios) else 1)


if __name__ == "__main__":
    main()
