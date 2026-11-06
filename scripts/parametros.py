"""Devuelve los parámetros de un ambiente (infra/samconfig.toml) más los que agrega el pipeline.

`sam deploy --parameter-overrides` reemplaza por completo los parámetros del archivo de
configuración, así que el pipeline usa este script para no perder los valores del ambiente.

Uso: python scripts/parametros.py qa VersionApp=1.4.0
"""
import sys
import tomllib
from pathlib import Path

ambiente, extras = sys.argv[1], sys.argv[2:]
config = tomllib.loads((Path(__file__).parent.parent / "infra" / "samconfig.toml").read_text(encoding="utf-8"))
base = config[ambiente]["deploy"]["parameters"]["parameter_overrides"]
print(" ".join([base, *extras]))
