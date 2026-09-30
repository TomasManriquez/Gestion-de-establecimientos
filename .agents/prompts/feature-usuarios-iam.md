# Prompt · Feature: gestión de usuarios, unidades organizacionales y acceso centralizado (IAM)

> **Uso:** mensaje inicial de una sesión nueva de agente, abierta en la raíz del repositorio.
> **Versión 3.1 (2026-09-30).** La v2 incorporó las respuestas P1 a P12. La v3 incorporó las
> respuestas N1 a N10, el requisito estricto de shadcn para el frontend, el hilo de Stack Overflow
> sobre CSV y el marco de interconexión de la sección 8. La v3.1 cierra N2, N11 y N12. Verificado contra el repo en el commit
> `5b0984e` más los cambios locales sin commitear (`backend/app/database/seed_service.py`,
> `.gitignore`, `CLAUDE.md`, `Documentacion/`).

---

## 0. Tu rol y cómo trabajas

Actúas como ingeniero de software senior en este repositorio. **En esta sesión planificas; no
implementas.** El entregable termina en la Fase 1 (§6). No crees ni modifiques archivos en
`backend/` o `frontend/` hasta que el usuario apruebe la Fase 1 de forma explícita.

Antes de producir nada:

1. Lee `CLAUDE.md` completo. Sus reglas son vinculantes y este prompt no las repite.
2. Lee, en este orden: `Documentacion/00-README.md`; `01-arquitectura.md` §4;
   `02-modelo-datos.md` §2, §6 y §7; `04-seguridad-y-acceso.md` completo;
   `05-guia-de-extension.md` §1, §3 y §5; `06-decisiones-adr.md` ADR-001, 002, 006, 007 y 008.
3. Para todo lo que toque el frontend, lee `.agents/skills/shadcn/SKILL.md` y sus reglas en
   `.agents/skills/shadcn/rules/` (`forms.md`, `composition.md`, `styling.md`, `icons.md`,
   `base-vs-radix.md`). Es un requisito estricto (C15).
4. Comprueba que lo que este prompt afirma sobre el código siga siendo cierto (rutas, líneas,
   nombres, IDs de tests). Si algo no coincide, el código manda: repórtalo como `🔸 BRECHA` y
   sigue adelante.

**Principio rector sobre patrones.** Cada patrón que introduzcas tiene que resolver un problema
concreto que este prompt nombra. Si no puedes decir qué requisito fallaría sin ese patrón, no lo
introduzcas. La arquitectura actual (ADR-007) es simple a propósito, y la feature tiene que
dejarla igual de fácil de leer. La reutilización se logra con **una sola ruta de código por
regla de negocio**, no con capas de abstracción genéricas. Ejemplo ya aplicado en este prompt: el
`ScopeFilter` quedó diferido (C4) porque ningún requisito de esta feature lo necesita.

---

## 1. Decisiones cerradas: no las vuelvas a discutir

Si encuentras evidencia que invalide alguna, detente y muéstrasela al usuario; no la cambies por
tu cuenta.

| # | Decisión | Razón |
|---|---|---|
| C1 | **Se mantiene MongoDB.** Nada de migrar a PostgreSQL ni de sumar un segundo motor en este sistema. | Se reevaluó ADR-001: filtrar datos por unidad es lógica de aplicación en cualquier motor, y migrar invalidaría todos los tests BE/INT, que mockean `db_service.db`. Motivos para reabrir la decisión: reportes habituales que crucen 3 o más colecciones, 2 o más escrituras multi-colección que la regla de negocio exija atómicas, permisos heredados que obliguen a consultas recursivas, o la llegada de un segundo SLEP. |
| C2 | **Identidad ≠ autenticación.** Un módulo nuevo `users` pasa a ser dueño de la colección `users`. `auth` solo verifica credenciales y emite tokens, deja de leer `db.users` directamente y usa `users_service`. | Brecha de `02` §6; límite L5. |
| C3 | Los métodos de autenticación se guardan como un array tipado `auth_providers[]` (`local`, `google`). | Mismo patrón discriminador de ADR-002. |
| C4 | **La autorización se resuelve con una dependencia de FastAPI**, `require_access(platform, roles)`, que en el controller devuelve un `AccessContext` (id del usuario y su rol en la plataforma). El service nunca recibe `current_user`. **El filtro de alcance (`ScopeFilter`) queda diferido** hasta el primer módulo que filtre datos por unidad. | No hay restricción de visibilidad en esta feature (C13): los roles solo limitan acciones. |
| C5 | **D3, D4 y la sobrescritura de secretos redactados (§10) se corrigen antes** de cualquier endpoint nuevo de escritura. | Si no, los roles quedan montados sobre un modelo en el que el rol no restringe nada. |
| C6 | El `sub` del JWT pasa de `username` a `str(_id)`, con compatibilidad hacia atrás en `get_current_user`. El `sub` es estable y nunca es el correo. | Los usuarios de Google no tienen username, y un correo puede cambiar. Además es el identificador que heredarán las demás plataformas (§8). |
| C7 | Google: el backend verifica el `id_token` (no se usa el authorization code flow). El alta es **por invitación** (`status: "invited"`) y no hay auto-provisión. | Evita que cualquier cuenta del dominio entre sola. |
| C8 | **`establishments` es la única fuente de establecimientos.** No se carga ni se versiona ningún CSV de establecimientos. | Respuesta P2. |
| C9 | **Eliminar un usuario = desactivarlo** (soft delete). | Respuesta P8. |
| C10 | **CSV: carga parcial con dry-run.** El CSV se traduce a JSON con la biblioteca estándar (`csv`, `io`, `codecs`) y ese JSON es exactamente el body del endpoint de alta masiva. No se usa pandas. | Respuestas P1 y P9. Ver §4.1. |
| C11 | **Todos los correos son `@slepllanquihue.cl`**, incluidos los del personal de establecimientos. Una única variable `ALLOWED_EMAIL_DOMAINS` sirve para validar las altas y para el chequeo `hd` de Google. | Respuesta P5. |
| C12 | **Solo el admin global (`iam/admin`) crea usuarios** y ejecuta operaciones masivas. Es un rol distinto de `datos/admin`. | Respuestas P12 y N7: separación de funciones. |
| C13 | **No hay restricción de visibilidad por establecimiento ni por unidad.** | Respuesta P11. |
| C14 | **Roles de plataforma:** `admin` (ver, editar y eliminar), `editor` (ver y editar) y `viewer` (solo ver). Rige igual para `datos` y `selloverde`. | Respuestas P7 y N6. |
| C15 | **Frontend: solo componentes shadcn/ui**, agregados con el CLI del proyecto y siguiendo las reglas de `.agents/skills/shadcn/`. No se usan otras bibliotecas de componentes ni markup propio cuando shadcn tiene un componente para ese caso. | Requisito estricto del usuario. Ver §4.3. |
| C16 | **Primer acceso y restablecimiento con un enlace de un solo uso** enviado por correo. La contraseña nunca viaja por correo. | Respuesta N1. |
| C17 | **La política de contraseñas se configura por variables de entorno** en esta iteración. | Respuesta N3. |
| C18 | **La subrogancia es solo visibilidad**: no transfiere permisos. Prioridad Could. | Respuesta N4: "añadido estético por si en algún momento se requiere". |
| C19 | **Perfil propio: el usuario edita su teléfono personal, su anexo y su contraseña.** El resto de los datos solo los cambia el admin global. | Respuesta N8. |
| C20 | **El rol `editor` ve credenciales en claro** (licencias, SSID), igual que `admin`. Solo `viewer` las recibe redactadas. | Respuesta N10 ("sin restricción"), leída como que el editor no tiene restricción para ver credenciales. Confírmalo en el resumen de la Fase 1, porque amplía quién ve secretos. |
| C21 | **Los correos se envían con Gmail API**, reutilizando el cliente OAuth que ya existe (`GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`). Una casilla remitente dedicada da su consentimiento **una sola vez** con el scope `gmail.send`, y el backend guarda el refresh token como secreto. | Respuesta N2. Detalle en §4.1 y §7. |
| C22 | **`positions` es una lista con al menos un valor** para los usuarios de establecimiento. Lo habitual es un solo valor; tener varios es excepcional. | Respuesta N11. |
| C23 | **El enum de cargos incluye `DOCENTE` y `ASISTENTE_EDUCACION` y no incluye `ENCARGADO_CONVIVENCIA`.** | Respuesta N12. |

