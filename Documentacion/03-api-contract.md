# 03 · Contrato de la API REST

> **Alcance.** Todo lo que un cliente necesita para integrarse contra este backend sin leer
> su código: endpoints, formas de request y response, convenciones transversales y política
> de evolución. Documento autocontenido para un consumidor externo.
>
> **Dos registros distintos conviven aquí.** Lo que el código hace hoy, verificado archivo por
> archivo, y lo que este documento declara **normativo** para la evolución del contrato. Donde
> el código no cumple la norma se marca `🔸 BRECHA`. Ninguna brecha fue corregida: son un
> registro, no un plan.
>
> **Verificado contra:** `backend/app/main.py` y los cinco `*_controller.py` / `*_entity.py`.

---

## 1. Resumen

Base: `/api`. Sin versionado en la ruta. Servidor documentado en `main.py:27-31` como
`version="1.0.0"` (metadato de OpenAPI, no de ruta).

| # | Método | Ruta | Auth | Respuesta |
|---|---|---|---|---|
| 1 | GET | `/` | pública | `{app, status, message}` |
| 2 | POST | `/api/auth/login` | pública | `Token` |
| 3 | POST | `/api/auth/login-form` | pública | `Token` |
| 4 | POST | `/api/auth/logout` | pública | `{message}` |
| 5 | GET | `/api/auth/me` | autenticado | `UserResponse` (ver §5.5) |
| 6 | GET | `/api/establishments` | `datos`: admin, editor, viewer | `EstablishmentListResponse` |
| 7 | GET | `/api/establishments/{rbd}` | `datos`: admin, editor, viewer | `Establishment` |
| 8 | PUT | `/api/establishments/{rbd}` | `datos`: admin, editor | `Establishment` |
| 9 | GET | `/api/counterparts/establishment/{rbd}` | `datos`: admin, editor, viewer | `Counterpart[]` |
| 10 | POST | `/api/counterparts` | `datos`: admin, editor | `Counterpart` (201) |
| 11 | PUT | `/api/counterparts/{cp_id}` | `datos`: admin, editor | `Counterpart` |
| 12 | DELETE | `/api/counterparts/{cp_id}` | `datos`: admin | `{message}` |
| 13 | GET | `/api/metrics/establishment/{rbd}` | `datos`: admin, editor, viewer | `Metric[]` |
| 14 | GET | `/api/metrics/establishment/{rbd}/{year}` | `datos`: admin, editor, viewer | `Metric` |
| 15 | PUT | `/api/metrics/establishment/{rbd}/{year}` | `datos`: admin, editor | `Metric` |
| 16 | GET | `/api/analytics/kpis` | `datos`: admin, editor, viewer | objeto de KPIs |
| 17 | GET | `/api/analytics/charts` | `datos`: admin, editor, viewer | objeto de series |

Más los tres endpoints que FastAPI monta solo: `/docs`, `/redoc`, `/openapi.json`.

**Estado tras F3 (2026-10-02).** La columna *Auth* de arriba es la que rige hoy: los 12 endpoints de
datos exigen un rol en la plataforma `datos` (`viewer` solo lee, `editor` escribe, solo `admin`
borra; `403` si falta, `401` sin sesión válida). Además existen, implementados, los endpoints
de la feature de usuarios marcados ✅ en §8 (auth: `password-policy` y `password`; `users`; `units`;
`platforms`). Lo marcado 🧭 en §8 sigue sin implementar.

> ⚠️ **Contradice el plan histórico.** `historico/implementation_plan_iter1.md` §5 documenta
> `/api/counterparts/{rbd}` y `/api/metrics/{rbd}`. Las rutas reales llevan el segmento
> `/establishment/` intercalado. El plan es intención, no estado — esta tabla es la verdad.

---

## 2. Autenticación

Esquema: **JWT Bearer**, HS256, sin refresh. El `sub` es `str(_id)` del usuario y el token lleva `iat`. Detalle del flujo y del modelo de roles en
`04-seguridad-y-acceso.md`; aquí solo lo que el cliente necesita.

```
POST /api/auth/login
Content-Type: application/json

{"username": "admin@slepllanquihue.cl", "password": "..."}
```

```json
{"access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer"}
```

Las peticiones posteriores llevan `Authorization: Bearer <access_token>`. El token expira a
los `ACCESS_TOKEN_EXPIRE_MINUTES` (default **180**, `config.py:11`). No hay endpoint de
refresh: al expirar hay que volver a autenticarse.

`POST /api/auth/login-form` hace exactamente lo mismo pero acepta
`application/x-www-form-urlencoded` con campos `username`/`password`. Existe para que el
"Authorize" de Swagger UI funcione (`oauth2_scheme` apunta a `tokenUrl="/api/auth/login"`,
`auth_service.py:11`). **Un cliente propio debe usar `/login`, no `/login-form`.**

`username` acepta el **correo** (se normaliza: minúsculas y sin espacios) o, mientras dure la
compatibilidad, el username legado del admin sembrado. Un usuario `invited` o `disabled` recibe
el mismo `401` que una credencial errónea.

`POST /api/auth/logout` **no invalida nada**: el JWT es stateless y no hay lista de revocación.
Devuelve `{"message": "Successfully logged out"}` y es el cliente quien debe descartar el token.
La ruta ni siquiera exige autenticación.

