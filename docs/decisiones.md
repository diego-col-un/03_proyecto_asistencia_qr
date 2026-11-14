# Decisiones de arquitectura (Nota 2)
| # | Decisión | Alternativas | Elegida | Por qué | Pilar asociado |
|---|---|---|---|---|---|
| B-1 | Cómo evitar asistencias duplicadas | (a) Consultar si existe y luego escribir; (b) transacción DynamoDB; (c) validar solo en la página | Clave compuesta `sessionId` + `studentId` y `PutItem` con `attribute_not_exists(sessionId)` | Una sola operación atómica: dos solicitudes simultáneas del mismo estudiante no pueden crear dos filas. La opción (a) deja una ventana de carrera y (b) añade costo y complejidad sin ganancia | Fiabilidad |
| B-2 | Cómo saber si un QR venció | (a) Confiar en el TTL de DynamoDB; (b) comparar `expiresAt` en el código | Comparar `expiresAt` con la hora del servidor en cada registro (410) | El TTL borra con retraso de hasta horas, así que un QR vencido seguiría registrando asistencia. Es el criterio de aceptación "un QR vencido nunca registra" | Seguridad / Fiabilidad |
| B-3 | Lectura de la sesión | Lectura eventualmente consistente (por defecto) | Lectura consistente (`ConsistentRead=True`) en `Sesiones` | Evita un 404 falso si el estudiante escanea justo después de crear la sesión. Cuesta el doble de unidades de lectura, un valor despreciable a este volumen | Fiabilidad |
| B-4 | Modo de capacidad de `Asistencias` | Capacidad aprovisionada | On-demand (`PAY_PER_REQUEST`) | El uso son ráfagas de unos minutos dos días a la semana; se paga por solicitud y no hay capacidad ociosa (HU-04) | Optimización de costos |
| B-5 | Copias de seguridad de `Asistencias` | PITR activado | Sin PITR | Decisión de costo. **Riesgo aceptado:** no hay recuperación a un instante dado ante borrado o corrupción. En producción real se activaría | Optimización de costos (a cambio de Fiabilidad) |
| B-6 | Índice para el reporte | Índice con solo claves o con atributos elegidos; consulta con `Scan` | `curso-fecha-index` (PK `courseId`, SK `date`) con proyección `ALL` | C consulta por curso y fecha sin recorrer la tabla. Los ítems son diminutos, así que proyectar todo cuesta poco y evita lecturas adicionales a la tabla base. Pendiente confirmar con C | Eficiencia de rendimiento |
| B-7 | Cómputo de la Lambda | x86; mayor memoria; empaquetar dependencias | Python 3.12, arm64, 128 MB, código en línea (solo `boto3`, ya incluido en el runtime) | Menor costo por ejecución y despliegue sin paso de empaquetado para esta función | Optimización de costos / Sostenibilidad |
| B-8 | Límite de solicitudes en la API | Un único límite global (5 req/s, ráfaga 10) | Límite propio para `POST /asistencias`: 50 req/s, ráfaga 100 (parámetros de CloudFormation) | Toda la clase escanea casi a la vez; el límite global rechazaría con 429 a estudiantes legítimos. Sigue acotando abuso y gasto | Fiabilidad / Optimización de costos |
| B-9 | Rol IAM de la Lambda | Rol propio de mínimo privilegio | `LabRole` existente (parámetro `NombreRolLambda`) | AWS Academy Learner Lab no permite crear roles. **Limitación del entorno**; ver política mínima abajo | Seguridad |
| B-10 | Validación y respuestas de error | Aceptar cualquier entrada; devolver detalle del error interno | `sessionId` con formato de token, `studentId` numérico de 6 a 12 dígitos; 400 para entrada inválida y 500 genérico sin detalles | Reduce abuso y no filtra información interna. Se añade el 400 al contrato original (200/404/410/409) | Seguridad |
| B-11 | Identidad del estudiante | Lista de matriculados; autenticación (p. ej. Cognito) | Solo el código estudiantil, sin autenticación | El alcance del curso no exige autenticación fuerte. **Limitación documentada:** un estudiante puede registrar el código de otro | Seguridad |
| B-12 | Configuración de la página del estudiante | URL de la API escrita en el código; URL recibida por parámetro de la dirección | Archivo `config.js` aparte, que completa quien despliega | Separa código y entorno. Se descartó recibir la API por parámetro porque permitiría armar enlaces que envíen los datos a otro servidor. El hosting final (S3 estático) está pendiente de acordar con A | Excelencia operativa / Seguridad |

