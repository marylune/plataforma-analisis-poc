#!/usr/bin/env bash
# Elimina los ambientes de la demostración para que no generen costos.
# Ejecutar en AWS CloudShell (región us-east-2):  bash limpiar.sh
# Los buckets tienen control de versiones, así que primero se borran todas las
# versiones; la tabla de producción tiene protección contra eliminación y se desactiva.
set -euo pipefail
REGION=${AWS_REGION:-us-east-2}
CUENTA=$(aws sts get-caller-identity --query Account --output text)

vaciar_bucket () {
  local b=$1
  aws s3api head-bucket --bucket "$b" --region $REGION 2>/dev/null || return 0
  echo "Vaciando $b ..."
  while true; do
    local lote
    lote=$(aws s3api list-object-versions --bucket "$b" --region $REGION --max-items 500 --output json \
      --query '{Objects: [Versions[].{Key:Key,VersionId:VersionId}, DeleteMarkers[].{Key:Key,VersionId:VersionId}][]}')
    if [ "$(echo "$lote" | grep -c '"Key"')" -eq 0 ]; then break; fi
    aws s3api delete-objects --bucket "$b" --region $REGION --delete "$lote" >/dev/null
  done
}

for AMB in dev qa prod; do
  vaciar_bucket "plataforma-$AMB-archivos-$CUENTA"
  if [ "$AMB" = "prod" ]; then
    aws dynamodb update-table --table-name plataforma-prod-trabajos --no-deletion-protection-enabled \
      --region $REGION >/dev/null 2>&1 || true
  fi
  echo "Eliminando la pila plataforma-$AMB ..."
  aws cloudformation delete-stack --stack-name "plataforma-$AMB" --region $REGION || true
done
for AMB in dev qa prod; do
  aws cloudformation wait stack-delete-complete --stack-name "plataforma-$AMB" --region $REGION || true
done
echo "Listo. Revise en CloudFormation que no queden pilas plataforma-*."