> 🔸 **BRECHA:** no existe autenticación de máquina a máquina. Un consumidor externo debe usar
> credenciales de un usuario humano de la colección `users`. Sin API keys, sin client
> credentials, sin scopes.
>
> ✅ **Revocación parcial (F3):** desactivar a un usuario, quitarle el acceso o cambiarle la
> contraseña corta sus sesiones en la siguiente petición (se relee el usuario y se compara `iat`
> con `password_changed_at`). `logout` sigue sin invalidar el token en el servidor.
>
> 🔸 **BRECHA:** sigue sin haber refresh; un token filtrado es válido hasta su `exp` (3 h) salvo
> que se desactive al usuario o se cambie su contraseña.

---

## 3. Convenciones transversales

Esta sección es **normativa**. Define lo que un cliente puede asumir y lo que la evolución del
backend debe respetar.

### 3.1 Versionado

**Norma:** toda ruta pública vive bajo `/api/v{N}/`. `N` se incrementa solo ante un cambio
*breaking* según §4. Dentro de una versión el contrato solo puede crecer. Dos versiones
mayores conviven durante el período de deprecación.

> 🔸 **BRECHA:** no hay versionado. Todas las rutas están en `/api/` y los prefijos se declaran
> en cada `APIRouter(prefix="/api/...")`. Introducir `/api/v1` requiere tocar los cinco
> controllers y las ~14 llamadas del frontend. Cuanto más tarde, más caro. Nótese que el
> `version="1.0.0"` de `main.py:30` solo aparece en el JSON de OpenAPI: un cliente no puede
> saber por la URL contra qué contrato habla.

### 3.2 Paginación

**Norma:** todo endpoint de colección pagina en el servidor, acepta `page` (1-indexado) y
`page_size`, y devuelve un sobre uniforme con metadatos.

**Implementado en el endpoint #6**, verificado por `test_BE04_server_side_pagination`:

| Parámetro | Tipo | Default | Validación | Origen |
|---|---|---|---|---|
| `page` | int | `1` | `ge=1` | `establishments_controller.py:20` |
| `page_size` | int | `100` | `ge=1, le=200` | `establishments_controller.py:21` |

Sobre de respuesta (`EstablishmentListResponse`):

```json
{
  "items": [ /* EstablishmentSummary */ ],
  "total": 78,
  "page": 1,
  "page_size": 100,
  "total_pages": 1
}
```

Garantías: `skip = (page - 1) * page_size` (`establishments_service.py:61`);
`total_pages = ceil(total / page_size)`, y **`1` cuando `total` es 0**, nunca 0
(`:81`); `total` es el conteo con filtros aplicados, no el total absoluto. El orden es
siempre `name` ascendente (`:64`) y no es configurable.

> 🔸 **BRECHA:** los endpoints #9 (contrapartes) y #13 (métricas históricas) devuelven un
> **array desnudo**, sin paginar ni envolver. Son colecciones acotadas por establecimiento
> (≲15 y ≲5 elementos), pero rompen la uniformidad: un cliente genérico no puede tratar todas
> las colecciones igual. Un endpoint transversal de contrapartes (§7) sí necesitaría paginar.
>
> 🔸 **BRECHA:** no hay parámetro de ordenamiento. El orden por `name` está hardcodeado.

### 3.3 Forma canónica del error

**Norma:** todo error devuelve un cuerpo con la misma forma, con un código de dominio estable
que el cliente pueda ramificar sin parsear texto, y **nunca** incluye rastros de pila, nombres
de colección, cadenas de conexión, credenciales ni valores de campos sensibles.

**Implementado:** el formato por defecto de FastAPI, sin manejador de excepciones propio.

```json
{"detail": "Establishment with RBD 9999 not found"}
```

Para errores de validación de Pydantic (422) el `detail` es en cambio una **lista de objetos**:

```json
{"detail": [{"type": "int_parsing", "loc": ["path", "year"], "msg": "...", "input": "abc"}]}
```

Es decir: `detail` es `string` o `array` según el tipo de error. Un cliente debe contemplar
ambos.

Códigos HTTP realmente emitidos por el código de aplicación:

| Código | Cuándo | Dónde |
|---|---|---|
| `200` | Éxito en GET, PUT, DELETE | todos |
| `201` | Contraparte creada | `counterparts_controller.py:16` |
| `400` | El PUT de establecimiento no pudo aplicarse | `establishments_controller.py:58` |
| `401` | Credenciales inválidas; token ausente, inválido o expirado; usuario del token inexistente | `auth_controller.py:18,37`; `auth_service.py:43-47` |
| `404` | RBD, `cp_id` o `(rbd, year)` inexistente | controllers de establishments, counterparts, metrics |
| `422` | Validación de Pydantic sobre path/query/body | automático de FastAPI |
| `500` | Excepción no capturada | automático |

Los `401` de autenticación incluyen la cabecera `WWW-Authenticate: Bearer`.