---

## 2. Requisitos funcionales

Numerados para poder trazarlos. Cada historia de usuario debe citar los `R` que cubre.

**R1 · Usuario.** Correo `@slepllanquihue.cl`, nombre, apellido, teléfono personal, anexo
(teléfono laboral interno) y los campos del documento `users` propuesto (estado, proveedores de
autenticación, accesos, última actividad, auditoría). Un booleano **funcionario SLEP**: si es
`true`, el usuario pertenece a una **unidad**; si es `false`, a un **establecimiento** (`rbd`).
Siempre uno de los dos: nunca ambos, nunca ninguno. Los usuarios de establecimiento tienen
**cargo** (enum, §3.1) para filtrar y buscar en implementaciones futuras.

**R2 · Unidad organizacional.** Entidad propia con id, código, nombre libre y un **nivel
jerárquico estricto** del 1 al 5. Estructura real a sembrar:

| Nivel | Unidad | Depende de |
|---|---|---|
| 1 | Dirección Ejecutiva | — |
| 2 | Gabinete · Jurídica · Comunicaciones · Auditoría | Dirección Ejecutiva (son unidades asesoras) |
| 3 | Subdirección de Gestión de Personas | Dirección Ejecutiva |
| 3 | Subdirección de Administración y Finanzas | Dirección Ejecutiva |
| 3 | Subdirección de Gestión Territorial | Dirección Ejecutiva |
| 3 | Unidad de Apoyo Técnico Pedagógico | Dirección Ejecutiva |
| 3 | Subdirección de Planificación y Control | Dirección Ejecutiva |
| 4 | Remuneraciones · Procesos Administrativos · Formación y Desarrollo | Gestión de Personas |
| 4 | Compras y Logística · Tecnologías de la Información · Finanzas | Administración y Finanzas |
| 4 | Gestión Territorial · Coordinación de Atención Ciudadana | Gestión Territorial |
| 4 | Mejora Continua · Monitoreo y Seguimiento | Apoyo Técnico Pedagógico |
| 4 | Infraestructura · Mantenimiento · Control de Gestión | Planificación y Control |
| 5 | (sin unidades hoy; el modelo lo soporta) | una unidad de nivel 4 |

Son 23 unidades. Los nombres **no** son fijos: el nivel es el invariante y el nombre es un dato.
Hay nombres que **se repiten entre niveles** ("Gestión Territorial" es a la vez subdirección y
unidad), así que el nombre no sirve como identificador y cada unidad tiene un `code` único
(§3.2).

**R3 · Jefatura y subrogancia.** Cada unidad puede tener una jefatura (`head_user_id`). La
subrogancia registra quién reemplaza a la jefatura durante un período, y se muestra (C18).

**R4 · Contrapartes ↔ usuarios.** Una contraparte (`counterparts`) es una persona que puede ser
o no usuario de la plataforma. El vínculo es opcional y nunca obligatorio.

**R5 · Vista de administración de usuarios.** Tabla con paginación en el servidor que muestra
usuario, permisos, unidad o establecimiento y fecha de última actividad. Incluye barra de
búsqueda, filtros y un botón "Crear usuario" que abre un modal: el formulario queda encima y la
tabla se sigue viendo detrás, bajo un overlay semitransparente. Permite seleccionar varios
usuarios para **edición masiva** (asignar unidad, dar o quitar acceso a una plataforma) y
**desactivación masiva**.

**R6 · Creación reutilizable.** Una sola ruta de código de creación sirve para el alta
individual, la carga masiva y el seed del administrador. La carga masiva traduce el CSV a JSON,
muestra la vista previa del dry-run y luego crea las filas válidas.

**R7 · Contraseñas.** Política configurable (C17) con valores por defecto recomendados. El admin
puede restablecer la contraseña de cualquier usuario. El primer acceso llega por correo como
enlace de un solo uso (C16).

**R8 · Unicidad del correo.**

**R9 · Validación de todos los formularios contra inyección.**

**R10 · Perfil propio** (C19).

**R11 · IAM centralizado (solo diseño, Fase 7).** Las plataformas bajo
`*.slepllanquihue.gob.cl` no deben tener cada una su propia gestión de usuarios. Hoy existen
`datos.slepllanquihue.gob.cl` (este sistema) y `selloverde.slepllanquihue.gob.cl`, que según la
información del usuario está hecha en NestJS con PostgreSQL y también arranca con un único admin
sembrado. Marco de diseño en §8.

---

## 3. Modelo de datos de partida (hipótesis que el diagrama de la Fase 1 valida o corrige)

Los nombres de colecciones y campos van en **inglés**, igual que los cinco módulos existentes.
`05` §1 Paso 1 pide nombres de carpeta en español: regístralo como `🔸 BRECHA` de la
documentación y sigue la convención del código.

### 3.1 `users`

```json
{
  "_id": "ObjectId",
  "email": "nombre.apellido@slepllanquihue.cl",
  "first_name": "…",
  "last_name": "…",
  "personal_phone": "+56912345678",
  "work_extension": "4521",
  "is_slep_staff": false,
  "unit_id": "ObjectId | null",
  "rbd": "7722 | null",
  "positions": ["DOCENTE", "PIE_ENCARGADO"],
  "status": "invited | active | disabled",
  "auth_providers": [
    { "provider": "local", "hashed_password": "…", "password_changed_at": "ISODate", "must_change_password": false },
    { "provider": "google", "subject": "…", "linked_at": "ISODate" }
  ],
  "access": [
    { "platform_id": "datos", "role": "editor", "granted_at": "ISODate", "granted_by": "ObjectId" }
  ],
  "last_login_at": "ISODate",
  "last_activity_at": "ISODate",
  "created_at": "ISODate", "created_by": "ObjectId",
  "updated_at": "ISODate", "updated_by": "ObjectId",
  "disabled_at": "ISODate | null"
}
```

- `email` se normaliza (`strip` + `lower`) antes de guardar **y** antes de buscar, y su dominio
  tiene que estar en `ALLOWED_EMAIL_DOMAINS` (C11).
- `work_extension` es un string de dígitos, no un número.
- **Cargo: `positions`** es una lista de `EstablishmentPosition(str, Enum)` definida en
  `users_entity.py`. Es obligatoria (al menos un valor) cuando `is_slep_staff = false`, y vacía
  para funcionarios SLEP. Tiene índice multikey (C22).
  - **Valores cerrados (C23):** `DIRECTOR`, `UTP_JEFE`, `PIE_ENCARGADO`, `CONVIVENCIA_ESCOLAR`,
    `INSPECTOR_GENERAL`, `SIGE_ENCARGADO`, `SECRETARIO`, `ADMINISTRADOR`, `DOCENTE` y
    `ASISTENTE_EDUCACION`.
  - **No existe `ENCARGADO_CONVIVENCIA`.** Duplicaría `CONVIVENCIA_ESCOLAR`, el valor canónico al
    que `seed_service.py:125` mapea la clave `convivencia_encargado` del JSON.
  - Es una lista porque los valores mezclan cargos (`DIRECTOR`, `DOCENTE`, `SECRETARIO`) con
    funciones (`PIE_ENCARGADO`, `SIGE_ENCARGADO`), y una persona puede ser docente y encargada
    PIE a la vez. Lo normal es que tenga **un solo valor**, así que la UI debe hacer fácil el caso
    de un valor y permitir agregar más sin darle protagonismo. Un único selector con opción de
    agregar otro es suficiente; no hace falta un multiselect en primer plano.
  - Los valores que coinciden con `CounterpartRole` usan exactamente el mismo string, para que un
    filtro futuro pueda cruzar ambas colecciones.
  - El CSV acepta varios valores separados por `|` en la misma celda. Lo habitual será uno solo.
- `personal_phone` es un dato personal: se agrega al mapa de campos sensibles de `02` §7, se
  excluye de la proyección del listado y solo lo ven el admin global y el propio usuario. Tiene
  en cuenta la Ley 19.628 y la Ley 21.719, que entra en vigencia en diciembre de 2026.
- El `role` que hoy está en la raíz del documento pasa a `access[]`, con compatibilidad hacia
  atrás mientras dure la migración. El admin actual pasa a tener `access` `iam/admin` y
  `datos/admin`.
