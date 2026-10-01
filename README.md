# 🏷️ [Sistema de asistencia con QR (serverless)] — Proyecto [03]

> **Ficha del caso** — Controlar asistencia a laboratorios consume 10 minutos de cada sesión en llamado a lista. La coordinación quiere que el estudiante escanee un QR único por sesión y la asistencia quede registrada al instante con reporte automático. No quieren servidores: las clases son 2 días a la semana y el resto del tiempo el sistema estaría desperdiciado.

| Campo | Valor |
|---|---|
| Proyecto | [03 · Sistema de asistencia con QR (serverless)] |
| Integrantes | [Diego Fernando Aristizábal Gutiérrez 1055751123, ] |
| URL demo | https://...|
| Costo mensual real | USD ... (objetivo: < 1 USD) |
| Despliegue | `aws cloudformation deploy --template-file iac/main.yaml --stack-name gtn-[equipo] --capabilities CAPABILITY_NAMED_IAM` |

## 🏗️ Arquitectura
[Diagrama en docs/arquitectura.png — exporta tu diagrama y referéncialo aquí]

## 🔑 Decisiones (resumen — la tabla completa en docs/decisiones.md)
| Decisión | Elegimos | Alternativa descartada | Por qué |
|---|---|---|---|
| | | | |

## 💰 Costos
Ver `docs/costos.md` — estimado vs real y optimizaciones aplicadas.

## 🚀 Cómo levantar
1. `cd app && docker compose up --build` → local
2. `aws cloudformation deploy ...` → AWS (ver `iac/README.md`)