> 🔸 **BRECHA:** no hay código de error de dominio. `{"detail": "..."}` con texto libre en
> español-inglés mezclado obliga a un cliente a ramificar por código HTTP o por substring.
>
> 🔸 **BRECHA:** los mensajes reproducen el identificador recibido (`f"Establishment with RBD {rbd} not found"`).
> Es inocuo con un RBD, pero establece un patrón: un mensaje que incluyera un valor de campo
> sensible violaría la norma sin que nada lo impida.
>
> 🔸 **BRECHA:** no hay manejador global de excepciones. Una excepción no prevista (por ejemplo
> un `cp_id` que no es un ObjectId válido: `ObjectId(cp_id)` en `counterparts_service.py:27`
> lanza `bson.errors.InvalidId`) produce un **500** en vez del `400`/`422` que correspondería.

### 3.4 Filtrado y búsqueda

Solo el endpoint #6 filtra. Todos los parámetros son query params opcionales; se combinan con
**AND**; omitirlos significa "sin filtrar".

| Parámetro | Semántica implementada | Origen |
|---|---|---|
| `search` | Si es **solo dígitos**: prefijo de `rbd` (`^{valor}`). Si no: substring case-insensitive sobre `name` OR `rbd` OR `comuna` | `establishments_service.py:35-43` |
| `comuna` | Igualdad exacta, case-insensitive (`^valor$`) | `:46` |
| `area_type` | Igualdad exacta, case-insensitive | `:49` |
| `category` | **Igualdad literal exacta**, sin regex | `:52` |
| `coverage` | Prefijo, case-insensitive (`^valor`) | `:55` |
| `adp` | Igualdad exacta, case-insensitive | `:58` |

La asimetría de `category` es intencional y está comentada en el código
(`establishments_service.py:50`): los valores de categoría contienen paréntesis
(`"5. ESCUELA BÁSICA (CURSO COMBINADO)"`) que un `$regex` interpretaría como grupo de captura.
Se resolvió con comparación directa en vez de escapar el valor.

> 🔸 **BRECHA (inyección de regex):** `search`, `comuna`, `area_type`, `coverage` y `adp` se
> interpolan **sin escapar** dentro de un `$regex`. Un valor como `(a+)+$` es un patrón
> catastróficamente backtracking: una petición autenticada puede bloquear un worker (ReDoS).
> A 78 documentos el impacto es acotado, pero es una superficie real y la mitigación estándar
> es `re.escape()` sobre el valor antes de construir el patrón.
>
> 🔸 **BRECHA:** `search` con `$regex` sin ancla no puede aprovechar el índice sobre `name`:
> es un collection scan. Correcto a esta escala; el reemplazo natural es un índice de texto
> (`$text`) o Atlas Search.

### 3.5 Semántica por verbo

| Verbo | Semántica en esta API | Idempotente |
|---|---|---|
| `GET` | Lectura pura, sin efectos | Sí |
| `POST` | `/api/auth/login`: no crea recurso. `/api/counterparts`: crea, devuelve 201 con `_id` | **No** |
| `PUT` | **Actualización parcial con upsert en métricas.** Ver abajo | Sí |
| `DELETE` | Borra la contraparte | Sí en efecto (segundo intento → 404) |

**`PUT` no es un reemplazo completo**, pese al verbo. Los tres PUT aceptan un body con todos
los campos opcionales y aplican solo los presentes. `establishments_service.py:99` filtra los
`None` antes de construir el `$set`. Semánticamente es un `PATCH`.

**Los PUT devuelven el documento completo actualizado**, no un acuse. Es un invariante con test
dedicado (`test_BE07_put_returns_updated_document`) y su razón es del lado cliente: permite al
frontend refrescar su estado con la respuesta en vez de re-consultar o esperar con un
temporizador. **Quien cambie un PUT para devolver `{"ok": true}` rompe ese test y la UI.**

Matiz importante del `$set` parcial: el filtrado de `None` es de **primer nivel**. Enviar
`{"connectivity": {"ssid": "NuevaRed"}}` reemplaza el objeto `connectivity` **entero** — el
resto de sus campos se pierden. Para editar un subcampo hay que enviar el bloque completo. El
frontend lo hace así (`EditFicha.jsx:175` envía el objeto completo).

**`PUT /api/metrics/establishment/{rbd}/{year}` es un upsert** (`metrics_service.py:36`): si no
existe el registro de ese año, lo crea. MongoDB añade `rbd` y `year` al documento nuevo desde
el filtro de igualdad. Es el único endpoint que crea por PUT.

> 🔸 **BRECHA:** el upsert de métricas con un body **vacío** produce un `$set` vacío, que pymongo
> rechaza lanzando excepción → 500. No hay guarda (compárese con `establishments_service.py:109`
> y `counterparts_service.py:23`, que sí la tienen).
>
> 🔸 **BRECHA:** `PUT /api/metrics/.../{year}` no valida el rango de `year`. Un año 1800 o 9999
> crea un documento válido.
>
> 🔸 **BRECHA:** `DELETE /api/counterparts/{id}` devuelve `{"message": "Counterpart deleted successfully"}`.
> El docstring de `test_BE07` declara `{message, deleted_id}`. La aserción del test no lo cubre,
> así que la divergencia no rompe nada — pero la intención documentada y el código no coinciden.

### 3.6 Modelo interno vs modelo público

Tres mecanismos, en este orden, deciden qué campo cruza la frontera HTTP:

