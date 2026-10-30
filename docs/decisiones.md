# Decisiones de arquitectura (Nota 2)
| # | Decisión | Alternativas | Elegida | Por qué | Pilar asociado |
|---|---|---|---|---|---|
| 1 | | | | | |
**Revisión 6 pilares Well-Architected:**
| Pilar | ¿Cómo lo cumple nuestro diseño? | Riesgo detectado |
|---|---|---|
| Excelencia operativa | | |
| Seguridad | | |
| Fiabilidad | | |
| Eficiencia rendimiento | | |
| Optimización de costos | | |
| Sostenibilidad | | |

## Tabla Sesiones: expiración del QR
|
|La tabla `Sesiones` usa DynamoDB en modo on-demand y TTL sobre el atributo
|`expiresAt` (epoch en segundos).
|
|**Importante:** el TTL de DynamoDB elimina los ítems con retraso (puede tardar
|horas después de `expiresAt`). Por eso un registro vencido puede seguir existiendo
|en la tabla.
|
|Regla para quien valide el token (Lambda `registrar-asistencia`):
|no basta con comprobar que el `sessionId` existe. Siempre hay que comparar
|`expiresAt` con la hora actual (`int(time.time())`):
|
|- el `sessionId` no existe → 404
|- existe pero `expiresAt <= ahora` → 410 (QR expirado)