- **Migración del admin sembrado.** Hoy no tiene correo. El bootstrap lo toma de
  `BOOTSTRAP_ADMIN_EMAIL`, una variable obligatoria sin default (T9).

**Invariantes, cada uno con su test:**
- `is_slep_staff = true` ⇒ `unit_id` tiene valor, `rbd` es null y `positions` está vacía. Si es
  `false`, entonces `rbd` tiene valor, `positions` tiene al menos un elemento y `unit_id` es null.
  Se valida con un `model_validator` de Pydantic.
- `rbd` existe en `establishments`. Lo valida el service a través de `establishments_service`
  (L5, C8).
- `unit_id` existe y la unidad está activa.
- Siempre queda al menos un usuario activo con `access` `iam/admin`. No se puede desactivar ni
  degradar al último admin global, **tampoco con una operación masiva**.
- Un admin global no puede desactivarse a sí mismo.
- `hashed_password` no aparece en ninguna respuesta. Un test recorre el JSON completo buscando
  la clave, con el mismo patrón que INT02.

**Índices:** `email` único; `auth_providers.subject` único parcial (solo cuando el proveedor es
google); `unit_id`; `rbd`; `positions` (multikey); `access.platform_id`; `status`;
`last_activity_at`.

### 3.2 `units`

```json
{
  "_id": "ObjectId",
  "code": "SD-GT",
  "name": "Subdirección de Gestión Territorial",
  "level": 3,
  "parent_id": "ObjectId | null",
  "ancestors": ["ObjectId(Dirección Ejecutiva)"],
  "head_user_id": "ObjectId | null",
  "order": 3,
  "status": "active | inactive",
  "created_at": "ISODate", "updated_at": "ISODate"
}
```

- `code` es un slug corto, único, en mayúsculas y estable: no cambia si la unidad se renombra.
  Es lo que usa el CSV para referirse a una unidad. Propón los códigos de las 23 unidades de R2
  en la Fase 1 para que el usuario los valide. Como referencia: `DE`, `GAB`, `JUR`, `COM`, `AUD`,
  `SD-GP`, `SD-AF`, `SD-GT`, `UATP`, `SD-PC`, `GP-REM`, `AF-TI`, `GT-GT`, `PC-INF`…
- `ancestors` es la ruta materializada desde la raíz. Permite consultar un subárbol con una
  consulta indexada, sin recursión. No uses `$graphLookup`.
- **Seed:** `units_service.ensure_bootstrap_units()`, llamado desde el `lifespan`, crea la
  estructura de R2 solo cuando la colección está vacía. Los datos van como constante en el
  módulo `units`, no como archivo `.json` (la política de documentación los ignora en git).

**Invariantes:**
- Hay exactamente una unidad de nivel 1, y no tiene padre.
- Las unidades de nivel 2 y 3 tienen como padre la de nivel 1. Las de nivel 4 cuelgan de una de
  nivel 3, y las de nivel 5 de una de nivel 4. En consecuencia, una unidad de nivel 2 no puede
  tener hijas. Esto es coherente con la respuesta N5: Auditoría queda sin cambios de modelo.
- El nombre es único **entre las hermanas**, no a nivel global.
- El service recalcula `ancestors` al crear o mover una unidad. Mover una unidad reescribe los
  `ancestors` de todo su subárbol.
- No se puede desactivar una unidad que tenga usuarios activos o unidades hijas activas.

**Índices:** `code` único; `(parent_id, name)` único; `ancestors` (multikey); `level`.

### 3.3 `platforms` y matriz de roles

```json
{ "_id": "iam",        "name": "Administración de usuarios",  "base_url": "https://datos.slepllanquihue.gob.cl",      "roles": ["admin"],                     "status": "active" }
{ "_id": "datos",      "name": "Gestión de Establecimientos", "base_url": "https://datos.slepllanquihue.gob.cl",      "roles": ["admin", "editor", "viewer"], "status": "active" }
{ "_id": "selloverde", "name": "Sello Verde",                 "base_url": "https://selloverde.slepllanquihue.gob.cl", "roles": ["admin", "editor", "viewer"], "status": "active" }
```

- `_id` es un slug estable que funciona como clave de negocio.
- `access[].role` se valida contra `platforms.roles`.
- `iam` es una plataforma lógica. El admin global es quien tiene `access` `iam/admin` (C12).
  Se implementa con el mismo mecanismo de `access[]`, sin campo booleano ni concepto nuevo.
- Las credenciales de plataforma se diseñan en la Fase 7 (§8).

**Matriz de roles en `datos`** (C14 y C20; reemplaza la de `04` §2.1 al implementarse):

| Operación | `viewer` | `editor` | `admin` |
|---|---|---|---|
| `GET` de establecimientos, contrapartes, métricas y analytics | ✅ | ✅ | ✅ |
| Ver `licenses[].password` y `ssid_password` en claro | ❌ redactado | ✅ | ✅ |
| `PUT` / `POST` de ficha, contrapartes y métricas | ❌ `403` | ✅ | ✅ |
| `DELETE` (hoy solo `DELETE /api/counterparts/{id}`) | ❌ `403` | ❌ `403` | ✅ |
| `/api/users/*` (salvo `/me`), escritura en `/api/units/*`, `/api/platforms/*` | solo con `iam/admin` | solo con `iam/admin` | solo con `iam/admin` |
| `GET` y `PATCH /api/users/me` | ✅ | ✅ | ✅ |

### 3.4 `subrogations` (R3, C18; propiedad del módulo `units`; prioridad Could)

```json
{
  "_id": "ObjectId",
  "unit_id": "ObjectId",
  "subrogate_user_id": "ObjectId",
  "starts_at": "ISODate",
  "ends_at": "ISODate | null",
  "reason": "VACACIONES | LICENCIA | COMISION | VACANCIA | OTRO",
  "document_ref": "Resolución Exenta N° … | null",
  "created_by": "ObjectId", "created_at": "ISODate",
  "cancelled_at": "ISODate | null"
}
```

- Es una colección aparte porque el historial crece sin límite. Su dueño es `units`, y que un
  módulo sea dueño de dos colecciones se registra en ADR-010.
- La subrogancia "vigente" se calcula por fecha. No hay jobs.
- Se muestra en el árbol de unidades, en la tabla de usuarios y en el perfil.
- Reglas adoptadas (N4 solo confirmó "visibilidad", así que se aplican las recomendaciones):
  - La registra el admin global.
  - Quien subroga está activo, no es la jefatura titular y pertenece al subárbol de la unidad.
  - No se superponen dos subrogancias vigentes para una misma unidad.
  - `ends_at` es obligatorio salvo cuando `reason = VACANCIA`.
- **No transfiere permisos.**

### 3.5 `counterparts` (cambio)

- Se agrega `user_id: Optional[str] = None`, que nunca es obligatorio.
- El backfill lo hace un script con modo dry-run que empareja por correo normalizado. Las
  coincidencias ambiguas y los registros sin correo se reportan, pero no se vinculan.
- Enmienda a ADR-002: "se modela la relación, no la persona" sigue vigente y el vínculo es
  opcional.

### 3.6 `auth_tokens` (C16; propiedad del módulo `auth`)

```json
{ "_id": "ObjectId", "user_id": "ObjectId", "purpose": "invite | reset", "token_hash": "sha256(…)",
  "expires_at": "ISODate", "used_at": "ISODate | null", "created_by": "ObjectId", "created_at": "ISODate" }
```

- El token (`secrets.token_urlsafe(32)`) solo viaja en el correo. En la base se guarda su hash.
- Un índice TTL sobre `expires_at` hace que Mongo borre solos los tokens vencidos.
- Al emitir un token nuevo para el mismo usuario y propósito, se invalida el anterior.

### 3.7 `audit_log` (propuesta del agente; necesita aprobación)

```json
{ "_id": "ObjectId", "at": "ISODate", "actor_id": "ObjectId", "action": "user.create | user.disable | access.grant | password.reset | unit.move | subrogation.create | …",
  "target_type": "user | unit | subrogation", "target_id": "…", "changes": { "campo": ["antes", "después"] }, "bulk_id": "string | null" }
```

- Solo se agregan registros; nunca se editan.
- `changes` jamás contiene hashes, contraseñas ni tokens.
- Motivo: `04` §7 dice que hoy no hay ninguna auditoría, y para un IAM saber quién le dio a
  quién acceso a qué es un requisito mínimo.