1. **Proyección MongoDB** — `LISTING_PROJECTION` (`establishments_service.py:6-17`) decide qué
   se lee del disco en el listado. Lo no proyectado no existe aguas abajo.
2. **Redacción por rol** — `find_by_rbd(include_sensitive=...)` sustituye por `[REDACTED]`.
3. **`response_model`** — Pydantic **descarta en silencio** cualquier campo del dict que el
   modelo no declare. Es el filtro final y el más fácil de olvidar.

Consecuencia operativa, y la causa más común de "agregué el campo y no aparece":
un campo nuevo en MongoDB no llega al cliente hasta declararlo en el modelo de respuesta;
en el listado, además, hay que agregarlo a la proyección **y** al aplanamiento manual.

| Campo interno | Público | Dónde se decide |
|---|---|---|
| `_id` (establecimiento) | **No** | El service lo stringifica, pero `Establishment` no lo declara |
| `_id` (contraparte/métrica) | **Sí, como `_id`** | `Field(alias="_id")` + `populate_by_name` |
| `licenses` | Solo en detalle | Fuera de `LISTING_PROJECTION` |
| `licenses[].password` | Solo admin | Redacción |
| `connectivity.ssid_password` | Solo admin | Redacción |
| `users.hashed_password` | **Nunca** | `UserResponse` solo declara 3 campos |
| `general_info.*` | Detalle completo; en el listado solo `category`, `adp`, `covertura`, **aplanados** | Proyección + `EstablishmentSummary` |

### 3.7 OpenAPI

FastAPI genera la especificación automáticamente desde los modelos y decoradores. Disponible en:

- `GET /openapi.json` — especificación OpenAPI 3.1
- `GET /docs` — Swagger UI
- `GET /redoc` — ReDoc

Los tres son **públicos**: no pasan por `get_current_user`.

Calidad actual del documento generado: los endpoints de establishments tienen `description`
por parámetro (`establishments_controller.py:14-21`) y todos tienen `response_model` salvo los
de analytics. Faltan `summary`/`description` a nivel de operación, ejemplos, y la declaración
de las respuestas de error (el 404 que un endpoint puede emitir no aparece en el esquema).

Para publicarla como contrato formal faltaría: fijar un `servers` explícito, declarar
`responses={404: ...}` por operación, versionar la ruta (§3.1), tipar las respuestas de
analytics (§7), y decidir si `/openapi.json` debe seguir siendo público.

---

## 4. Política de evolución del contrato

**Norma.** Un cambio es *breaking* si un cliente correcto que funcionaba deja de funcionar.

**No-breaking** — entran en la versión vigente:

- Agregar un campo **opcional** a un modelo de respuesta (ej. `location` en `EstablishmentSummary`).
- Agregar un campo **opcional** a un body de request.
- Agregar un endpoint nuevo.
- Agregar un valor a `CounterpartRole`. *(Ojo: es no-breaking para el servidor, pero rompe a un
  cliente que haga exhaustividad sobre el enum. Un enum de salida es un contrato: documentar la
  ampliación.)*
- Agregar un query param opcional con default que preserve el comportamiento actual.
- Relajar una validación (subir `le=200` a `le=500` en `page_size`).

**Breaking** — exigen versión nueva:

- Eliminar o renombrar cualquier campo de respuesta.
- Cambiar el tipo de un campo. **El caso canónico de este dominio: `rbd` es `str`.** Pasarlo a
  `int` rompe todo cliente que lo compare, lo concatene o lo use como clave de diccionario, y
  además invalida el índice único y las referencias de `counterparts` y `metrics`.
- Volver requerido un campo antes opcional del request.
- Cambiar el significado de un campo sin cambiar su nombre (el peor, porque no falla: si
  `attendance_avg` pasara de `"92%"` a `0.92`, todo cliente seguiría "funcionando" y mostraría
  un dato falso).
- Endurecer una validación (bajar el `le` de `page_size`).
- Cambiar un código HTTP (404 → 204 en un recurso ausente).
- Cambiar la forma del sobre de paginación.
- Cambiar el orden por defecto del listado, si un cliente paginaba asumiéndolo estable.

**Procedimiento de deprecación (norma):** anunciar en el `description` de la operación y en
este documento → emitir cabecera `Deprecation` y `Sunset` en las respuestas de la operación →
convivencia de `v{N}` y `v{N+1}` por al menos un ciclo de despliegue completo → retirar.

> 🔸 **BRECHA:** sin `/api/v1` (§3.1) no hay dónde alojar la versión nueva, así que hoy la
> política es inaplicable: todo cambio breaking es un corte duro coordinado con el frontend.
> Es la brecha de mayor consecuencia de este documento.

---

## 5. Referencia por endpoint

### 5.1 `GET /` — estado del servicio
Pública. `200` → `{"app": "SLEP Llanquihue - Gestión de Establecimientos", "status": "online", "message": "..."}`.
Usada como healthcheck en `Dockerfile.prod` y `docker-compose.prod.yml`. No reporta el estado de MongoDB.

> 🔸 **BRECHA:** el healthcheck devuelve `online` aunque la conexión a MongoDB esté caída,
> porque no la consulta. Un backend sin base pasaría el healthcheck y Nginx lo consideraría sano.

