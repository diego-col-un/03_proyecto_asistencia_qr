#!/usr/bin/env bash
# Prueba de POST /asistencias (casos 200, 409, 404, 410 y 400).
# Uso:  bash probar-asistencia.sh
# Si API_URL o TABLA_SESIONES no estan definidas, las lee del stack gtn-asistencia-qr.

set -u
STACK="${STACK:-gtn-asistencia-qr}"

salida() {
  aws cloudformation describe-stacks --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text --no-cli-pager
}

API_URL="${API_URL:-$(salida ApiUrl)}"
API_URL="${API_URL%/}"
TABLA_SESIONES="${TABLA_SESIONES:-$(salida TablaSesionesNombre)}"

if [ -z "$API_URL" ] || [ -z "$TABLA_SESIONES" ]; then
  echo "No pude obtener API_URL o TABLA_SESIONES. Defínelas a mano o revisa el stack $STACK."
  exit 1
fi

echo "API:   $API_URL"
echo "Tabla: $TABLA_SESIONES"
echo

AHORA=$(date +%s)
HOY=$(date +%F)
OK_ID="test-vigente-${AHORA}-abcdef"
EXP_ID="test-vencida-${AHORA}-abcdef"

# Sesion vigente (10 min) y sesion vencida (hace 100 s)
aws dynamodb put-item --table-name "$TABLA_SESIONES" --no-cli-pager --item "{
  \"sessionId\":{\"S\":\"$OK_ID\"},\"courseId\":{\"S\":\"GC-101\"},
  \"date\":{\"S\":\"$HOY\"},\"createdAt\":{\"N\":\"$AHORA\"},
  \"expiresAt\":{\"N\":\"$((AHORA + 600))\"},\"teacherId\":{\"S\":\"test\"}}" || exit 1

aws dynamodb put-item --table-name "$TABLA_SESIONES" --no-cli-pager --item "{
  \"sessionId\":{\"S\":\"$EXP_ID\"},\"courseId\":{\"S\":\"GC-101\"},
  \"date\":{\"S\":\"$HOY\"},\"createdAt\":{\"N\":\"$((AHORA - 700))\"},
  \"expiresAt\":{\"N\":\"$((AHORA - 100))\"},\"teacherId\":{\"S\":\"test\"}}" || exit 1

FALLOS=0
llamar() { # $1=descripcion  $2=codigo esperado  $3=cuerpo JSON
  local codigo marca="OK   "
  codigo=$(curl -s -o /tmp/resp.json -w "%{http_code}" -X POST "$API_URL/asistencias" \
    -H "Content-Type: application/json" -d "$3")
  if [ "$codigo" != "$2" ]; then marca="FALLO"; FALLOS=$((FALLOS + 1)); fi
  echo "[$marca] $1 -> $codigo (esperado $2) $(cat /tmp/resp.json)"
}

llamar "Registro valido"    200 "{\"sessionId\":\"$OK_ID\",\"studentId\":\"1055751123\"}"
llamar "Duplicado"          409 "{\"sessionId\":\"$OK_ID\",\"studentId\":\"1055751123\"}"
llamar "Otro estudiante"    200 "{\"sessionId\":\"$OK_ID\",\"studentId\":\"1055751124\"}"
llamar "Sesion inexistente" 404 '{"sessionId":"no-existe-0123456789abcdef","studentId":"1055751123"}'
llamar "QR vencido"         410 "{\"sessionId\":\"$EXP_ID\",\"studentId\":\"1055751123\"}"
llamar "studentId invalido" 400 "{\"sessionId\":\"$OK_ID\",\"studentId\":\"abc\"}"
llamar "Cuerpo no es JSON"  400 'esto no es json'

echo
if [ "$FALLOS" -eq 0 ]; then echo "Todas las pruebas pasaron."; else echo "$FALLOS prueba(s) fallaron."; fi
