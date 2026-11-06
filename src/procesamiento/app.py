"""Función de procesamiento de archivos (demostración técnica, Proyecto 3).

Recibe desde SQS los eventos "Object Created" que EventBridge genera cuando se carga
un archivo en S3, lo procesa y registra el resultado del trabajo en DynamoDB.

El procesamiento simula una transformación que depende de la CPU (lectura del CSV,
agregados y varias pasadas de cálculo sobre el contenido). Como en Lambda la CPU crece
en proporción a la memoria, el tiempo de procesamiento baja cuando se aumenta la
memoria de la función: eso es lo que se mide en el escenario de cambio #63.

Los archivos cargados con el prefijo "invalidos/" fallan a propósito, para validar
que los mensajes que no se pueden procesar llegan a la cola de errores.
"""

import csv
import hashlib
import io
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import unquote_plus

import boto3

PREFIJO_INVALIDOS = "invalidos/"

_s3 = None
_tabla = None


def _clientes():
    global _s3, _tabla
    if _s3 is None:
        _s3 = boto3.client("s3")
        _tabla = boto3.resource("dynamodb").Table(os.environ["TABLA_TRABAJOS"])
    return _s3, _tabla


def procesar_contenido(datos: bytes, pasadas: int) -> dict:
    """Calcula filas y suma de los valores numéricos, y aplica la carga de cómputo."""
    filas = 0
    total = 0.0
    lector = csv.reader(io.StringIO(datos.decode("utf-8", errors="replace")))
    for fila in lector:
        filas += 1
        for celda in fila:
            try:
                total += float(celda)
            except ValueError:
                pass
    huella = b""
    for _ in range(pasadas):
        huella = hashlib.sha256(huella + datos).digest()
    return {"filas": filas, "total": round(total, 2), "huella": huella.hex()[:16]}


def _a_epoch_ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def handler(event, context):
    s3, tabla = _clientes()
    pasadas = int(os.environ.get("PASADAS_PROCESAMIENTO", "400"))

    for registro in event["Records"]:
        evento = json.loads(registro["body"])
        detalle = evento["detail"]
        bucket = detalle["bucket"]["name"]
        clave = unquote_plus(detalle["object"]["key"])
        cargado_ms = _a_epoch_ms(evento["time"])

        tabla.put_item(Item={
            "archivoId": clave,
            "estado": "procesando",
            "cargadoEnMs": cargado_ms,
            "versionFuncion": context.function_version,
        })

        if clave.startswith(PREFIJO_INVALIDOS):
            # Falla controlada: tras 2 intentos, SQS envía el mensaje a la cola de errores.
            raise ValueError(f"Archivo inválido para la prueba de la cola de errores: {clave}")

        inicio = time.perf_counter()
        datos = s3.get_object(Bucket=bucket, Key=clave)["Body"].read()
        resultado = procesar_contenido(datos, pasadas)
        duracion_ms = int((time.perf_counter() - inicio) * 1000)
        completado_ms = int(time.time() * 1000)

        tabla.put_item(Item={
            "archivoId": clave,
            "estado": "completado",
            "bytes": len(datos),
            "filas": resultado["filas"],
            "total": str(resultado["total"]),
            "huella": resultado["huella"],
            "duracionProcesamientoMs": duracion_ms,
            "latenciaTotalMs": completado_ms - cargado_ms,
            "cargadoEnMs": cargado_ms,
            "completadoEn": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "memoriaMb": int(context.memory_limit_in_mb),
            "versionFuncion": context.function_version,
            "ambiente": os.environ.get("AMBIENTE", ""),
        })
        print(json.dumps({
            "mensaje": "archivo procesado",
            "archivo": clave,
            "duracionProcesamientoMs": duracion_ms,
            "memoriaMb": int(context.memory_limit_in_mb),
            "versionFuncion": context.function_version,
        }))

    return {"procesados": len(event["Records"])}