### 5.2 `POST /api/auth/login`
Pública. Body `LoginRequest {username: str, password: str}` (JSON, solo escalares: un objeto de operadores da `422`). `200` → `Token {access_token, token_type: "bearer"}`. `401` credenciales inválidas o usuario no activo. `422` body mal formado.

### 5.3 `POST /api/auth/login-form`
Idéntico, body `application/x-www-form-urlencoded`. Existe solo para Swagger UI.

### 5.4 `POST /api/auth/logout`
Pública, sin efecto de servidor. `200` → `{"message": "Successfully logged out"}`.

### 5.5 `GET /api/auth/me`
Autenticado (cualquier rol, incluso sin acceso a `datos`). `200` → `UserResponse`:

```json
{"username": "admin@slepllanquihue.cl", "full_name": "Administrador SLEP", "role": "admin",
 "id": "66…", "email": "admin@slepllanquihue.cl",
 "access": [{"platform_id": "iam", "role": "admin"}, {"platform_id": "datos", "role": "admin"}]}
```

`username`, `full_name` y `role` son el contrato original. **`role` es el rol en `datos`, o
`"none"` si el usuario no tiene acceso a esa plataforma.** `id`, `email` y `access` son aditivos
(F3). `401` token inválido/expirado, usuario no activo o sesión anterior a un cambio de contraseña.
El frontend lo usa al montar para rehidratar la sesión (`App.jsx:48`).

### 5.6 `GET /api/establishments`
Bearer. Query: `search`, `comuna`, `area_type`, `category`, `coverage`, `adp` (§3.4) + `page`, `page_size` (§3.2).
`200` → `EstablishmentListResponse`. Cada ítem es un `EstablishmentSummary`:

```json
{"rbd":"7722","rbd_full":"7722","name":"LICEO ...","comuna":"PUERTO VARAS",
 "area_type":"URBANO","address":"...","category":"7. LICEO POLITÉCNICO","adp":"Si","covertura":"MEDIA"}
```

**Garantía de seguridad (INT-02):** este endpoint nunca incluye `licenses`, `connectivity` ni
`printers`, para ningún rol. Verificado por `test_INT02_listing_response_never_contains_licenses_field`.

### 5.7 `GET /api/establishments/{rbd}`
Bearer. `200` → `Establishment` completo (esquema en `02-modelo-datos.md` §3).
`404` si el RBD no existe. **La respuesta depende del rol**: para no-admin,
`licenses[].password` y `connectivity.ssid_password` valen `"[REDACTED]"`.

### 5.8 `PUT /api/establishments/{rbd}`
`datos`: admin o editor (`viewer` recibe `403`). Body `EstablishmentUpdate`: todos los campos
opcionales; `rbd`, `rbd_dv` y `rbd_full` **no** son modificables.
`200` → `Establishment` actualizado; las credenciales van en claro porque solo `admin` y `editor`
pueden llegar aquí (C20), y el controller pasa `include_sensitive` explícito al service.
`422` si un secreto llega como `"[REDACTED]"` y no hay valor almacenado equivalente (misma
posición y mismo `name` en las licencias). Si hay uno equivalente se conserva y la edición
funciona. `400` si no se pudo actualizar.

> ✅ **RESUELTO (D4):** la fuga por escritura está cerrada (el `viewer` no puede escribir) y cubierta por `test_INT04_*`.

>
> 🔸 **BRECHA:** `update_by_rbd` devuelve el documento incluso cuando `matched_count == 0`
> solo si el `$set` quedó vacío (`:109-110`), y en el camino normal comprueba
> `modified_count > 0 or matched_count > 0` (`:117`) — un RBD inexistente da ambos en 0 y
> retorna `None` → `400`. Un RBD inexistente debería ser `404`, no `400`.

### 5.9 `GET /api/counterparts/establishment/{rbd}`
Bearer. `200` → array de `Counterpart` (con `_id` string). Array vacío si no hay ninguna.
**Nunca 404.**

### 5.10 `POST /api/counterparts`
Bearer. Body `CounterpartCreate {rbd, role, origin, name, email?, phone?}` — `role` y `origin`
validados contra sus enums (valor fuera del enum → `422`). `201` → `Counterpart` con `_id`.
Sin validación de que el `rbd` exista ni de duplicados (`02-modelo-datos.md` §3.4).

### 5.11 `PUT /api/counterparts/{cp_id}`
Bearer. `cp_id` es el `_id` de MongoDB como string. Body `CounterpartUpdate`: `name`, `email`,
`phone`, `role`, `origin`, todos opcionales. **`rbd` no es modificable.** `200` → `Counterpart`
actualizada. `404` si no existe. `500` si `cp_id` no es un ObjectId válido (§3.3).

### 5.12 `DELETE /api/counterparts/{cp_id}`
Bearer. `200` → `{"message": "Counterpart deleted successfully"}`. `404` si no existe.

### 5.13 `GET /api/metrics/establishment/{rbd}`
Bearer. `200` → array de `Metric` **ordenado por `year` ascendente** (`metrics_service.py:8`).
Array vacío si no hay. Recuérdese que los años previos a 2026 vienen con la mayoría de los
campos en su valor por defecto (`02-modelo-datos.md` §5).