---

## 4. Patrones: cuáles usar y cuáles no

### 4.1 Aprobados (backend)

| Patrón | Dónde | Qué resuelve |
|---|---|---|
| **Módulo por dominio** (ADR-007) | `users/`, `units/`, `platforms/`, cada uno con exactamente tres archivos | Mantiene la predictibilidad del árbol. Un cuarto archivo en un módulo necesita un ADR. |
| **Un único pipeline de creación** | `users_service.create_many(items, actor_id, dry_run) -> BulkResult`; `create(item)` es `create_many([item])` | **R6.** El alta individual, el CSV, el seed y la futura provisión IAM pasan por las mismas validaciones: normalizar → resolver referencias (`unit_code` → `unit_id`, `rbd`) en lote → detectar duplicados dentro del lote y contra la base → insertar → auditar → emitir invitación. El service recibe `actor_id: str`, no el usuario (L3). |
| **Bootstrap desde el módulo dueño** | `users_service.ensure_bootstrap_admin()` y `units_service.ensure_bootstrap_units()`, llamados desde el `lifespan` de `main.py` | Reemplazan `_seed_admin_user` de `seed_service.py`. El seed usa los mismos pipelines, y `database` no importa módulos de dominio. |
| **CSV → JSON con la biblioteca estándar** (C10) | Ver el detalle debajo de esta tabla | **R6.** El CSV no tiene reglas propias: se traduce al mismo JSON del alta masiva. |
| **Unión discriminada para operaciones masivas** | `BulkOperation = Annotated[Union[AssignUnit, GrantAccess, RevokeAccess, Disable, Enable], Field(discriminator="op")]`; en el service, un `dict` de `op` → método | **R5.** Un solo endpoint `POST /api/users/bulk`. |
| **Dependencia de autorización** | `require_access(platform, roles) -> AccessContext` en `auth` | C4, C5, C14. |
| **Plataforma lógica `iam`** | `platforms` + `access[]` | C12, sin un concepto nuevo. |
| **Árbol materializado** | `units.ancestors` | Consultas de subárbol sin recursión. |
| **Estado calculado por fecha** | `subrogations` | "Vigente" sin jobs. |
| **Índice TTL** | `auth_tokens.expires_at` | Los tokens vencidos desaparecen sin cron. |
| **Soft delete por estado** | `users.status` | C9. |
| **Modelo de actualización por audiencia** | `UserAdminUpdate` vs `UserSelfUpdate` (solo `personal_phone`, `work_extension`), ambos con `extra="forbid"` | **R10, C19.** Enviar `access`, `status` o `unit_id` a `/me` devuelve `422`. La protección está en el tipo y no depende de un `if`. |
| **Envío de correo como módulo de infraestructura** | `backend/app/mail/mail_service.py`, al mismo nivel que `database/`, con un único método `send(to, subject, html, text)` | **C16, C21.** Los módulos de dominio no saben que existe Gmail. En los tests se mockea `mail_service`, igual que hoy se mockea `db_service`. Como es infraestructura y no dominio, no sigue la regla de los tres archivos. Se registra en ADR-012. |

**Detalle del envío con Gmail API (C21):**
- **Dependencias:** usa `google-auth` (que ya se necesita para C7) para refrescar el access token
  a partir del refresh token, y llama directamente al endpoint REST
  `users.messages.send` de Gmail. El mensaje se arma con `email.message.EmailMessage` de la
  biblioteca estándar, codificado en base64url. **No agregues `google-api-python-client`**: es
  una dependencia grande para una sola llamada.
- **El envío no bloquea el event loop.** Usa un cliente HTTP asíncrono, o ejecuta la llamada
  síncrona en el threadpool. Y no hagas que la respuesta del alta espere al correo si eso la
  vuelve lenta: el alta ya está diseñada para tolerar un envío fallido (§6, primer acceso).
- **Consentimiento inicial.** Un script en `backend/scripts/` (mismo patrón que
  `import_kmz_locations.py`) ejecuta una sola vez el flujo de consentimiento con la casilla
  remitente e imprime el refresh token para guardarlo como secreto. Nunca lo escribe en un
  archivo del repo. El procedimiento se documenta en `07-operacion.md`.
- **Riesgos operativos que el ADR-012 tiene que dejar escritos:**
  - La pantalla de consentimiento del cliente OAuth tiene que ser de tipo **Internal**. Si fuera
    External en estado "Testing", Google caduca el refresh token a los 7 días.
  - Si cambia la contraseña de la casilla remitente, Google revoca los tokens con scopes de Gmail,
    y el envío falla hasta repetir el consentimiento. El diseño lo tolera: el usuario queda
    `invited` y el admin reenvía. Pero el fallo tiene que quedar en el log y ser visible para el
    admin.
  - El refresh token da permiso para enviar correo en nombre de esa casilla. Se trata con el mismo
    cuidado que `JWT_SECRET`.

**Detalle de CSV → JSON (C10), verificado contra el hilo de Stack Overflow citado por el
usuario.** El hilo propone tres opciones:

1. `csv.DictReader(codecs.iterdecode(file.file, "utf-8"))` en un endpoint `def`, que lee el
   `SpooledTemporaryFile` de `UploadFile` en streaming y cierra el archivo al terminar (o con
   `BackgroundTasks` si se devuelve la lista).
2. Leer el contenido completo → `io.StringIO(contents.decode(...))` → `csv.DictReader`, y cerrar
   el buffer y el archivo.
3. Copiar el contenido a un `NamedTemporaryFile` en disco y abrirlo por ruta.

**Usa la opción 2.** Las razones:

- La decodificación tiene que probar `utf-8-sig` (el BOM que agrega Excel) y, si falla, `cp1252`
  (Excel en es-CL). Esto no se puede hacer sobre un stream a medio consumir.
  `codecs.iterdecode(..., "utf-8")` de la opción 1, además, deja el BOM pegado al nombre de la
  primera columna.
- `csv.Sniffer` necesita una muestra del contenido para detectar si el delimitador es `;` o `,`.
- Con un límite de tamaño y de filas, tener el archivo en memoria es seguro.
- La opción 3 escribe datos personales en disco sin necesidad. Descártala.

Una precisión que el hilo aclara: su ejemplo de la opción 2 usa `file.file.read()` dentro de un
endpoint `def`. Como este backend usa `async def` en todas partes (Motor), hay que usar
`await file.read()`. Llamar a `file.file.read()` dentro de `async def` bloquea el event loop.

Otras dos diferencias con el hilo:

- **Salida en lista, no en diccionario.** El hilo arma un `dict` con una columna `Id` como clave.
  Aquí se necesita una **lista** de filas que conserve el número de fila, para reportar los
  errores de cada una.
- **Lo que viaja es el JSON, no el CSV.** `POST /api/users/import` recibe el CSV y devuelve el
  JSON traducido con el resultado del dry-run. El frontend muestra la vista previa y, cuando el
  admin confirma, envía ese mismo JSON (solo con las filas válidas) a
  `POST /api/users/bulk-create`.

### 4.2 Prohibidos

| No introducir | Motivo |
|---|---|
| Capa repository, `BaseService` o `BaseRepository` genéricos | ADR-007 descartó la arquitectura hexagonal. |
| Carpetas `utils/` o `shared/` | L11. |
| Event bus, CQRS, colas, Celery o cron | Ninguna operación de esta feature lo requiere. |
| Redis u otra caché distribuida | No hace falta ni en esta feature ni en el diseño de §8 (lo que se cachea allí son claves públicas). |
| `ScopeFilter` o filtros de alcance por unidad | C4. |
| Un microservicio IAM separado | Ver §8. |
| `$graphLookup` para la jerarquía | `ancestors` lo hace innecesario. |
| Librerías de RBAC (casbin u otras) | Tres roles por plataforma se resuelven con un `set`. |
| pandas para el CSV | C10. |
| Cualquier biblioteca de componentes que no sea shadcn/ui (MUI, Chakra, Ant, etc.) | C15. |
| `@tanstack/react-table` para la tabla de usuarios | La paginación, el filtrado y el orden los hace el servidor (T8). La `Table` de shadcn con `Pagination` y `Checkbox` alcanza. Si aparece una necesidad real (por ejemplo, columnas configurables), justifícala. |
| `react-hook-form` + `zod` sin justificación | Las reglas de `forms.md` no los exigen: la maquetación de formularios es con `Field`. El formulario de usuario tiene alrededor de diez campos, y el backend es la frontera de validación. Si decides agregarlos, justifícalo en la Fase 1 como decisión con su impacto en el despliegue. |