**Revisión 6 pilares Well-Architected:**
| Pilar | ¿Cómo lo cumple nuestro diseño? | Riesgo detectado |
|---|---|---|
| Excelencia operativa | B: Tabla, Lambda y ruta definidas en CloudFormation; scripts de prueba reproducibles (`probar-asistencia.sh`, `prueba_concurrencia.py`); logs con retención de 7 días; `cfn-lint` sobre la plantilla | B: El despliegue depende de credenciales manuales del Learner Lab; el `Jenkinsfile` de la plantilla no está adaptado al enfoque serverless |
| Seguridad | B: Validación de entradas, errores sin detalle interno, expiración verificada en el servidor, límite de solicitudes por ruta | B: CORS abierto (`*`) pendiente de restringir a la URL de la página; `LabRole` más amplio que el mínimo; suplantación posible con un código estudiantil ajeno |
| Fiabilidad | B: Escritura condicional sin duplicados bajo concurrencia; servicios administrados de AWS; lectura consistente de la sesión | B: Sin PITR. Con ráfagas de 100 solicitudes simultáneas desde un cliente local hubo latencias altas y, en una corrida, 6 solicitudes sin respuesta (causa en diagnóstico; en la segunda corrida no hubo errores) |
| Eficiencia de rendimiento | B: Serverless que escala con la demanda; dos operaciones DynamoDB por registro (`GetItem` y `PutItem`) | B: Arranque en frío de la Lambda con ráfagas; latencia medida por completar con los resultados del diagnóstico |
| Optimización de costos | B: On-demand, sin servidores ociosos, arm64 con 128 MB, logs con retención corta, límite de solicitudes que acota el gasto ante abuso | B: Costo por solicitud por calcular y documentar en `costos.md` |
| Sostenibilidad | B: Sin recursos ociosos; arm64; retención corta de logs | B: Los datos de prueba se acumulan en `Asistencias`; hay que borrar el stack al terminar el trabajo (`delete-stack`) |

## Política IAM mínima (referencia, no aplicada en el Learner Lab)

Es la política que tendría el rol propio de `registrar-asistencia` fuera del Learner Lab:

- `dynamodb:GetItem` solo sobre la tabla `Sesiones`.
- `dynamodb:PutItem` solo sobre la tabla `Asistencias`.
- `logs:CreateLogStream` y `logs:PutLogEvents` solo sobre el grupo de logs de la función.

En el Learner Lab se usa `LabRole`, que es más amplio. El riesgo se acota porque el código solo ejecuta esas dos operaciones.

## Pruebas realizadas (insumo para el informe)

- Casos funcionales (`scripts/probar-asistencia.sh`): 200, 409, 404, 410 y 400, todos con el resultado esperado en AWS real (captura en `evidencias/`).
- Concurrencia (`scripts/prueba_concurrencia.py`, 100 solicitudes simultáneas por escenario):
  - Mismo estudiante ×100: una sola solicitud con 200 y 99 con 409, en todas las corridas. No hay duplicados.
  - 100 estudiantes distintos: en la segunda corrida, 100 solicitudes con 200 (p50 2684 ms, p95 15779 ms); en la primera, 94 con 200 y 6 sin respuesta.
  - Reportes en `evidencias/concurrencia-*.md`.

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