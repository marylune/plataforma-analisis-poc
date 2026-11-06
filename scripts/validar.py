"""Validación de un ambiente desplegado (criterios de las secciones 5.2 y 5.4 del plan).

1. Carga N archivos CSV de prueba del tamaño indicado al bucket del ambiente.
2. Espera a que la función los procese y lee el resultado de cada trabajo en DynamoDB.
3. Calcula el tiempo de procesamiento (promedio y percentil 95) y la latencia total.
4. Opcionalmente carga un archivo inválido y comprueba que llega a la cola de errores.
5. Compara con los criterios y escribe un informe en Markdown y en JSON.

Termina con código 1 si algún criterio no se cumple, para que el pipeline falle.

Uso:
  python scripts/validar.py --stack plataforma-qa --archivos 10 --tamano-mb 10 --p95-max-seg 60 --probar-cola-errores
"""
import argparse
import io
import json
import math
import os
import random
import sys
import time
import uuid

import boto3


def salidas_pila(cfn, stack):
    pila = cfn.describe_stacks(StackName=stack)["Stacks"][0]
    return {o["OutputKey"]: o["OutputValue"] for o in pila.get("Outputs", [])}


def generar_csv(tamano_mb, semilla):
    rnd = random.Random(semilla)
    objetivo = int(tamano_mb * 1024 * 1024)
    buf = io.StringIO()
    buf.write("fecha,cliente,producto,cantidad,valor\n")
    while buf.tell() < objetivo:
        buf.write(f"2026-11-{rnd.randint(1, 30):02d},C{rnd.randint(1, 5000)},P{rnd.randint(1, 300)},"
                  f"{rnd.randint(1, 50)},{rnd.uniform(1000, 900000):.2f}\n")
    return buf.getvalue().encode("utf-8")


def percentil(valores, p):
    orden = sorted(valores)
    k = max(0, math.ceil(p / 100 * len(orden)) - 1)
    return orden[k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", required=True)
    ap.add_argument("--archivos", type=int, default=10)
    ap.add_argument("--tamano-mb", type=float, default=10)
    ap.add_argument("--p95-max-seg", type=float, default=60, help="Criterio: percentil 95 del procesamiento")
    ap.add_argument("--espera-max-seg", type=int, default=600)
    ap.add_argument("--probar-cola-errores", action="store_true")
    ap.add_argument("--salida", default="informe-validacion")
    a = ap.parse_args()

    region = os.environ.get("AWS_REGION", "us-east-2")
    cfn = boto3.client("cloudformation", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    sqs = boto3.client("sqs", region_name=region)
    out = salidas_pila(cfn, a.stack)
    tabla = boto3.resource("dynamodb", region_name=region).Table(out["NombreTabla"])

    corrida = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    datos = generar_csv(a.tamano_mb, corrida)
    claves = [f"pruebas/{corrida}/archivo-{i:03d}.csv" for i in range(a.archivos)]
    print(f"Cargando {a.archivos} archivos de {a.tamano_mb} MB en {out['NombreBucket']} ...")
    for clave in claves:
        s3.put_object(Bucket=out["NombreBucket"], Key=clave, Body=datos)

    clave_invalida = None
    errores_antes = 0
    if a.probar_cola_errores:
        errores_antes = int(sqs.get_queue_attributes(
            QueueUrl=out["UrlColaErrores"], AttributeNames=["ApproximateNumberOfMessages"]
        )["Attributes"]["ApproximateNumberOfMessages"])
        clave_invalida = f"invalidos/{corrida}/archivo-invalido.csv"
        s3.put_object(Bucket=out["NombreBucket"], Key=clave_invalida, Body=b"no es un archivo valido\n")

    print("Esperando el procesamiento ...")
    resultados, inicio = {}, time.time()
    while len(resultados) < len(claves) and time.time() - inicio < a.espera_max_seg:
        for clave in claves:
            if clave in resultados:
                continue
            item = tabla.get_item(Key={"archivoId": clave}, ConsistentRead=True).get("Item")
            if item and item.get("estado") == "completado":
                resultados[clave] = item
        time.sleep(5)

    duraciones = [int(i["duracionProcesamientoMs"]) / 1000 for i in resultados.values()]
    latencias = [int(i["latenciaTotalMs"]) / 1000 for i in resultados.values()]
    memorias = sorted({int(i["memoriaMb"]) for i in resultados.values()})
    versiones = sorted({str(i["versionFuncion"]) for i in resultados.values()})

    llego_a_errores = None
    if clave_invalida:
        # 2 intentos con un tiempo de visibilidad de 360 s: puede tardar unos 6 a 12 minutos.
        limite = time.time() + 1200
        while time.time() < limite:
            n = int(sqs.get_queue_attributes(
                QueueUrl=out["UrlColaErrores"], AttributeNames=["ApproximateNumberOfMessages"]
            )["Attributes"]["ApproximateNumberOfMessages"])
            if n > errores_antes:
                llego_a_errores = True
                break
            time.sleep(30)
        else:
            llego_a_errores = False

    criterios = [
        ("Todos los archivos procesados", f"{len(resultados)}/{len(claves)}", len(resultados) == len(claves)),
        ("Percentil 95 del procesamiento", f"{percentil(duraciones, 95):.1f} s (máx. {a.p95_max_seg:.0f} s)" if duraciones else "sin datos",
         bool(duraciones) and percentil(duraciones, 95) <= a.p95_max_seg),
    ]
    if clave_invalida:
        criterios.append(("Archivo inválido en la cola de errores", "sí" if llego_a_errores else "no", bool(llego_a_errores)))

    informe = {
        "stack": a.stack,
        "corrida": corrida,
        "archivos": len(claves),
        "tamanoMb": a.tamano_mb,
        "memoriaMb": memorias,
        "versionFuncion": versiones,
        "procesamientoPromedioSeg": round(sum(duraciones) / len(duraciones), 2) if duraciones else None,
        "procesamientoP95Seg": round(percentil(duraciones, 95), 2) if duraciones else None,
        "latenciaTotalP95Seg": round(percentil(latencias, 95), 2) if latencias else None,
        "criterios": [{"criterio": c, "resultado": r, "cumple": ok} for c, r, ok in criterios],
    }
    md = [
        f"## Validación de `{a.stack}` (corrida {corrida})",
        "",
        f"- Archivos: {len(claves)} de {a.tamano_mb} MB",
        f"- Memoria de la función: {', '.join(map(str, memorias))} MB · versión publicada: {', '.join(versiones)}",
        f"- Procesamiento: promedio {informe['procesamientoPromedioSeg']} s · percentil 95 {informe['procesamientoP95Seg']} s",
        f"- Latencia total (carga → completado), percentil 95: {informe['latenciaTotalP95Seg']} s",
        "",
        "| Criterio | Resultado | ¿Cumple? |",
        "|---|---|---|",
        *[f"| {c} | {r} | {'✅' if ok else '❌'} |" for c, r, ok in criterios],
    ]
    texto = "\n".join(md)
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