### 4.3 Frontend: reglas de shadcn aplicadas a esta feature (C15)

Las reglas completas están en `.agents/skills/shadcn/`. Estas son las que más afectan a esta
feature y las más fáciles de romper:

- **Flujo obligatorio del CLI:**
  1. `npx shadcn@latest info` para confirmar `base` (radix o base), `style`, `iconLibrary`
     (`lucide`) y los componentes ya instalados. Hoy son solo `alert`, `button`, `card`, `input`
     y `label`.
  2. `npx shadcn@latest docs <componente>` antes de usar cada uno, leyendo las URLs que
     devuelve.
  3. `npx shadcn@latest add …` para lo que falte.
  4. Revisar los archivos agregados.
  - Nunca descargues archivos de componentes a mano.
  - Nunca uses `--overwrite` sin aprobación del usuario.
  - Nunca agregues componentes de un registro de terceros sin que el usuario lo nombre.
- **Qué componente para qué** (verifica los nombres con `docs`):

  | Necesidad | Componente |
  |---|---|
  | Tabla | `Table` + `Pagination` |
  | Selección múltiple | `Checkbox` |
  | Estado y rol | `Badge` |
  | Acciones de fila | `DropdownMenu` |
  | Modal de alta y edición | `Dialog` con `DialogTitle` obligatorio |
  | Confirmación de desactivación masiva | `AlertDialog` |
  | Toggle "Funcionario SLEP" | `Switch` |
  | Establecimiento con búsqueda | `Combobox` (o `Popover` + `Command`, según la versión instalada) |
  | Unidad y cargo | `Select` o `Combobox` |
  | Filtros | Controles de formulario dentro de `FieldGroup` |
  | Tabla sin resultados | `Empty` |
  | Carga | `Skeleton` |
  | Avisos | `sonner` si la base es radix |
  | Vista previa del CSV | `Table` + `Alert` para los errores por fila |

- **Formularios:** `FieldGroup` + `Field`. La validación se marca con `data-invalid` en el
  `Field` y `aria-invalid` en el control, y el `409` por correo repetido se muestra en ese mismo
  campo.
- **El overlay del modal:** el requisito R5 (la tabla visible detrás) se cumple con el overlay
  del `Dialog`. Si la opacidad por defecto no alcanza, se ajusta **una vez** en
  `components/ui/dialog.jsx` siguiendo `customization.md`, no con clases en cada uso. No asignes
  `z-index` a mano en overlays.
- **Estilos:**
  - Usa tokens semánticos (`bg-background`, `text-muted-foreground`, variantes de `Badge`) y
    nunca colores crudos.
  - Usa `flex` con `gap-*`, no `space-y-*`, y `cn()` para las clases condicionales.
  - Los íconos dentro de un `Button` llevan `data-icon` y no llevan clases de tamaño.
- **No copies el estilo de los componentes existentes.** Hay unas 340 clases de color crudas
  (`bg-slate-900`, `text-sky-500`…) repartidas entre `AppLayout.jsx`, `Directory.jsx`,
  `FichaEstablecimiento.jsx` y otros. Eso viola `styling.md`: regístralo como `🔸 BRECHA` de
  estilo y **no lo refactorices en esta feature**. Las pantallas nuevas siguen la skill. Si con
  eso quedan visualmente distintas del resto, ajusta las variables de tema en `src/index.css`
  (el `tailwindCssFile` del proyecto) en lugar de volver a los colores crudos. Si la diferencia
  persiste, preséntala al usuario como decisión.
- **Guard de rol:** es un componente nuevo que compone con `ProtectedRoute`. **No modifiques
  `ProtectedRoute`** (regla 4 de CLAUDE.md).
- **Cliente API único:** `frontend/src/lib/api.js` (ADR-008).
- **Un solo formulario:** `UserForm`, reutilizado para crear y editar. El backend es la frontera.

---

## 5. Criterios transversales (valen para toda historia y cada uno necesita un test)

**T1 · Inyección.** El stack es MongoDB, así que la "SQL injection" no aplica literalmente.
Los vectores reales son estos:
- **Inyección de operadores**, por ejemplo `{"email": {"$ne": null}}`. Todo body y todo query
  param es un modelo Pydantic con tipos escalares y `model_config = ConfigDict(extra="forbid")`.
  Test: esos payloads devuelven `422`.
- **Inyección de regex / ReDoS (D5).** Toda búsqueda de texto pasa por `re.escape`. Test: buscar
  `(a+)+$` o `.*` se interpreta como texto literal.
- **Asignación masiva de campos.** `PATCH /api/users/me` con `access` devuelve `422` y el
  documento no cambia.
- Todos los strings tienen longitud máxima. El correo usa `EmailStr` más la validación de
  dominio (C11). El teléfono personal usa formato E.164 chileno. El anexo acepta solo dígitos.
- El CSV se valida fila por fila con las mismas reglas.
- La validación del frontend es solo experiencia de usuario. **Cada criterio se verifica contra
  el backend.**

**T2 · Unicidad del correo.** Se normaliza antes de guardar y antes de buscar. El índice único
es la garantía final: `DuplicateKeyError` se traduce a `409` en el controller. En los lotes se
reportan, fila por fila, los duplicados internos y los que chocan con la base.

**T3 · Autenticación y autorización.** Ninguna ruta queda sin autenticación (L8). Cada ruta
declara con `require_access` qué plataforma y qué roles admite. Hay tests por rol según la matriz
de §3.3.

**T4 · Campos sensibles.** Ninguna respuesta incluye `hashed_password` ni `token_hash`.
`personal_phone` solo llega al admin global y al propio usuario. Las credenciales de
establecimiento se redactan solo para `viewer` (C20). Test que recorre el JSON completo.

**T5 · Respuestas de escritura.** Las escrituras individuales devuelven el documento resultante
(L9). Las masivas devuelven un `BulkResult` con el resultado de cada ítem.

**T6 · Auditoría.** Toda escritura sobre `users`, `units`, `subrogations` o `access` deja un
registro en `audit_log`, si se aprueba §3.7.

**T7 · Invariantes de admin.** Aplican los de §3.1, también en masa.

**T8 · Paginación.** Paginación en el servidor con `page_size ≤ 200` y el patrón de BE04.

**T9 · Configuración sin defaults peligrosos.** Ninguna variable secreta o de identidad tiene
default (D2): `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GMAIL_SENDER_ADDRESS`,
`GMAIL_REFRESH_TOKEN`, `BOOTSTRAP_ADMIN_EMAIL`, `ALLOWED_EMAIL_DOMAINS` y `PUBLIC_BASE_URL`. Si falta alguna, la app no arranca. La política de
contraseñas sí tiene defaults, porque no es un secreto, pero se valida al arrancar: un valor
fuera de rango impide el arranque con un mensaje claro.

**T10 · Frontend conforme a shadcn.** Cada historia de frontend incluye un CA verificable que
compruebe:
- que todo componente usado viene de `@/components/ui/` y fue agregado con el CLI;
- que los `Dialog` y `AlertDialog` tienen título;
- que no hay colores crudos, `space-y-*` ni `z-index` manual en los archivos nuevos.

Esto último se puede verificar con un `grep` sobre esos archivos. Incluye el comando en el CA.

---

## 6. Fase 1: entregables de esta sesión (planificación, sin código)

Prepara 1a y 1b en conjunto. Presenta 1c antes del gate.

### 1a · Diagrama de datos como Artifact

Publícalo como Artifact. Si tu entorno no lo permite, déjalo como `.md` con Mermaid en
`Documentacion/`. Contenido:

1. **Un `erDiagram` de Mermaid** con `users`, `units`, `subrogations`, `platforms`,
   `auth_tokens`, `establishments` (solo `rbd` y `name`), el cambio en `counterparts` y
   `audit_log` (marcada como propuesta). Los subdocumentos embebidos (`auth_providers[]`,
   `access[]`) se ven distintos de las referencias entre colecciones. Muestra las relaciones
   lógicas con su cardinalidad, marca índices y campos sensibles, y agrega una leyenda.
