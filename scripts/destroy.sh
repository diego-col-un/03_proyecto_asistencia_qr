#!/usr/bin/env bash
# Teardown completo: borra el stack y el bucket de artefactos (que vive fuera
# de CloudFormation, ver docs/decisiones.md). Es el inverso de deploy.sh.
# Uso: ./scripts/destroy.sh <nombre-equipo>
#
# El bucket web lo vacia y borra el propio stack (custom resource VaciarBucketWeb),
# por eso aqui solo hay que ocuparse del bucket de artefactos.
set -euo pipefail

NOMBRE_EQUIPO="${1:?Uso: ./scripts/destroy.sh <nombre-equipo>}"

STACK="gtn-asistencia-qr"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="gtn-${NOMBRE_EQUIPO}-artifacts-${ACCOUNT}"

cd "$(dirname "$0")/.."

echo ">> Borrando stack ${STACK}"
if aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" >/dev/null 2>&1; then
  aws cloudformation delete-stack --stack-name "$STACK" --region "$REGION"
  echo "   esperando a que termine el borrado del stack..."
  aws cloudformation wait stack-delete-complete --stack-name "$STACK" --region "$REGION"
  echo "   stack eliminado."
else
  echo "   el stack no existe, se omite."
fi

echo ">> Borrando bucket de artefactos: s3://${BUCKET}"
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  # --force vacia el bucket antes de eliminarlo.
  aws s3 rb "s3://${BUCKET}" --force
  echo "   bucket de artefactos eliminado."
else
  echo "   el bucket de artefactos no existe, se omite."
fi

# La Lambda de autovaciado escribe logs mientras el stack se borra y recrea su
# LogGroup; por eso no lo gestiona CloudFormation. Se espera unos segundos a que
# termine esa escritura y se borra al final para dejar la cuenta vacia.
LOG_GROUP="/aws/lambda/gtn-${NOMBRE_EQUIPO}-vaciar-bucket-web"
echo ">> Borrando LogGroup de la Lambda de autovaciado: ${LOG_GROUP}"
sleep 10
aws logs delete-log-group --log-group-name "$LOG_GROUP" --region "$REGION" 2>/dev/null \
  && echo "   LogGroup eliminado." \
  || echo "   el LogGroup no existe, se omite."

echo ">> Teardown completo."
