# 🏷️ Sistema de asistencia con QR (serverless) — Proyecto 03

> **Ficha del caso** — Controlar asistencia a laboratorios consume 10 minutos de cada sesión en llamado a lista. La coordinación quiere que el estudiante escanee un QR único por sesión y la asistencia quede registrada al instante con reporte automático. No quieren servidores: las clases son 2 días a la semana y el resto del tiempo el sistema estaría desperdiciado.

| Campo | Valor |
|---|---|
| Proyecto | 03 · Sistema de asistencia con QR (serverless) |
| Integrantes | Alejandro Ospina Parra (A · HU-01), Diego Fernando Aristizábal Gutiérrez 1055751123 (HU-02), _(pendiente C · HU-03/04)_ |
| URL demo | https://... _(pendiente)_ |
| Costo mensual real | USD ... (objetivo: < 1 USD) |
| Despliegue | `./scripts/deploy.sh <nombre-equipo>` (ver "Cómo levantar") |

## 🏗️ Arquitectura

Solo servicios serverless de AWS. Sin EC2, sin contenedores.

```
Docente    → API Gateway (HTTP API) → Lambda crear-sesion       → DynamoDB Sesiones
                                           └→ devuelve QR (SVG) con URL de escaneo
Estudiante → escanea QR → página web (S3) → API Gateway → Lambda registrar-asistencia → DynamoDB Asistencias
EventBridge (diario) → Lambda generar-reporte → lee Asistencias → HTML en S3
```

Componentes: **API Gateway (HTTP API v2)** · **Lambda** (Python 3.12, arm64, 128 MB) · **DynamoDB** (PAY_PER_REQUEST) · **S3** (páginas web y reportes) · todo definido en **CloudFormation** (`iac/main.yaml`).

[Diagrama en `docs/arquitectura.png` — exporta tu diagrama y referéncialo aquí]

## 🔑 Decisiones (resumen — la tabla completa en `docs/decisiones.md`)

| Decisión | Elegimos | Alternativa descartada | Por qué |
|---|---|---|---|
| Tipo de API | HTTP API (API Gateway v2) | REST API | Menor costo y latencia para este caso |
| Cómputo | Lambda arm64 128 MB | EC2 / contenedores | Sin servidores, costo proporcional al uso |
| Rol de las Lambdas | `LabRole` (parámetro) | Rol por Lambda (mínimo privilegio) | AWS Academy Learner Lab no permite crear roles IAM |
| Generación del QR | `segno` (Python puro) | Servicio externo de QR | El QR se genera dentro de la app, sin dependencias externas |

## 💰 Costos

Ver `docs/costos.md` — estimado vs real y optimizaciones aplicadas.

## 🚀 Cómo levantar

Requisitos: AWS CLI configurado (credenciales del Learner Lab), Python 3.12 y `cfn-lint`.

1. **Validar la plantilla**

   ```bash
   cfn-lint iac/*.yaml
   ```

2. **Desplegar el stack** (empaqueta las Lambdas, sube artefactos a S3 y hace `cloudformation deploy`)

   ```bash
   ./scripts/deploy.sh <nombre-equipo>
   # Ej.: ./scripts/deploy.sh qr-serverless
   ```

   El script imprime los outputs del stack (URL de la API, endpoint del docente, nombres de tablas).

3. **Probar el registro de asistencia**

   ```bash
   ./scripts/probar-asistencia.sh <ApiUrl>
   ```

Para eliminar todo: `aws cloudformation delete-stack --stack-name gtn-asistencia-qr` (ver notas de limpieza en `iac/README.md`).

## 📁 Estructura

```
app/
  crear_sesion/          Lambda HU-01 (docente genera el QR)
  registrar_asistencia/  Lambda HU-02 (estudiante escanea)
  generar_reporte/       Lambda HU-03 (reporte automático)
  web/docente/           página del docente
  web/estudiante/        página del estudiante
iac/main.yaml            plantilla CloudFormation completa
scripts/                 deploy.sh y pruebas
docs/                    decisiones y costos
```