### 5.14 `GET /api/metrics/establishment/{rbd}/{year}`
Bearer. `year` es `int` en el path (no numérico → `422`). `200` → `Metric`. `404` si no existe
ese par.

### 5.15 `PUT /api/metrics/establishment/{rbd}/{year}`
Bearer. Body `MetricUpdate`, todos opcionales. **Upsert.** `200` → `Metric` resultante.
No emite 404: si no existía, lo crea.

### 5.16 `GET /api/analytics/kpis`
Bearer. `200` →

```json
{"total_establishments": 78, "total_enrollment_2026": 0, "total_enrollment_2025": 0,
 "total_teachers_2026": 0, "total_communes": 5}
```

**El año 2026 está hardcodeado** en el pipeline (`analytics_service.py:10` y `:26`). En 2027 este
endpoint seguirá informando 2026 hasta que alguien edite el código.

### 5.17 `GET /api/analytics/charts`
Bearer. `200` → cuatro series, cada una un array de `{label, value}`:

```json
{"enrollment_by_area": [{"label":"URBANO","value":0}],
 "enrollment_by_commune": [...], "establishments_by_category": [...],
 "establishments_by_connectivity": [...]}
```

`enrollment_by_area` y `enrollment_by_commune` usan `$lookup` de `metrics` contra
`establishments` filtrando `year: 2026` (mismo hardcode). `establishments_by_category` limpia
el prefijo numérico de la categoría (`"7. LICEO" → "LICEO"`, `:111-114`) — **esa limpieza vive
solo aquí**, no en el modelo, así que el `category` del listado sí trae el prefijo y el del
gráfico no. `establishments_by_connectivity` etiqueta los nulos como `"Sin Conexión"`.

> 🔸 **BRECHA:** los endpoints de analytics **no tienen `response_model`**
> (`analytics_controller.py:7,11`). Devuelven un dict libre, así que no aparecen tipados en
> OpenAPI y nada impide que un cambio en el service altere la forma sin aviso. Son los dos
> únicos endpoints sin contrato declarado.
>
> 🔸 **BRECHA:** el año de referencia hardcodeado (2026, en
> `analytics_service.py:10,48,74`) es el acoplamiento temporal más concreto del backend.
> El diseño correcto es un query param `year` con default calculado, no una constante en el
> código.

---

## 6. Ejemplo de integración externa

```bash
BASE=https://<host>/api

TOKEN=$(curl -sS -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"USUARIO","password":"CLAVE"}' | jq -r .access_token)

# Directorio filtrado y paginado
curl -sS "$BASE/establishments?comuna=FRUTILLAR&area_type=RURAL&page=1&page_size=50" \
  -H "Authorization: Bearer $TOKEN"

# Ficha completa
curl -sS "$BASE/establishments/7722" -H "Authorization: Bearer $TOKEN"

# Serie histórica de matrícula
curl -sS "$BASE/metrics/establishment/7722" -H "Authorization: Bearer $TOKEN"
```

Datos ficticios. El token vale 3 horas; al recibir `401` hay que repetir el login.

---

## 7. Capacidades que el contrato no ofrece hoy

Registro de ausencias, no plan de trabajo. Un integrador debe saber que no existen:

- **Endpoint transversal de contrapartes.** `GET /api/counterparts?role=TI` no existe, pese a
  que la consulta transversal es la justificación de diseño de la colección (ADR-002). Solo se
  puede consultar por establecimiento.
- **Endpoint transversal de métricas por año.** El plan histórico documentaba
  `GET /api/metrics?year=2026`; `metrics_service.find_by_year()` está **implementado**
  (`metrics_service.py:22`) pero **ningún controller lo expone**. Código muerto alcanzable.
- **Creación ni borrado de establecimientos.** Solo GET y PUT. Los 78 llegan por seeding.
- **Gestión de usuarios y roles** por API.
- **Analytics parametrizable**: sin filtro por año, comuna o categoría.
- **Rate limiting, cuotas o auditoría** de peticiones.
- **Cabeceras de caché o `ETag`.** Toda respuesta se recalcula.
- **Exportación** (CSV/XLSX), pese a que `pandas` y `openpyxl` figuran en `requirements.txt`.

---

## 8. 🧭 DISEÑO F2: contrato de usuarios, unidades y acceso

> **Estado por ruta (2026-10-02):** ✅ implementada y verificada en F3 · 🧭 diseño aprobado, sin
> implementar. Origen de las decisiones: ADR-009 a ADR-014 (`06`). Modelo de datos en `02` §9;
> matriz de roles en `04` §9. Con D10 (sin versionado), **todo cambio de §8.2 es potencialmente
> breaking y se coordina con el frontend** en la misma fase.

### 8.1 Endpoints nuevos

`Acceso` indica lo que declara `require_access(plataforma, roles)`. «Autenticado» es cualquier
usuario `active`, con o sin acceso a `datos`. Las rutas fijas (`/me`, `/bulk`, `/import`) se
declaran **antes** de `/{id}` para que no las capture.

**`/api/auth`** (módulo `auth`)

