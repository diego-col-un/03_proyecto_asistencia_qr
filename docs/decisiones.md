# Decisiones de arquitectura (Nota 2)
| # | Decisión | Alternativas | Elegida | Por qué | Pilar asociado |
|---|---|---|---|---|---|
| 1 | Tipo de API | REST API vs HTTP API | HTTP API (API Gateway v2) | Menor costo y latencia; suficiente para este caso (no se necesitan API keys nativas ni WAF) | Optimización de costos |
| 2 | Cómputo | EC2 / contenedores vs Lambda | Lambda (Python 3.12, arm64, 128 MB) | Sin servidores; costo proporcional al uso; las clases son 2 días/semana | Optimización de costos, Sostenibilidad |
| 3 | Rol IAM de las Lambdas | Rol por Lambda (mínimo privilegio) vs rol compartido existente | `LabRole` (parámetro `NombreRolLambda`) | AWS Academy Learner Lab no permite crear roles IAM. Es una limitación del entorno, no una elección de diseño (ver riesgo abajo) | Seguridad |
| 4 | Generación del QR | Servicio/API externa vs librería local | `segno` (Python puro) empaquetado en el zip | El QR se genera dentro de la app, sin dependencias externas ni costo adicional | Seguridad, Optimización de costos |
| 5 | Facturación DynamoDB | Aprovisionada vs bajo demanda | PAY_PER_REQUEST (on-demand) | Tráfico intermitente y bajo; se paga solo por request | Optimización de costos |
| 6 | Hosting de las páginas web | CloudFront + S3 vs S3 website | S3 website (acceso público de solo lectura) | CloudFront agrega costo y complejidad que el objetivo de <1 USD/mes no justifica; las páginas son estáticas y públicas | Optimización de costos |
| 7 | Bucket de artefactos de despliegue | Dentro de CloudFormation vs fuera, gestionado por scripts | Fuera del stack, creado por `deploy.sh` y borrado por `destroy.sh` | `cloudformation package` necesita el bucket **antes** de que exista el stack (problema del huevo y la gallina). Se gestiona con el par simétrico de scripts | Excelencia operativa |
| 8 | Borrado limpio del bucket web | Vaciado manual documentado vs automático | Custom resource + Lambda que vacía el bucket en `delete-stack` | Cumple el criterio "eliminar el stack sin pasos manuales"; costo ~0 (solo corre en operaciones de CFN) | Excelencia operativa |

**Revisión 6 pilares Well-Architected:**
| Pilar | ¿Cómo lo cumple nuestro diseño? | Riesgo detectado |
|---|---|---|
| Excelencia operativa | Todo es IaC (`iac/main.yaml`); despliegue y teardown con un comando (`deploy.sh` / `destroy.sh`); validación con `cfn-lint` antes de cada PR | El bucket de artefactos y el LogGroup de autovaciado se gestionan por script, no por CFN (documentado arriba) |
| Seguridad | QR efímero (expiración corta); validación estricta de entrada en las Lambdas; escritura condicional contra duplicados; secreto de endpoint planificado (paso 3) | `LabRole` es permisivo (no hay mínimo privilegio); CORS aún en `*` (pendiente restringir a la URL web) |
| Fiabilidad | DynamoDB on-demand (sin límites de capacidad que agotar); lectura consistente al validar sesiones; reintentos nativos de API Gateway → Lambda | Sin pruebas automáticas aún para `crear_sesion` |
| Eficiencia rendimiento | Lambda arm64 (mejor precio/rendimiento); 128 MB basta para la carga; HTTP API (menor latencia que REST) | Cold starts posibles por el patrón de uso intermitente (aceptable para el caso) |
| Optimización de costos | Todo serverless y bajo demanda; S3 website en vez de CloudFront; sin EC2; objetivo <1 USD/mes | — |
| Sostenibilidad | arm64 (Graviton, más eficiente); recursos que solo consumen al usarse; clases 2 días/semana sin infraestructura ociosa | — |

## Tabla Sesiones: expiración del QR

La tabla `Sesiones` usa DynamoDB en modo on-demand y TTL sobre el atributo
`expiresAt` (epoch en segundos).

**Importante:** el TTL de DynamoDB elimina los ítems con retraso (puede tardar
horas después de `expiresAt`). Por eso un registro vencido puede seguir existiendo
en la tabla.

Regla para quien valide el token (Lambda `registrar-asistencia`):
no basta con comprobar que el `sessionId` existe. Siempre hay que comparar
`expiresAt` con la hora actual (`int(time.time())`):

- el `sessionId` no existe → 404
- existe pero `expiresAt <= ahora` → 410 (QR expirado)

## Despliegue y borrado limpio del stack (decisiones 7 y 8)

El criterio de aceptación pide que el stack se despliegue y se elimine **sin
pasos manuales**. Hay dos recursos que no pueden vivir dentro de CloudFormation
y se gestionan con los scripts `deploy.sh` / `destroy.sh`:

### Bucket de artefactos (fuera del stack)
`aws cloudformation package` sube el código empaquetado de las Lambdas a un
bucket S3 **antes** de crear el stack. Ese bucket no puede ser parte del stack
que lo necesita para desplegarse (problema del huevo y la gallina). Por eso:

- `deploy.sh` lo crea si no existe (`gtn-<equipo>-artifacts-<cuenta>`).
- `destroy.sh` lo vacía y lo borra al final del teardown.

### Bucket web: autovaciado en el borrado
CloudFormation no borra un bucket S3 que contenga objetos (falla con
`BucketNotEmpty`). Como el bucket web se puebla con `aws s3 sync`, se añadió un
**custom resource** (`VaciarBucketWeb`) respaldado por una Lambda que vacía el
bucket cuando el stack se borra. Así `delete-stack` limpia todo solo. La Lambda
usa el módulo `cfnresponse` (disponible automáticamente al usar `Code: ZipFile`
inline) y su costo es despreciable: solo se ejecuta en operaciones de
CloudFormation, no en el uso normal de la app.

### Hallazgo: LogGroup huérfano de la Lambda de autovaciado
La Lambda de autovaciado **escribe logs mientras el stack se está borrando**.
AWS Lambda recrea su LogGroup justo después de que CloudFormation lo elimina, lo
que deja un LogGroup huérfano. Si ese LogGroup se declara en la plantilla, el
siguiente `deploy` falla en la validación temprana
(`AWS::EarlyValidation::ResourceExistenceCheck`: "el recurso ya existe").

**Solución adoptada** (verificada con un ciclo real deploy → destroy → redeploy
en AWS): no declarar el LogGroup de esa Lambda en CloudFormation (dejar que
Lambda lo gestione) y borrarlo en `destroy.sh`. Los LogGroups de
`crear-sesion` y `registrar-asistencia` sí se gestionan en la plantilla, porque
esas Lambdas no se ejecutan durante el borrado y no recrean nada.

> Limitación conocida: el `destroy.sh` espera unos segundos (`sleep`) antes de
> borrar ese LogGroup para atajar la condición de carrera con la escritura de la
> Lambda. No está garantizado al 100%; si reaparece, es un residuo inofensivo
> (no rompe el redeploy ni tiene costo relevante).

## Riesgo documentado: rol `LabRole` (decisión 3)

El acuerdo del equipo pide mínimo privilegio (un rol por Lambda). En AWS Academy
Learner Lab **no se pueden crear roles IAM**, así que todas las Lambdas usan el
rol compartido `LabRole`, que es permisivo. Es una limitación del entorno, no
una elección de diseño. Si el entorno final permite crear roles, se debe migrar
a un rol por Lambda con permisos acotados a sus tablas y buckets.