2. **El organigrama del SLEP** con las 23 unidades reales y sus `code` propuestos, marcando las
   jefaturas, más un ejemplo de subrogancia vigente. Tiene que mostrar `parent_id` y `ancestors`
   de al menos un nodo de nivel 4.
3. **Un `stateDiagram` del ciclo de vida del usuario**: `invited → active → disabled → active`,
   con el evento que dispara cada transición (invitación enviada, primer acceso, desactivación,
   reactivación, invitación vencida y reenvío).

Cada diagrama va seguido de una explicación en prosa (convención de `00` §5).

### 1b · Historias de usuario

Usa este formato para cada historia:

```
### US-XX · Título
Como <rol> quiero <acción> para <beneficio>.
Trazabilidad: R#, C#, T#
Prioridad: Must | Should | Could   ·   Origen: usuario | propuesta del agente
Criterios de aceptación:
- CA-XX.1 Dado <estado> cuando <acción> entonces <resultado observable> → test_BE##_<nombre>
- CA-XX.2 …
Fuera de alcance: …
Depende de: US-YY
```

**Reglas para los criterios:**
- Cada CA se puede observar por HTTP o en la UI, tiene resultado binario (pasa o no pasa) y
  **nombra el test que lo verifica**. Sigue la numeración existente (`test_BE##_`, `test_FE##_`,
  `test_INT##_`) a partir del último ID que exista de verdad. Compruébalo con `ls` y no lo
  supongas: el commit `5b0984e` menciona FE06, pero ese archivo no existe.
- No se aceptan CA vagos como "valida correctamente", "es seguro", "es intuitivo" o "es rápido".
- Los casos negativos (lo que **no** debe pasar) pesan igual que los positivos.
- Separa las historias que pidió el usuario de las que propones tú. Las tuyas no entran al plan
  hasta que se aprueben.

**Épicas mínimas.** Coinciden con las fases de §7. Complétalas, divídelas o fusiónalas, pero
justifica cada cambio.

| Épica | Contenido |
|---|---|
| E0 · Prerrequisitos | `require_access` con la matriz de §3.3, que cierra D3 y D4. Protección contra la sobrescritura de secretos redactados (§10), con su test. El test que falta para la fuga por `PUT` (`04` §4). Extraer `users` de `auth` sin cambiar el comportamiento. Migrar el admin sembrado. Mantener `GET /api/auth/me` con su contrato actual (lo usan `App.jsx` y los tests FE). |
| E1 · Unidades | Seed del organigrama, CRUD del admin global, invariantes de nivel, mover una unidad con su subárbol, árbol para los selectores, jefatura. |
| E1b · Subrogancia (Could) | Registrar, cancelar y mostrar subrogancias (C18). |
| E2 · Usuarios | Alta SLEP y alta de establecimiento (con `positions`), edición, desactivar y reactivar, unicidad, dominio de correo, última actividad. |
| E2b · Perfil propio | `GET` y `PATCH /api/users/me` con `UserSelfUpdate`, cambio de contraseña propia, vista `/perfil`. |
| E3 · Contraseñas y primer acceso | Política por variables de entorno, invitación con enlace de un solo uso, reenvío, restablecimiento por el admin, `mail_service` con Gmail API (C21) y el script de consentimiento inicial. |
| E4 · Acceso por plataforma | Seed de `platforms` (`iam`, `datos`, `selloverde`), otorgar y revocar rol por plataforma. |
| E5 · Operaciones masivas | `POST /api/users/bulk`, CSV → JSON con vista previa, `bulk-create` parcial, plantilla. |
| E6 · Frontend de administración | Vista `/usuarios`, filtros en la URL, modal, selección múltiple, vista previa del CSV y guard de rol, todo conforme a §4.3. |
| E7 · Contrapartes ↔ usuarios | `user_id` opcional, backfill con dry-run, visualización en la ficha. |
| E8 · Google | Según C7 y C11. |
| E9 · Endurecimiento (propuesta del agente) | `audit_log`; rate limiting del login, del reset y del canje de enlaces (`04` §7). |
| E10 · IAM | Una única historia de tipo spike: producir el ADR de §8, sin implementación. |

**Detalles que las historias tienen que cubrir, porque son fáciles de hacer mal:**
- **Primer acceso (C16):**
  - Al crear un usuario se envía un correo con un enlace de un solo uso (§3.6) para definir la
    contraseña. El mismo correo ofrece entrar con la cuenta de Google institucional.
  - El enlace vence (propón un plazo) y queda inservible después de usarse.
  - El restablecimiento por el admin usa el mismo mecanismo con `purpose: reset` y actualiza
    `password_changed_at`. `get_current_user` rechaza los tokens con
    `iat < password_changed_at`.
  - Si el envío falla, el alta no se revierte: el usuario queda `invited`, la respuesta lo
    informa y el admin puede reenviar la invitación.
- **Política de contraseñas (C17):**
  - `PASSWORD_MIN_LENGTH`, `PASSWORD_MAX_LENGTH` (al menos 64), `PASSWORD_REQUIRE_CHAR_CLASSES`
    (0 a 4) y una lista de contraseñas comunes.
  - Los defaults siguen NIST SP 800-63B vigente: priorizar el largo sobre las reglas de
    composición (clases en 0 por defecto), bloquear contraseñas comunes o comprometidas y no
    forzar la rotación periódica. **Verifica en la norma el largo mínimo vigente** y cítalo. La
    revisión 4 eleva el mínimo cuando la contraseña es el único factor.
  - El frontend obtiene la política de un endpoint para validar en vivo, y el backend la vuelve a
    aplicar.
- **Última actividad.** `last_login_at` se actualiza en cada login. `last_activity_at` se
  actualiza como mucho una vez cada N minutos por usuario.
- **CSV:**
  - Límite de tamaño y de filas.
  - La unidad se referencia por `code`.
  - `positions` va separado por `|` dentro de la celda.
  - Las filas de establecimiento se validan contra `establishments` (C8).
  - La plantilla la sirve un endpoint y no es un archivo versionado.
- **Operaciones masivas.**
  - Tienen un límite de ids por operación.
  - Los invariantes de admin se aplican a todo el lote.
  - Un `bulk_id` agrupa la auditoría.
  - Devuelven el resultado de cada id.
- **Modal, toggle y filtros:** según R5 y §4.3.
  - Al cambiar el `Switch` "Funcionario SLEP" se limpian los campos del otro modo.
  - Los filtros son: unidad (decide si incluye el subárbol), nivel, tipo, establecimiento, cargo,
    plataforma, rol, estado y "subrogando ahora". Se guardan en los query params (patrón de
    FE01).

### 1c · Preguntas abiertas y supuestos

Presenta N13 de §9.2, confirma la lectura de C20 y agrega las que encuentres. Cada ítem dice qué
cambia según la respuesta e incluye tu recomendación.

### Gate

Presenta 1a, 1b y 1c, más una **matriz de trazabilidad** (R y T → historias → tests). Después
**detente**. No pases a la Fase 2 sin un "aprobado" explícito del usuario.

---

## 7. Fases siguientes (sirven para agrupar las historias; no se ejecutan ahora)

Cada fase se trabaja en su propia rama (`feature/usuarios-fN`), cumple la DoD de `05` §6 y
muestra la salida real de los tests.

| Fase | Contenido | Notas |
|---|---|---|
| F2 · Documentación de diseño | ADR-009 (acceso por plataforma, roles, plataforma `iam`, `ScopeFilter` diferido), ADR-010 (unidades jerárquicas y subrogancias), ADR-011 (vínculo opcional contraparte ↔ usuario, enmienda a ADR-002), ADR-012 (primer acceso por correo y módulo de envío). Nota de reevaluación en ADR-001 y enmienda a ADR-006. Borradores de `02`, `03` y `04` actualizados. | Si se decide, mover los índices de cada colección nueva a su módulo. |
| F3 · Backend núcleo | E0, E1, E2, E2b, E4 | **Toca un punto único de falla (auth).** Aplica la regla 4: punto de restauración y BE03/BE05/INT02 en verde antes y después, con la salida visible. |
| F4 · Primer acceso y masivo | E3, E5, E1b | |
| F5 · Frontend | E6, la vista de E2b y la parte visual de E7 | Conforme a §4.3. |
| F6 · Google | E8 | Regla 4 otra vez. |
| F7 · IAM | ADR de §8 | Solo diseño. |