| Método | Ruta | Acceso | Respuesta |
|---|---|---|---|
| POST | `/api/auth/google` 🧭 F6 | pública | `Token` (verifica el `id_token`; sin auto-provisión) |
| GET | `/api/auth/config` 🧭 F6 | pública | `{google_client_id}` (el frontend no tiene variables de entorno, ADR-008) |
| GET | `/api/auth/password-policy` ✅ | pública | `{min_length, max_length, require_char_classes}` |
| POST | `/api/auth/set-password` 🧭 F4 | pública | `204` (canje del enlace; mismo error genérico `400` ante token usado, vencido o inexistente) |
| POST | `/api/auth/password` ✅ | autenticado | `Token` nuevo (cambio de contraseña propia) |

**`/api/users`** (módulo `users`; todo `iam/admin` salvo `/me`)

| Método | Ruta | Acceso | Respuesta |
|---|---|---|---|
| GET | `/api/users/me` ✅ | autenticado | `UserMe` (incluye su propio `personal_phone`) |
| PATCH | `/api/users/me` ✅ | autenticado | `UserMe` (solo `personal_phone` y `work_extension`; otro campo → `422`) |
| GET | `/api/users` ✅ | `iam/admin` | `UserListResponse` (paginado, filtros) |
| POST | `/api/users` ✅ | `iam/admin` | `201` `User` + `invitation` |
| GET | `/api/users/{id}` ✅ | `iam/admin` | `User` |
| PATCH | `/api/users/{id}` ✅ | `iam/admin` | `User` (no admite `access`, `status` ni `auth_providers`) |
| POST | `/api/users/{id}/disable` · `/enable` ✅ | `iam/admin` | `User` |
| PUT | `/api/users/{id}/access/{platform_id}` ✅ | `iam/admin` | `User` (`{role}`) |
| DELETE | `/api/users/{id}/access/{platform_id}` ✅ | `iam/admin` | `User` |
| POST | `/api/users/{id}/invitation` 🧭 F4 | `iam/admin` | `User` + `invitation` (reenvío; solo `invited`) |
| POST | `/api/users/{id}/password-reset` 🧭 F4 | `iam/admin` | `202` (solo `active`) |
| POST | `/api/users/import` 🧭 F4 | `iam/admin` | `ImportPreview` (CSV multipart → JSON con dry-run; no escribe) |
| GET | `/api/users/import/template` 🧭 F4 | `iam/admin` | `text/csv` con BOM |
| POST | `/api/users/bulk-create` 🧭 F4 | `iam/admin` | `BulkResult` (`dry_run` opcional) |
| POST | `/api/users/bulk` 🧭 F4 | `iam/admin` | `BulkResult` (unión discriminada por `op`) |

No existe `DELETE /api/users/{id}`: eliminar es desactivar (C9).

**Sobre el correo.** No hay endpoint genérico para enviar correos (sería un relay abierto). Los
correos salen como efecto de tres operaciones del admin global: crear un usuario
(`POST /api/users`, `POST /api/users/bulk-create`), reenviar la invitación
(`POST /api/users/{id}/invitation`) y restablecer la contraseña
(`POST /api/users/{id}/password-reset`). Cada una toma el correo del documento del usuario y usa
una plantilla HTML y de texto (ADR-012).

**`/api/units`, `/api/platforms`, `/api/audit`**

| Método | Ruta | Acceso | Respuesta |
|---|---|---|---|
| GET | `/api/units` · `/api/units/tree` · `/api/units/{id}` ✅ | autenticado | `Unit[]` · árbol anidado (`?expand=head` agrega id y nombre a mostrar) |
| POST | `/api/units` ✅ | `iam/admin` | `201` `Unit` |
| PATCH | `/api/units/{id}` ✅ | `iam/admin` | `Unit` (solo `name`, `order`) |
| POST | `/api/units/{id}/move` ✅ | `iam/admin` | `Unit` (reescribe `ancestors` del subárbol) |
| POST | `/api/units/{id}/deactivate` · `/activate` ✅ | `iam/admin` | `Unit` |
| PUT | `/api/units/{id}/head` ✅ | `iam/admin` | `Unit` (`{user_id}` o `null`) |
| POST | `/api/units/{id}/subrogations` · GET igual ruta 🧭 F4 | `iam/admin` · autenticado | `201` `Subrogation` · lista (Could) |
| POST | `/api/units/subrogations/{sid}/cancel` 🧭 F4 | `iam/admin` | `Subrogation` (Could) |
| GET | `/api/platforms` ✅ | `iam/admin` | `Platform[]` |
| PATCH | `/api/platforms/{id}` ✅ | `iam/admin` | `Platform` (solo `name`, `status`) |
| GET | `/api/audit` 🧭 F4 | `iam/admin` | paginado (`page_size ≤ 200`) |

### 8.2 Cambios a endpoints existentes (✅ todos implementados en F3, salvo `user_id` de contrapartes 🧭 F4)

