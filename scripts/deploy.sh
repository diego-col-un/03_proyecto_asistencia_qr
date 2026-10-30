#!/usr/bin/env bash
# Despliegue completo: empaqueta las Lambdas, las sube a S3 y despliega el stack.
# Uso: ./scripts/deploy.sh <nombre-equipo> [ParametroCF=valor ...]
# Ej.: ./scripts/deploy.sh qr-serverless ScanBaseUrl=https://mi-sitio/estudiante/index.html
set -euo pipefail

NOMBRE_EQUIPO="${1:?Uso: ./scripts/deploy.sh <nombre-equipo> [Param=valor ...]}"
shift || true

STACK="gtn-asistencia-qr"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="gtn-${NOMBRE_EQUIPO}-artifacts-${ACCOUNT}"
PY="${PYTHON:-python}"

cd "$(dirname "$0")/.."

echo ">> Bucket de artefactos: s3://${BUCKET}"
if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  aws s3 mb "s3://${BUCKET}" --region "$REGION"
fi

echo ">> Construyendo crear_sesion (dependencias para Lambda arm64, Python 3.12)"
rm -rf build
mkdir -p build/crear_sesion
"$PY" -m pip install -q --upgrade \
  --target build/crear_sesion \
  --platform manylinux2014_aarch64 --python-version 3.12 --only-binary=:all: \
  -r app/crear_sesion/requirements.txt
rm -rf build/crear_sesion/bin build/crear_sesion/share
cp app/crear_sesion/handler.py build/crear_sesion/

echo ">> Empaquetando plantilla"
aws cloudformation package \
  --template-file iac/main.yaml \
  --s3-bucket "$BUCKET" \
  --output-template-file build/packaged.yaml

echo ">> Desplegando stack ${STACK}"
aws cloudformation deploy \
  --template-file build/packaged.yaml \
  --stack-name "$STACK" \
  --parameter-overrides "NombreEquipo=${NOMBRE_EQUIPO}" "$@" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION"

echo ">> Outputs:"
aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs" --output table