**Impacto en despliegue ya conocido (regla 3).** Confírmalo en cada fase:
- **Las variables de Google no llegan hoy al contenedor.** El usuario dejó `GOOGLE_CLIENT_ID` y
  `GOOGLE_CLIENT_SECRET` en el `.env` de la raíz, que está correctamente ignorado por git. Pero
  `docker-compose.yml` fija el `environment` del backend a mano y `docker-compose.prod.yml` solo
  interpola las variables que nombra. Hay que agregarlas explícitamente a los dos compose y a
  `.env.production.template`. Para verificar el `id_token` (C7) solo se necesita
  `GOOGLE_CLIENT_ID`. Con C21, `GOOGLE_CLIENT_SECRET` **también se usa**: lo necesita el refresco
  del token de Gmail.
- **Backend:** `email-validator` (requerido por `EmailStr`), `google-auth` y un cliente HTTP
  asíncrono para Gmail API (por ejemplo `httpx`). Nada de `google-api-python-client`. Todos
  obligan a reconstruir la imagen. Para firmar tokens asimétricos en F7, PyJWT (ya instalado)
  necesita `cryptography`.
- **Fuera del repo:** confirmar que la pantalla de consentimiento del cliente OAuth es de tipo
  Internal, agregarle el scope `gmail.send`, crear o elegir la casilla remitente y ejecutar una
  vez el script de consentimiento. Son tareas de la consola de Google Cloud y de Workspace que el
  agente no puede hacer: debe dejarlas como checklist para el usuario en `07-operacion.md`.
- **Frontend:** cada componente de shadcn agregado puede traer dependencias `@radix-ui/*`. Revisa
  con `--dry-run` qué agrega cada `add`. Todo eso obliga a reconstruir la imagen.
- **Variables nuevas:** `ALLOWED_EMAIL_DOMAINS`, `BOOTSTRAP_ADMIN_EMAIL`, `PUBLIC_BASE_URL`,
  `PASSWORD_MIN_LENGTH`, `PASSWORD_MAX_LENGTH`, `PASSWORD_REQUIRE_CHAR_CLASSES`,
  `GMAIL_SENDER_ADDRESS`, `GMAIL_REFRESH_TOKEN`, `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`.
  Todas van a los dos compose y a la plantilla.

---

## 8. Marco de interconexión entre plataformas (Fase 7, solo diseño)

Esta sección fija **el concepto y el enfoque**, no la implementación. El ADR de F7 lo convierte
en un diseño detallado.

### 8.1 Dirección adoptada

`datos` pasa a ser el **emisor de identidad** (Identity Provider, IdP) de las plataformas bajo
`*.slepllanquihue.gob.cl`. Autentica al usuario (Google o contraseña local) y emite **tokens
firmados**. Cada plataforma consumidora (hoy `selloverde`, en NestJS con PostgreSQL) **verifica el
token de forma local**, con la clave pública de `datos`, y decide la autorización dentro de su
propio contexto a partir de los claims.

- La autenticación (AuthN) está centralizada en `datos`.
- La autorización (AuthZ) es local de cada plataforma, a partir del rol que trae el token.
- La fuente de verdad de los accesos es `users.access[]` (§3.1), que ya está modelado por
  plataforma.
- **El contrato entre plataformas es el token, y solo el token.** Ninguna plataforma lee la base
  de otra.

**Por qué este enfoque.** La verificación es local: no hay una llamada de red ni una consulta a
la base de `datos` por request. `selloverde` no necesita saber que `datos` usa MongoDB, y la
caché queda reducida a lo único que hay que cachear, que son las claves públicas.

**Aclaración sobre el diagnóstico de la propuesta que dio origen a esta sección.** Esa propuesta
describe la idea original del usuario como "B consulta la base de datos de A". La idea original
era un endpoint HTTP de verificación con caché, que es la opción A de la v2 de este prompt, y no
acceso directo a la base. Aun así, la conclusión se mantiene:

- **Queda prohibido que cualquier plataforma se conecte a la MongoDB de `datos`.**
- Una API de consulta servidor a servidor sigue siendo válida para datos que no viajan en el
  token (por ejemplo, listar usuarios para asignarlos dentro de `selloverde`), pero no para
  autorizar cada request.

### 8.2 Correcciones obligatorias sobre la propuesta

La propuesta acierta en la dirección, pero tiene defectos que convertirían el SSO en el punto
más débil de todas las plataformas. El ADR debe resolverlos así:

| # | Defecto en la propuesta | Qué exige el diseño |
|---|---|---|
| 1 | Permite firmar con una `SECRET_KEY` compartida entre plataformas. | **Solo firma asimétrica** (RS256, ES256 o EdDSA). La clave privada existe únicamente en `datos`. Las plataformas obtienen la clave pública desde `/.well-known/jwks.json`, con `kid` para poder rotarla. Con un secreto compartido, cualquier plataforma podría firmar tokens de `iam/admin` válidos para `datos`. |
| 2 | Un único token con el mapa de accesos de **todas** las plataformas (`access: {a, b, c}`) y además una lista `roles`: dos fuentes de verdad dentro del mismo token. | **Un token por audiencia.** Lleva `aud=selloverde` y solo el rol de esa plataforma (`"role": "editor"`). Cada plataforma rechaza los tokens cuyo `aud` no sea el suyo. Esto aplica el mínimo privilegio (`selloverde` no se entera de los accesos del usuario en otras plataformas) y evita que un token entregado a `selloverde` se reutilice contra `datos`. |
| 3 | La sesión de `datos`, incluida la de `iam/admin`, sería el mismo token que reciben las demás. | **La sesión propia de `datos` nunca sale de `datos`.** Los tokens para terceros son otros, con su propia audiencia. Por eso la sesión interna de `datos` puede seguir en HS256, porque su secreto nunca sale del sistema, y no hay que migrarla. |
| 4 | Expiración de 24 horas en el ejemplo (`exp - iat = 86400`), sin mecanismo de revocación. | **Access tokens cortos (5 a 15 minutos, a definir) con renovación en `datos`.** La ventana de revocación (cuánto sigue entrando un usuario ya desactivado) es igual al TTL del token y tiene que quedar escrita. Un usuario `disabled` no obtiene tokens nuevos. Se relaciona con la "ventana de propagación" de `04` §1. |
| 5 | Mecanismo de entrega contradictorio: propone una cookie `HttpOnly` en `Domain=.slepllanquihue.gob.cl` y a la vez que el frontend envíe el token en `Authorization: Bearer`. JavaScript no puede leer una cookie `HttpOnly`. | **El ADR elige un mecanismo de entrega.** Recomendado: **redirección con código de un solo uso**. `selloverde` redirige a `datos`, que autentica y devuelve un código. El backend de `selloverde` lo canjea de servidor a servidor por un token con `aud=selloverde` y abre su propia sesión. Es el authorization code flow de OIDC: se implementa con bibliotecas mantenidas, no a mano. Si se elige la cookie de dominio padre, el ADR debe asumir que esa cookie llega a **todos** los subdominios, presentes y futuros. Un subdominio comprometido la obtiene, y los subdominios son "same-site" entre sí, así que `SameSite` no los separa y hace falta protección CSRF explícita. En ese caso, esa cookie solo puede contener una sesión de SSO, nunca un token de acceso a una plataforma. |
| 6 | Dice que el guard "descifra" el token y pone datos personales en los claims. | Un JWT firmado **no está cifrado**: cualquiera que lo tenga puede leer los claims. **Claims mínimos:** `iss`, `sub`, `aud`, `exp`, `iat`, `jti`, `email`, `name` y `role`. Nada de teléfono ni de datos de unidad que la plataforma no necesite. |
| 7 | Afirma que B "no necesita tablas de usuarios". | En cuanto `selloverde` guarde "quién creó este registro" o asigne tareas a personas, necesita referenciar usuarios desde PostgreSQL. **Proyección local mínima:** una tabla con `sub`, `email`, `name` y `last_seen_at`, actualizada con upsert al validar cada token (just-in-time). Sin contraseñas y sin roles, porque el rol siempre viene del token. |
| 8 | Presenta el enfoque como si eliminara el punto único de falla. | Lo **reduce, pero no lo elimina.** Si `datos` está caído, nadie puede **iniciar** sesión en ninguna plataforma. Las sesiones abiertas siguen funcionando hasta que su token expire. El ADR debe decirlo, y aceptarlo explícitamente a esta escala. |
| 9 | El correo de ejemplo es `@slepllanquihue.gob.cl`. | El dominio de correo es `@slepllanquihue.cl` (C11). El dominio web es `*.slepllanquihue.gob.cl`. No son el mismo, y la restricción `hd` de Google se aplica al de correo. |