| Endpoint | Cambio | ¿Breaking? |
|---|---|---|
| `GET /api/auth/me` | **Aditivo:** conserva `username`, `full_name`, `role` y agrega `id`, `email` y `access: [{platform_id, role}]`. `role` es el rol en `datos`, o `"none"` si no tiene acceso. | No |
| `POST /api/auth/login` | El campo `username` acepta el correo (normalizado) o el username legado. Un usuario `invited` o `disabled` recibe el mismo `401` que una credencial errónea. El token lleva `sub = str(_id)` e `iat`. | No para clientes que tratan el token como opaco |
| Los 12 endpoints de datos | `Depends(get_current_user)` pasa a `require_access("datos", …)`. **`viewer` recibe `403` en toda escritura; `editor` no puede `DELETE`; quien no tiene acceso a `datos` recibe `403`.** | **Sí, de comportamiento** (intencional: cierra D3 y D4) |
| `PUT /api/establishments/{rbd}` | Un `licenses[].password` o `connectivity.ssid_password` igual a `"[REDACTED]"` conserva el valor almacenado; si no hay valor equivalente → `422`. | No |
| `POST/PUT /api/counterparts` | Campo opcional `user_id` (validado contra `users`). | No |

El token ya no se considera válido si `iat < password_changed_at` del usuario (`04` §9.4). Los
tokens legados con `sub = username` se aceptan mientras dure la compatibilidad.

### 8.3 Convenciones de las rutas nuevas

- **Respuestas de escritura:** devuelven el documento resultante (L9), nunca `{"ok": true}`.
  Los `User` nunca incluyen `hashed_password` ni `token_hash`; `personal_phone` solo lo reciben
  `iam/admin` y el propio usuario.
- **`invitation`** (en todo `User`): `{sent_at, expires_at, last_error, sent}`. `sent` es
  verdadero solo si hay `sent_at` y no hay `last_error`. Mientras no exista el envío de correo (F4)
  un usuario recién creado trae `last_error: "mail_not_configured"` y `sent: false`: se dice la
  verdad en vez de simular un envío. Si el correo falla en F4, el alta igual responde `201`.
- **Errores de las rutas nuevas:** `409` lleva `detail: {code, message, field}` (`field` es el
  campo en conflicto, por ejemplo `email`, para que el formulario lo marque); `422` por una
  referencia o combinación inválida que detecta el service lleva `detail: [{field, code, message}]`
  (la misma forma de lista que usa Pydantic); `404` lleva un texto. Los `code` estables son:
  `duplicate`, `self_disable`, `last_admin`, `level2_no_children`, `invalid_parent_level`,
  `single_root`, `cycle`, `has_active_users`, `has_active_children`, `inactive_parent`,
  `head_inactive`, `head_not_slep_staff`, `head_not_member`, `unit_not_found`, `rbd_not_found`,
  `invalid_role`, `invalid_combination`, `current_password_incorrect`, `no_local_password`.
- **Paginación:** `{items, total, page, page_size, total_pages}`, `page_size ≤ 200`, por defecto 100
  (patrón de §3.2); `total_pages` es 1 cuando no hay resultados. `GET /api/users` filtra por `q` (texto, escapado con `re.escape`), unidad
  (+ `include_descendants`), nivel, tipo, `rbd`, cargo, plataforma, rol, estado y `acting`.
- **Entradas:** todo body y todo query param es un modelo Pydantic de tipos escalares con
  `extra="forbid"`. Un campo desconocido, o un objeto donde se espera un escalar
  (`{"$ne": null}`), responde `422`. `UserAdminUpdate` y `UserSelfUpdate` son tipos distintos.
- **`BulkResult`:**

```json
{"bulk_id": "…", "dry_run": false, "total": 5, "created": 3, "failed": 2,
 "items": [{"index": 0, "status": "created", "id": "…", "errors": [], "invitation": "queued"},
           {"index": 3, "status": "invalid", "errors": [{"field": "email", "code": "duplicate", "message": "…"}]}]}
```

  `status` posibles: `created`, `invalid`, `duplicate`, `ok`, `not_found`, `last_admin`, `self`,
  `mode_mismatch`. El `index` coincide con el número de fila del CSV menos la cabecera.
- **CSV:** `POST /api/users/import` recibe `multipart` (≤ 1 MiB, ≤ 200 filas), decodifica
  `utf-8-sig` y luego `cp1252`, detecta `;` o `,`, y devuelve una **lista** `[{row, data,
  errors}]` que es exactamente el body de `bulk-create`. Columnas: `email`, `first_name`,
  `last_name`, `personal_phone`, `work_extension`, `unit_code`, `rbd`, `positions` (varios valores
  separados por `|`). La unidad se referencia por `code`.
- **Límites:** 200 ítems por lote (CSV, `bulk-create` y `bulk`), una sola constante.
- **Códigos nuevos:** `403` rol insuficiente; `409` violación de regla de negocio o de unicidad
  (correo repetido, último admin, nivel inválido, solapamiento de subrogancia); `413` CSV
  demasiado grande; `429` límite de intentos, con `Retry-After`. Un `ObjectId` inválido en una
  ruta nueva responde `404`/`422`, no `500` (no replica D12).
- **Rutas versionadas:** las rutas nuevas **no** llevan `/v1` (consistente con las 17 actuales y
  con D10). Los endpoints para terceros de F7 sí irán versionados desde el primer día (`04` §10).

### 8.4 Políticas que el contrato no cambia

`response_model` en toda ruta (L7), `Depends` de autenticación en toda ruta no pública (L8, ahora
vía `require_access`), `page_size ≤ 200` y la forma de error de FastAPI (§3.3). Los códigos de
error de dominio siguen siendo una brecha abierta: las rutas nuevas devuelven el `detail` por
defecto, salvo los `errors[].code` de `BulkResult`.
