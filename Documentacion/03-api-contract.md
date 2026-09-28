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
| 5 | GET | `/api/auth/me` | Bearer | `UserResponse` |
| 6 | GET | `/api/establishments` | Bearer | `EstablishmentListResponse` |
| 7 | GET | `/api/establishments/{rbd}` | Bearer | `Establishment` |
| 8 | PUT | `/api/establishments/{rbd}` | Bearer | `Establishment` |
| 9 | GET | `/api/counterparts/establishment/{rbd}` | Bearer | `Counterpart[]` |
| 10 | POST | `/api/counterparts` | Bearer | `Counterpart` (201) |
| 11 | PUT | `/api/counterparts/{cp_id}` | Bearer | `Counterpart` |
| 12 | DELETE | `/api/counterparts/{cp_id}` | Bearer | `{message}` |
| 13 | GET | `/api/metrics/establishment/{rbd}` | Bearer | `Metric[]` |
| 14 | GET | `/api/metrics/establishment/{rbd}/{year}` | Bearer | `Metric` |
| 15 | PUT | `/api/metrics/establishment/{rbd}/{year}` | Bearer | `Metric` |
| 16 | GET | `/api/analytics/kpis` | Bearer | objeto de KPIs |
| 17 | GET | `/api/analytics/charts` | Bearer | objeto de series |

Más los tres endpoints que FastAPI monta solo: `/docs`, `/redoc`, `/openapi.json`.

> ⚠️ **Contradice el plan histórico.** `historico/implementation_plan_iter1.md` §5 documenta
> `/api/counterparts/{rbd}` y `/api/metrics/{rbd}`. Las rutas reales llevan el segmento
> `/establishment/` intercalado. El plan es intención, no estado — esta tabla es la verdad.

---

## 2. Autenticación

Esquema: **JWT Bearer**, HS256, sin refresh. Detalle del flujo y del modelo de roles en
`04-seguridad-y-acceso.md`; aquí solo lo que el cliente necesita.

```
POST /api/auth/login
Content-Type: application/json

{"username": "admin", "password": "..."}
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

`POST /api/auth/logout` **no invalida nada**: el JWT es stateless y no hay lista de revocación.
Devuelve `{"message": "Successfully logged out"}` y es el cliente quien debe descartar el token.
La ruta ni siquiera exige autenticación.

> 🔸 **BRECHA:** no existe autenticación de máquina a máquina. Un consumidor externo debe usar
> credenciales de un usuario humano de la colección `users`. Sin API keys, sin client
> credentials, sin scopes.
>
> 🔸 **BRECHA:** sin revocación ni refresh, un token filtrado es válido hasta 3 horas y no hay
> forma de cortarlo salvo rotar `JWT_SECRET`, lo que invalida las sesiones de todos.

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
Pública. Body `LoginRequest {username: str, password: str}` (JSON). `200` → `Token {access_token, token_type: "bearer"}`. `401` credenciales inválidas. `422` body mal formado.

### 5.3 `POST /api/auth/login-form`
Idéntico, body `application/x-www-form-urlencoded`. Existe solo para Swagger UI.

### 5.4 `POST /api/auth/logout`
Pública, sin efecto de servidor. `200` → `{"message": "Successfully logged out"}`.

### 5.5 `GET /api/auth/me`
Bearer. `200` → `UserResponse {username, full_name, role}`. `401` token inválido/expirado.
El frontend lo usa al montar para rehidratar la sesión desde el token de `localStorage` (`App.jsx:48`).

> 🔸 **BRECHA:** `current_user["full_name"]` se accede por índice, no con `.get()`
> (`auth_controller.py:58`). Un usuario insertado a mano sin `full_name` produce `KeyError` → 500.

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
Bearer (**cualquier autenticado, no solo admin**). Body `EstablishmentUpdate`: todos los campos
opcionales; `rbd`, `rbd_dv` y `rbd_full` **no** son modificables.
`200` → `Establishment` actualizado **con los campos sensibles sin redactar** —
`update_by_rbd` invoca `find_by_rbd(include_sensitive=True)` (`establishments_service.py:110,118`).
`400` si no se pudo actualizar.

> 🔸 **BRECHA (fuga por escritura):** un usuario `viewer` que emita un PUT recibe en la respuesta
> las contraseñas en claro que el GET le habría redactado. La redacción protege la lectura pero
> no el retorno de la escritura. Es el vacío más directo entre BE-05 y el comportamiento real,
> y no está cubierto por ningún test.
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