### 8.3 Restricciones que se mantienen de la v2

- Los endpoints para terceros van versionados desde el primer día (`/api/v1/iam/...` y el
  JWKS), porque existe D10 (la API no tiene versionado).
- Rate limiting en el login, en el canje de códigos y en la renovación de tokens.
- La plataforma `iam` **no se expone**: nunca se emite un token con `aud=iam` hacia terceros, y
  ninguna plataforma puede otorgar `iam/admin`.
- Cada plataforma consumidora se registra en `platforms`, con sus URLs de redirección permitidas
  (una lista exacta, sin comodines) y su credencial de cliente guardada hasheada.

### 8.4 Construir o adoptar

Emitir tokens asimétricos, publicar el JWKS y canjear códigos es un **subconjunto acotado** de
OIDC, y se implementa con bibliotecas mantenidas:

- En Python: PyJWT con `cryptography`, o `authlib`/`joserfc`.
- En NestJS: `@nestjs/passport` + `passport-jwt` + `jwks-rsa`, o `jose`.

Si el ADR concluye que hace falta un OIDC completo (discovery, refresh tokens rotativos, pantallas
de consentimiento, logout federado), tiene que comparar con adoptar un IdP existente (Keycloak,
Zitadel o Authentik) federado con Google, antes de construirlo.

### 8.5 Lo que esto implica para las fases F3 a F6

**Nada del plan actual bloquea este diseño.** Esa es la razón para no adelantar nada de F7:

- `sub` es el `_id` estable (C6).
- `access[]` ya está modelado por plataforma y el rol de cada token sale de ahí.
- `status` ya permite negar la emisión de tokens.
- `platforms` ya existe como registro.

Lo único que F7 agrega es: el par de claves, el endpoint JWKS, el endpoint de autorización y
canje, y las credenciales y URLs de redirección de cada plataforma.

### 8.6 Entregables de F7

- ADR con la decisión sobre el mecanismo de entrega (8.2 #5), el TTL y la renovación, la rotación
  de claves y la decisión de construir o adoptar.
- **Contrato de claims** como esquema JSON: es la única interfaz entre plataformas.
- Diagramas de secuencia de: login desde `selloverde`, verificación de un request, renovación,
  desactivación de un usuario (con la ventana visible) y rotación de claves.
- Plan de PoC con `selloverde`: guard de NestJS, tabla de proyección y migración de su admin
  sembrado.

**Datos que hay que pedirle al usuario:** confirmar el stack de `selloverde` (NestJS + PostgreSQL,
según la propuesta), cómo autentica hoy, si comparte host o proxy con `datos`, y dónde termina
TLS.

---

## 9. Preguntas

### 9.1 Respondidas

| # | Pregunta | Respuesta | Dónde se aplica |
|---|---|---|---|
| P1 | "…y tra" truncado | CSV → JSON con bibliotecas integradas, según el hilo de Stack Overflow | C10, §4.1 |
| P2 | ¿CSV de establecimientos? | `establishments` es la única fuente | C8 |
| P3 | Reglas de nivel | Organigrama real | R2, §3.2 |
| P4 | ¿Subdirección con usuario único? | Es jefatura, más la subrogancia | R3, §3.4 |
| P5 | Dominio de correo | `@slepllanquihue.cl` | C11 |
| P6 | Cargo | Enum para usuarios de establecimiento | §3.1 |
| P7 | Roles | Eliminar / editar / ver | C14 |
| P8 | Eliminación | Desactivar | C9 |
| P9 | CSV parcial o total | Parcial con dry-run | C10 |
| P10 | Contraseñas | Política configurable, acceso por correo | R7 |
| P11 | Visibilidad por `rbd` | Sin restricción | C13 |
| P12 | Quién crea usuarios | Solo el admin global | C12 |
| — | Perfil propio | Ver y editar los datos propios | R10 |
| N1 | ¿Contraseña o enlace por correo? | Enlace de un solo uso | C16 |
| N3 | ¿Dónde se configura la política? | Variables de entorno | C17 |
| N4 | Subrogancia | Solo visibilidad | C18 |
| N5 | Auditoría | Sin cambios | §3.2 |
| N6 | Roles de `selloverde` | El mismo esquema | C14 |
| N7 | ¿Separar el admin global? | Sí | C12 |
| N8 | Campos editables del perfil | Teléfono, anexo y contraseña | C19 |
| N9 | Valores de cargo | La lista del usuario, con ajustes | §3.1 |
| N10 | ¿El editor ve credenciales? | Sin restricción | C20 (confirmar la lectura) |
| N2 | Transporte del correo | Gmail API con el cliente OAuth existente | C21, §4.1 |
| N11 | `positions`: ¿lista o valor único? | Lista con al menos un valor; los casos con varios serán puntuales | C22, §3.1 |
| N12 | Ajustes al enum de cargos | Agregar `DOCENTE` y `ASISTENTE_EDUCACION`; no agregar `ENCARGADO_CONVIVENCIA` | C23, §3.1 |

### 9.2 Abiertas (inclúyelas en 1c)

| # | Pregunta | Recomendación de partida |
|---|---|---|
| N13 | **¿Cuál es la casilla remitente?** Con C21 hace falta una casilla `@slepllanquihue.cl` que envíe las invitaciones y los restablecimientos. ¿Existe una, o hay que pedírsela a TI? | Una casilla dedicada, no personal (por ejemplo, una de notificaciones o no-reply). Si se usara la casilla de una persona, al irse o cambiar su contraseña se cortaría el envío para todos. |
| C20 | **Confirmar la lectura de N10**: el rol `editor` ve en claro las contraseñas de licencias y del SSID. | Presentarlo tal cual. Si la lectura es incorrecta, cambia la matriz de §3.3 y el editor vuelve a recibir los valores redactados. |

---

## 10. Brechas del repo que afectan la feature (repórtalas, no las ocultes)

- **🔸 BRECHA nueva, destructiva: sobrescritura de secretos redactados.**
  - `EditFicha.jsx:35` obtiene la ficha, que a un no-admin le llega con `licenses[].password` y
    `connectivity.ssid_password` cambiados por `"[REDACTED]"`.
  - `EditFicha.jsx:173-175` los reenvía completos en el `PUT`, y `update_by_rbd` los guarda con
    `$set`.
  - Resultado: **cuando un no-admin guarda la ficha, las contraseñas reales quedan reemplazadas
    por el literal `"[REDACTED]"`.**
  - Con la matriz de §3.3 (C20), el único rol que recibe valores redactados (`viewer`) no puede
    hacer `PUT`, así que el bug deja de ser alcanzable por diseño. Igual se agrega en E0 una
    protección en el backend (si llega el marcador de redacción, se conserva el valor almacenado),
    con su test. Es barata, y el bug destruye datos si la matriz cambia algún día.
- **`npm run lint` no se puede ejecutar.** `eslint` no está en `frontend/package.json` ni
  instalado, y no hay archivo de configuración, aunque CLAUDE.md §2 lo pide como comando de
  verificación. Regístralo como `🔸 BRECHA` nueva y no declares nunca que el lint pasó.
- **Estilos de los componentes existentes fuera de la skill de shadcn** (§4.3). Se registra y no
  se refactoriza en esta feature.
- **Hay cambios locales sin commitear de los que depende la feature:** `seed_service.py`,
  `.gitignore` (que cierra D17 al commitearse), `CLAUDE.md`, `Documentacion/` y este prompt.
  Tienen que quedar commiteados antes de F3, porque son el punto de restauración de la regla 4.
- `ensure_indexes` sigue centralizado en `database_service.py`. Se decide en F2.

---

## 11. Formato de tu respuesta en esta sesión

1. Resumen de lo que verificaste y de cualquier diferencia con este prompt (10 líneas como
   máximo), incluida la confirmación de la lectura de C20.
2. Link al Artifact de diagramas.
3. Historias de usuario agrupadas por épica.
4. Matriz de trazabilidad.
5. Preguntas abiertas (N13, la confirmación de C20 y las que agregues).
6. Detente y espera la aprobación.
