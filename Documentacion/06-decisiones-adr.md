# 06 · Decisiones de arquitectura (ADR)

> **Alcance.** Por qué el sistema está hecho así y no de otra forma. Formato ADR corto:
> Contexto · Decisión · Consecuencias · Alternativas descartadas.
>
> **Sobre la reconstrucción.** El repositorio no tenía ADRs. Estas decisiones se reconstruyen
> **retroactivamente** a partir de tres fuentes: el código actual, el historial de commits, y
> `historico/implementation_plan_iter1.md` — que es la única evidencia escrita de la intención
> original. Donde la motivación no pudo verificarse, se dice.
>
> **Estado de todos los ADR:** aceptado e implementado, salvo indicación contraria.

---

## ADR-001 · MongoDB documental en lugar de un motor relacional

**Contexto.** El dato origen son planillas Excel del servicio (`Documentacion/excel_details.txt`,
`2026 - Directorio SLEP Llanquihue.xlsx`) con estructura irregular: columnas que aparecen y
desaparecen entre versiones, bloques opcionales (un establecimiento puede tener Starlink, BAM,
ambos o ninguno), listas de longitud variable (impresoras, anexos telefónicos) y celdas con
texto libre donde se esperaría un número. El equipo venía de contexto relacional
(`implementation_plan_iter1.md` §1 lo dice explícitamente).

**Decisión.** MongoDB, modelando cada establecimiento como un documento que **embebe
subdocumentos tipados** en vez de normalizar en tablas.

**Consecuencias.**
- La ficha completa se arma con **una sola lectura** (`establishments.find_one({rbd})`), sin joins.
- Los bloques opcionales no requieren tablas con filas ausentes ni columnas nulas.
- Las listas variables (`bam[]`, `printers.owned[]`) son naturales.
- **No hay integridad referencial.** `counterparts.rbd` y `metrics.rbd` apuntan a
  `establishments.rbd` sin que nada lo garantice. `POST /api/counterparts` acepta un `rbd`
  inexistente (`02` §3.4).
- **No hay validación de esquema en la base.** Pydantic valida en la frontera de la aplicación;
  un `updateMany` directo en Mongo puede escribir cualquier forma.
- Las agregaciones son pipelines de `$lookup`, más verbosos y menos optimizables que un `JOIN`.
- Cambiar el esquema no requiere migración — y por eso tampoco hay historial de esquema.

**Alternativas descartadas.** PostgreSQL normalizado: habría dado integridad referencial y
validación de tipos, al costo de ~8 tablas, migraciones para cada columna nueva de planilla, y
un `JOIN` de varias tablas para armar cada ficha. PostgreSQL con columnas `JSONB`: habría
conservado la integridad del núcleo y la flexibilidad de los bloques; es la alternativa más
seria y no hay registro de que se evaluara.

> ⚠️ **NO VERIFICADO:** no existe registro escrito de que se hayan comparado alternativas. Esta
> reconstrucción infiere la motivación de la forma del dato y del comentario de
> `implementation_plan_iter1.md` §1.

> 🧭 **Reevaluación (F2, feature de usuarios e IAM): se mantiene MongoDB.** Se evaluó migrar
> a PostgreSQL por la gestión de usuarios y unidades. Se descartó: filtrar datos por unidad es
> lógica de aplicación en cualquier motor, y migrar invalidaría todos los tests BE/INT, que
> mockean `db_service.db`. La jerarquía de unidades se resuelve con ruta materializada
> (ADR-010), sin recursión. **Motivos que reabren esta decisión:** reportes habituales que
> crucen 3 o más colecciones; 2 o más escrituras multi-colección que la regla de negocio exija
> atómicas; permisos heredados que obliguen a consultas recursivas; o la llegada de un segundo
> SLEP. Hoy ninguno se cumple. Nota: `selloverde` usa PostgreSQL y eso no afecta a esta
> decisión, porque las plataformas no comparten base (ADR-009 y `04` §10).

---

## ADR-002 · `counterparts` como colección separada con discriminador `role`

**Contexto.** El modelo inicial (descrito y descartado en `implementation_plan_iter1.md` §1)
tenía las contrapartes como un objeto con **más de 20 campos fijos** dentro del establecimiento:
`territorial`, `territorial_email`, `territorial_phone`, `rrhh`, `rrhh_email`… Dos problemas
concretos: agregar un rol significaba tres campos nuevos en el esquema del establecimiento, y
la pregunta operativa real del servicio — *"¿quiénes son todos los encargados TI de la red?"* —
no se podía responder sin recorrer los 78 documentos.

**Decisión.** Colección `counterparts` independiente, donde **cada documento es una asignación**
(`rbd` + `role` + `origin` + datos de contacto) y el campo `role` actúa como discriminador
tipado (`CounterpartRole`, un `(str, Enum)` de 17 valores). `origin` distingue si la persona
pertenece al establecimiento o al SLEP.

**Consecuencias.**
- Agregar un rol es **agregar un valor a un enum**. Cero cambios de esquema.
- La consulta transversal es directa: `db.counterparts.find({role: "TI"})`.
- La ficha requiere una segunda consulta — el frontend lo resuelve con
  `Promise.all([...])` (`FichaEstablecimiento.jsx:39-41`).
- La validación del rol la hace Pydantic en la frontera: un valor fuera del enum devuelve `422`
  sin tocar la base.
- **Se modela la relación, no la persona.** Un profesional que atiende cinco establecimientos
  son cinco documentos con el mismo nombre y correo. No hay entidad "persona" ni deduplicación.
- **Duplicación del director**: se sigue guardando en `general_info.director` *además* de como
  contraparte (`02` §4.1). Es deuda conocida (D7), no parte de la decisión.
- El discriminador es hoy un enum sin índice propio (`02` §3.4): la consulta que justifica la
  decisión hace collection scan.

**Alternativas descartadas.** Mantener los campos fijos (el problema que se resolvía). Embeber
un array de contrapartes dentro del establecimiento: habría evitado la segunda consulta, pero
la búsqueda transversal habría requerido `$unwind` sobre todos los documentos — precisamente el
caso de uso que motivó el cambio. Una colección `personas` normalizada más una tabla de
asignaciones: correcto si alguna vez se necesita "todos los EE que atiende Fulano" por identidad
y no por nombre literal; se descartó por sobre-ingeniería para el uso actual.

---

## ADR-003 · `metrics` como colección versionada por `(rbd, year)`

**Contexto.** El modelo inicial tenía `metrics` como un bloque plano dentro del establecimiento,
con los años codificados **en el nombre del campo**: `matricula_2022`, `matricula_2023`,
`matricula_2026`… Cada año nuevo era un campo nuevo en el esquema, y comparar años requería
saber de antemano qué campos existían. La huella sigue visible en el seeding
(`seed_service.py:67,94`), que lee exactamente esas claves.

**Decisión.** Colección `metrics` con **clave compuesta de negocio `(rbd, year)`** e índice
único sobre ella. Un documento por establecimiento y año.

**Consecuencias.**
- **Un año nuevo es un documento nuevo, no un campo nuevo.** El esquema no cambia jamás por el
  paso del tiempo.
- El índice único `(rbd, year)` impide dos registros del mismo año a nivel de base de datos.
- Las series temporales son una consulta ordenada (`find({rbd}).sort("year", 1)`).
- Las agregaciones por año son un `$match: {year: N}` sobre un índice.
- El histórico se **carga incompleto**: los años 2022-2025 se siembran con 5 de los 26 campos
  (`seed_service.py:94-105`), y los defaults de Pydantic los rellenan con ceros
  indistinguibles de datos reales (`02` §5).
- La ficha requiere una tercera consulta.
- **El punto de extensión no funciona solo**, porque `analytics_service` hardcodea `2026` en sus
  pipelines (`analytics_service.py:10,48,74`, D6). Registrar 2027 no bastará para que el dashboard
  lo muestre.

**Alternativas descartadas.** Mantener los campos con sufijo de año (el problema). Un array
embebido de métricas por año dentro del establecimiento: habría evitado la tercera consulta,
pero crece sin techo dentro del límite de 16 MB por documento y obliga a traer toda la historia
para leer un año.

---

## ADR-004 · `OwnedPrinter` y `LeasedPrinter` como sub-modelos separados

**Contexto.** El servicio tiene impresoras de dos regímenes con atributos **disjuntos**. Las
propias importan por su licitación y fecha de vencimiento de garantía. Las arrendadas importan
por su número de serie, orden de compra del equipo y de la bandeja, contacto de soporte del
proveedor, dirección IP, contador inicial y ubicación física. El modelo previo tenía un solo
bloque incompleto (`implementation_plan_iter1.md` §1 lo señala como problema).

**Decisión.** Dos modelos Pydantic distintos bajo `Printers {owned: [], leased: []}`
(`establishments_entity.py:5-38`), cada uno con los campos que su régimen realmente tiene.

**Consecuencias.**
- Ningún campo nulo por no aplicar: un `LeasedPrinter` no tiene `licitation` porque no existe
  el concepto.
- La distinción es explícita en el árbol de datos y en la UI (pestaña de inventario de la ficha).
- Agregar un tercer régimen (comodato, donación) requiere un sub-modelo y una clave nuevos en
  `Printers` — no es un discriminador extensible como el de `counterparts`.
- `test_BE08_lifecycle_verification` cubre específicamente que `licitation` sea opcional en
  `OwnedPrinter`.

**Alternativas descartadas.** Un modelo único con todos los campos y un discriminador `regime`,
al estilo `counterparts`: habría sido extensible, al costo de que la mitad de los campos fueran
inaplicables en cada instancia. Se prefirió precisión de esquema sobre extensibilidad porque los
regímenes de contratación pública cambian con poca frecuencia.

---

## ADR-005 · Tipar como `str` los campos que vienen de planillas

**Contexto.** Los datos origen son celdas de Excel llenadas a mano durante años. Una celda de
"puntos de red" puede contener `30`, `"30 puntos"` o `"s/i"`. Una de fecha puede tener
`2024-03-01`, `"marzo 2024"` o vacío. Un tipado fuerte habría hecho fallar la validación en
masa durante el seeding.

**Decisión.** Tipar como `str` con default `""` todo campo cuya fuente sea una celda de planilla
de contenido irregular: fechas (`test_date`, `install_date`, `expiry_date`,
`BamEntry.start/term/end`), cantidades textuales (`InternalNetwork.points_count`,
`Connectivity.download_speed_2030`), y `attendance_avg` en métricas.

**Consecuencias.**
- El seeding es robusto: ningún registro se pierde por un valor mal formado.
- **No se puede ordenar ni filtrar por rango** sobre esos campos sin normalizar antes.
- `attendance_avg` no es agregable — el KPI de asistencia no se puede calcular en un pipeline
  (`02` §5). Es el costo más visible de la decisión.
- La normalización queda diferida y sin dueño: nadie sabe cuándo se hará ni quién la valida.

**Alternativas descartadas.** Tipado fuerte con validadores de Pydantic que normalicen al leer:
lo correcto a mediano plazo, descartado por costo inicial. Una etapa de limpieza previa al
seeding: es la opción sana, y no existe porque la conversión planilla → JSON tampoco está
automatizada (`01` §1).

**Criterio para código nuevo:** esta decisión aplica **solo a campos que vienen de planillas**.
Un campo nuevo que nace en el sistema se tipa correctamente desde el principio. Ver `05` §2.3.

---

## ADR-006 · JWT local propio en lugar de Google Workspace

**Contexto.** El objetivo declarado del proyecto incluye "un sistema de gestión de usuario
generalizado conectado al directorio general de Google Workspace de la organización, con gestión
de roles y perfiles configurables".

**Decisión (de hecho, para la iteración actual).** Autenticación local: usuario y contraseña en
la colección `users`, hash bcrypt, JWT HS256 emitido por el propio backend, rol como campo de
texto libre en el documento de usuario.

**Consecuencias.**
- El sistema funciona sin dependencias externas ni configuración de OAuth: se puede desarrollar
  y desplegar de forma autónoma.
- **El objetivo declarado del proyecto no está cumplido.** No hay OAuth, ni sincronización de
  directorio, ni perfiles configurables.
- Existe **un solo usuario**, sembrado, sin endpoint de gestión (`02` §6). Un segundo usuario
  requiere insertarlo a mano en MongoDB.
- El modelo de roles es binario de facto: `admin` o no (`04` §2).
- La migración futura a OIDC/Google es **contenible**: `auth_service.get_current_user` es el
  único punto que el resto del sistema consume, y los controllers solo leen
  `current_user["role"]`. Reemplazar la emisión del token y el origen del usuario no obliga a
  tocar los otros cuatro módulos. Que hoy el rol se relea siempre desde la base
  (`auth_service.py:57`, ver `04` §1) facilita el cambio: el rol nunca dependió del token.
- Hasta que la migración ocurra, los defaults de `JWT_SECRET` y `ADMIN_PASSWORD` (D2) son un
  riesgo activo.

**Alternativas descartadas.** OAuth 2.0 con Google como proveedor de identidad: es el destino
declarado, diferido por costo de configuración y por no bloquear el desarrollo del núcleo del
sistema. Sesiones con cookie `HttpOnly` en vez de JWT en `localStorage`: más resistente a XSS,
descartado sin registro escrito (ver la brecha de `04` §1).

> ⚠️ **NO VERIFICADO:** que el diferimiento haya sido una decisión deliberada y no simplemente
> trabajo pendiente. Esta reconstrucción lo registra como decisión porque el sistema es
> coherente y está desplegado con autenticación local, no porque exista evidencia escrita.

> 🧭 **Enmienda (F2): el objetivo declarado pasa a ser el plan, con tres cambios.**
> 1. **`auth` deja de ser dueño de `users`.** La identidad vive en el módulo `users`; `auth`
>    solo verifica credenciales y emite tokens (ADR-013).
> 2. **El rol deja de ser un campo de texto libre** en el usuario y pasa a `users.access[]`
>    por plataforma (ADR-009).
> 3. **Google se integra verificando el `id_token` en el backend**, con alta solo por
>    invitación y restricción de dominio (`04` §9.6). No se usa authorization code flow ni
>    se sincroniza el directorio de Workspace.
>
> Se mantienen: bcrypt, JWT HS256 para la sesión propia de este sistema, relectura del usuario
> en cada request (sin ventana de propagación) y el token en `localStorage` (brecha de `04` §1,
> sin cambio). La sesión interna nunca sale de este sistema; los tokens para otras
> plataformas son otro mecanismo, diseñado en F7 (`04` §10).

---

## ADR-007 · Organización modular por dominio (estilo NestJS) en FastAPI

**Contexto.** FastAPI no impone estructura. La convención más común de la comunidad es agrupar
por capa técnica (`routers/`, `models/`, `schemas/`, `crud/`), lo que dispersa un dominio en
cuatro carpetas.

**Decisión.** Agrupar por dominio: una carpeta por módulo con exactamente tres archivos de
nombre predecible (`*_entity.py`, `*_service.py`, `*_controller.py`), registrados en `main.py`
con `include_router`. El propio `implementation_plan_iter1.md` §3 lo rotula "NestJS-like".

**Consecuencias.**
- Todo lo de un dominio está en una carpeta. Cambiar establecimientos no abre `counterparts`.
- La estructura es **mecánicamente predecible**, que es lo que permite que la receta de
  `05` §1 sea seguible sin leer código existente — el requisito explícito para que un agente
  de IA extienda el sistema.
- Las responsabilidades por capa son claras y los límites, verificables por inspección de los
  imports (`05` §3).
- El vocabulario es de NestJS, no de FastAPI: un desarrollador Python puede buscar `routers/` y
  no encontrarlo. "Controller" y "entity" no son términos del ecosistema FastAPI.
- No hay inyección de dependencias real: los services son singletons instanciados al final de su
  archivo e importados directamente. Sencillo, pero no permite sustituirlos en tests sin
  `patch`.
- `analytics` rompe el patrón: no tiene `_entity.py`, porque no persiste entidades propias — y
  esa es exactamente la razón por la que sus dos endpoints quedaron sin `response_model` (D11).

**Alternativas descartadas.** La estructura por capas del tutorial de FastAPI: descartada por
dispersión. Arquitectura hexagonal con puertos y adaptadores: sobre-ingeniería para cinco
módulos CRUD con un solo adaptador de persistencia.

---

## ADR-008 · El frontend consume rutas relativas, sin URL de API configurable

**Contexto.** La SPA y la API se despliegan siempre juntas, detrás del mismo origen.

**Decisión.** Los componentes llaman `axios.get('/api/...')` con rutas **relativas**. El
enrutamiento lo resuelve un proxy: `server.proxy` de Vite en desarrollo
(`vite.config.js` → `http://backend:8000`), `location /api/` de Nginx en producción
(`nginx.conf` → `proxy_pass http://backend:8000`). **No existe `VITE_API_URL`.**

**Consecuencias.**
- Cero configuración de entorno en el frontend. El build es idéntico en dev y prod.
- Mismo origen en el navegador: CORS es irrelevante para el frontend propio, y el `allow_origins=["*"]`
  del backend solo afecta a clientes externos (`04` §5).
- Apuntar la SPA a otro backend exige cambiar el proxy, no el código — lo que es cómodo para
  desplegar y **incómodo para desarrollar el frontend contra un backend remoto**.
- El backend **no puede desplegarse en un dominio distinto** sin cambiar la configuración del
  proxy o introducir la variable que hoy no existe.
- No hay capa de cliente API en el frontend: cada componente construye su llamada. Catorce
  llamadas repartidas en seis componentes, sin un lugar único donde cambiar el prefijo si algún
  día se introduce `/api/v1` (`03` §3.1). Es el costo directo de esta decisión.

**Alternativas descartadas.** `VITE_API_URL` con URL absoluta: más flexible, exige build por
entorno y configuración de CORS real. Un módulo `src/lib/api.js` con una instancia de axios
configurada: compatible con esta decisión y mejor que el estado actual — no se hizo, y es lo que
convendría introducir junto con el versionado de la API.

> 🧭 **Nota (F2):** la feature de usuarios crea `frontend/src/lib/api.js` solo para las
> pantallas nuevas, sobre el `axios` global (reutiliza la cabecera `Authorization` y el
> interceptor 401 de `App.jsx`). Los componentes existentes no se migran. Ver D19 en `05` §5.

---

> **ADR-009 a ADR-014 (F2).** Decisiones de la feature de gestión de usuarios, unidades y
> acceso centralizado. **Estado: aceptadas, pendiente de implementar** (se aprobaron el
> 2026-10-02). Hasta que cada fase las implemente y las verifique con tests, el código no las
> cumple; las secciones de `02`, `03` y `04` que las desarrollan llevan la marca `🧭 DISEÑO`.

## ADR-009 · Acceso por plataforma y roles; `iam` como plataforma lógica; `ScopeFilter` diferido

**Contexto.** El control de acceso actual es un `if` en un solo punto
(`establishments_controller.py:40`, `current_user.get("role") == "admin"`) y el rol es texto
libre en el documento de usuario. Resultado: cualquier autenticado escribe todo (D3) y el `PUT`
devuelve credenciales sin redactar (D4) (`04` §2). Además, el SLEP opera más de una plataforma
(`datos` y `selloverde`) y ninguna debería tener su propia gestión de usuarios.

**Decisión.**
1. Cada usuario tiene `access[]`: entradas `{platform_id, role, granted_at, granted_by}`, una
   por plataforma. Los roles válidos de cada plataforma salen de la colección `platforms`
   (`02` §9). Roles de `datos` y `selloverde`: `admin` (ver, editar y eliminar), `editor`
   (ver y editar) y `viewer` (solo ver).
2. **`iam` es una plataforma lógica** con el único rol `admin`. El admin global es quien tiene
   `iam/admin`. No hay campo booleano ni concepto nuevo. **`iam/admin` y `datos/admin` son
   roles distintos** (separación de funciones): solo `iam/admin` crea usuarios, gestiona
   unidades y accesos y ejecuta operaciones masivas.
3. La autorización se resuelve con una **dependencia de FastAPI**
   `require_access(platform, roles) -> AccessContext`, definida en `auth`. El controller recibe
   `AccessContext {user_id, role}`. **El service nunca recibe el usuario** (L3): sigue
   recibiendo booleanos como `include_sensitive`.
4. Matriz de `datos` en `04` §9.3. El rol `editor` ve las credenciales en claro igual que
   `admin`; solo `viewer` las recibe redactadas (lectura de la respuesta N10; confirmada por el usuario el 2026-10-06: esas credenciales son de uso público).
5. **El filtro de alcance por unidad (`ScopeFilter`) queda diferido** hasta el primer módulo que
   filtre datos por unidad. En esta feature no hay restricción de visibilidad por
   establecimiento ni por unidad: los roles limitan acciones, no filas.

**Consecuencias.**
- Cierra D3 y D4. Un `viewer` recibe `403` en toda escritura, y el `PUT` queda cubierto por test.
- Un usuario que solo tiene acceso a `selloverde` se autentica pero recibe `403` en `datos`;
  `GET /api/auth/me` devuelve `role: "none"` para él (contrato aditivo, `03` §8.2).
- Toda ruta declara `require_access` o está en una allowlist explícita; un test recorre
  `app.routes` para exigirlo (`04` §9.7).
- El rol sigue sin viajar en el token como fuente de verdad: se relee el usuario en cada
  request (`04` §1), así que revocar un acceso surte efecto en la siguiente petición.
- El `role` de la raíz del documento se mantiene como compatibilidad durante la migración y se
  retira después.
- Los 12 endpoints de datos existentes (establecimientos, contrapartes, métricas y analytics) cambian de `Depends(get_current_user)` a
  `Depends(require_access("datos", …))`. Es un cambio de comportamiento deliberado, no un
  refactor.

**Alternativas descartadas.** Librería de RBAC (casbin u otras): tres roles por plataforma se
resuelven con un `set`. Un booleano `is_global_admin`: crea un concepto paralelo al de acceso.
Un único rol por usuario: no sirve con varias plataformas. Implementar `ScopeFilter` ya: ningún
requisito de esta feature lo necesita y agregaría una capa sin problema que resolver.

---

## ADR-010 · Unidades jerárquicas y subrogancias

**Contexto.** Los funcionarios del SLEP pertenecen a una estructura organizacional de cinco
niveles (23 unidades hoy, `02` §9.2). Los nombres se repiten entre niveles («Gestión
Territorial» es subdirección y unidad), así que el nombre no sirve como identificador. La
jefatura puede ser reemplazada temporalmente.

**Decisión.**
1. Colección `units` con `level` estricto de 1 a 5, `code` único y estable, `parent_id` y
   **`ancestors` materializado** (ruta desde la raíz). Un subárbol se consulta con
   `{ancestors: <id>}` y un índice multikey; no se usa `$graphLookup` ni recursión.
2. Reglas de nivel: exactamente una unidad de nivel 1 sin padre; las de nivel 2 y 3 cuelgan de
   la de nivel 1; las de nivel 4 de una de nivel 3; las de nivel 5 de una de nivel 4. Una unidad
   de nivel 2 no tiene hijas. El nombre es único **entre hermanas** `(parent_id, name)`, no
   global. El nivel es el invariante; el nombre es un dato.
3. El service recalcula `ancestors` al crear o mover, y mover reescribe el de todo el subárbol.
   No se desactiva una unidad con usuarios activos ni con hijas activas.
4. **Seed** en `units_service.ensure_bootstrap_units()` desde una **constante del módulo**, no
   un `.json` (los `.json` de `Documentacion/` se ignoran en git, y este dato es de código).
5. **`subrogations` es una colección aparte**, propiedad del módulo `units`: el historial crece
   sin límite. La subrogancia «vigente» se calcula por fecha en la consulta; no hay jobs.
   **Solo da visibilidad y no transfiere permisos.**

**Consecuencias.**
- Un módulo es dueño de dos colecciones (`units`, `subrogations`). Es una excepción acotada a la
  convención de ADR-007, y se registra aquí.
- `units` no puede importar `users` (ADR-013): lo que necesita de `users` llega como parámetro
  calculado por el controller.
- Mover una unidad es una escritura multi-documento no transaccional. A esta escala (23
  unidades) el riesgo de dejar `ancestors` a medias es bajo y se mitiga recalculando en una
  sola pasada; si la jerarquía creciera, sería uno de los motivos para reabrir ADR-001.
- Los códigos de las 23 unidades son una propuesta validada por el usuario.

**Alternativas descartadas.** Solo `parent_id` con consulta recursiva: obliga a `$graphLookup`
o a varias lecturas por subárbol. Árbol anidado embebido en un documento: no se puede indexar
por unidad ni actualizar un nodo sin reescribir el árbol. Subrogancia embebida en la unidad:
el array crece sin techo. Un job que active y cierre períodos: «vigente» por fecha no lo necesita.

---

## ADR-011 · Vínculo opcional entre contraparte y usuario (enmienda a ADR-002)

**Contexto.** Una contraparte es una asignación `(rbd, role, origin, persona)`; la persona puede
ser o no usuario de la plataforma. Saber cuáles lo son permite, por ejemplo, ofrecerles acceso.

**Decisión.** `counterparts` gana `user_id: Optional[str] = None`. El vínculo **nunca es
obligatorio**. Un usuario puede estar vinculado a muchas contrapartes (un profesional del SLEP
atiende varios establecimientos). El backfill de los datos existentes es un script con modo
dry-run por defecto que empareja por correo normalizado; los casos ambiguos y los registros sin
correo se reportan y no se vinculan. `counterparts_service` valida el `user_id` a través de
`users_service` (L5).

**Consecuencias.** **ADR-002 sigue vigente:** se modela la relación y no la persona; el vínculo
es una referencia opcional, no una entidad «persona». La respuesta de contrapartes expone solo
`user_id`, nunca datos del usuario. El campo es no-breaking (`03` §4). La duplicación de
datos de contacto entre `counterparts` y `users` no se resuelve aquí.

**Alternativas descartadas.** Colección `personas` y tabla de asignaciones (descartada en
ADR-002, sigue siendo sobre-ingeniería). Hacer obligatorio el vínculo: la mayoría de las
contrapartes de establecimiento no serán usuarios. Fusionar contrapartes y usuarios: mezcla
una asignación con una cuenta.

---

## ADR-012 · Primer acceso por correo y módulo de envío `mail_service`

**Contexto.** La contraseña no debe viajar por correo, y las altas serán masivas (CSV). El
sistema no envía correo hoy. El cliente OAuth de Google (`GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`) ya existe para el login.

**Decisión.**
1. **Primer acceso y restablecimiento con un enlace de un solo uso.** Colección `auth_tokens`
   (propiedad de `auth`) con `purpose` `invite` o `reset`. El token es
   `secrets.token_urlsafe(32)`, viaja solo en el correo y en la base se guarda su
   `sha256`. Un índice TTL sobre `expires_at` borra los vencidos. Emitir un token nuevo
   invalida el anterior del mismo usuario y propósito. El canje es una actualización condicional
   atómica (`used_at: null` y `expires_at > ahora`). Todo fallo de canje responde igual.
2. El enlace lleva el token en el **fragmento** (`/definir-contrasena#token=…`) para que no
   llegue a logs de servidor ni a la cabecera `Referer`.
3. **Si el envío falla, el alta no se revierte.** El usuario queda `invited`, la respuesta lo
   informa y el error se guarda en `users.invitation.last_error`, visible para el admin, que
   puede reenviar. En altas masivas las invitaciones salen después de responder
   (`BackgroundTasks`, que corre en el proceso y no es una cola): 200 envíos seguidos no caben en
   el `proxy_read_timeout 120s` de nginx.
4. **Los correos salen con Gmail API**, reutilizando el cliente OAuth existente. Una casilla
   remitente dedicada da su consentimiento **una sola vez** con el scope
   `https://www.googleapis.com/auth/gmail.send`, mediante un script de `backend/scripts/`; el
   refresh token se guarda como secreto (`GMAIL_REFRESH_TOKEN`) y nunca en un archivo del repo.
5. **`mail_service` es infraestructura, no dominio:** `backend/app/mail/mail_service.py`, al
   nivel de `database/`, con un único método `send(to, subject, html, text)`. No sigue la regla
   de los tres archivos. Ningún módulo de dominio sabe que existe Gmail; en los tests se
   mockea `mail_service`, como hoy se mockea `db_service`.
6. Dependencias: `google-auth` para refrescar el access token y `httpx` (asíncrono) para la
   llamada REST a `users.messages.send`. El mensaje se arma con `email.message.EmailMessage`.
   **No se agrega `google-api-python-client`**: es una dependencia grande para una llamada.
   El refresco síncrono de `google-auth` corre fuera del event loop.

7. **Se desarrolla antes de tener credenciales (decisión del 2026-10-02).** El remitente será
   una cuenta aparte que se configura después. Por eso `mail_service` tiene dos modos,
   elegidos por `MAIL_MODE` (obligatoria, sin default): `gmail` (envío real; exige
   `GMAIL_SENDER_ADDRESS`, `GMAIL_REFRESH_TOKEN`, `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`) y
   `console` (escribe el mensaje, con su enlace, en el log; solo para desarrollo). El arranque
   **rechaza `console` si `PUBLIC_BASE_URL` no apunta a `localhost` o `127.0.0.1`**, de modo que
   no pueda quedar activo en producción sin querer. El código y los tests no dependen de
   credenciales (los tests mockean `mail_service`); pasar a `gmail` es solo configuración.
   Cada variable pasa a ser obligatoria en la fase que la usa, no antes.
8. **No hay un endpoint genérico de envío de correo.** Un endpoint que reciba destinatario y
   cuerpo sería un relay abierto sobre la casilla del SLEP. El envío está acoplado a dos
   operaciones del admin global: crear un usuario (`POST /api/users`, `bulk-create`) y
   `POST /api/users/{id}/invitation` (reenvío) o `…/password-reset`. Ambas toman el correo del
   usuario desde su documento, emiten el token y arman el mensaje con **plantillas HTML y de
   texto** que viven en `auth` (con los datos del usuario escapados). `mail_service.send` solo
   lo invoca el código de dominio.

**Consecuencias — riesgos operativos que quedan escritos.**
- **La pantalla de consentimiento del cliente OAuth debe ser de tipo *Internal*.** Si fuera
  *External* en estado *Testing*, Google caduca el refresh token a los 7 días.
- **Si cambia la contraseña de la casilla remitente, Google revoca los tokens con scopes de
  Gmail** y el envío falla hasta repetir el consentimiento. El diseño lo tolera (usuarios
  `invited` y reenvío), pero el fallo queda en el log y en `users.invitation.last_error`.
- **El refresh token da permiso para enviar correo en nombre de la casilla.** Se trata con el
  mismo cuidado que `JWT_SECRET`. Una casilla personal no sirve: al irse su dueño se corta el
  envío para todos.
- Las tareas de la consola de Google y de Workspace las hace una persona, no el código; el
  checklist está en `07` §9.
- Cuotas de Gmail: el envío masivo se limita a 200 por lote (constante) y se hace en serie.

**Alternativas descartadas.** Enviar la contraseña (o una temporal) por correo: contradice el
requisito. SMTP con contraseña de aplicación: otra credencial de larga vida, sin el alcance acotado
que da el scope `gmail.send`. Cuenta de servicio con delegación a nivel de dominio: no
tiene refresh token que caduque, pero exige un permiso de administrador de Workspace sobre
todo el dominio, más amplio que el de una casilla; es la alternativa a evaluar si la gestión
del refresh token resultara costosa. Un proveedor externo (SendGrid y similares): otro
contrato y otro secreto para un volumen bajo.

---

## ADR-013 · Dirección de dependencias entre los módulos de la feature

**Contexto.** L5 permite que un service importe a otro solo hacia abajo y sin ciclos. La feature
introduce dos pares que se necesitan mutuamente: `users ↔ units` (`users` valida `unit_id`;
`units` necesita contar usuarios activos al desactivar una unidad y validar jefatura y
subrogante) y `users ↔ auth` (la invitación escribe `auth_tokens`, de `auth`; `auth` lee
usuarios).

**Decisión.** Un grafo acíclico, de arriba hacia abajo:

```
auth → users → units → audit
            ├→ platforms → audit
            ├→ establishments
            └→ audit
counterparts → users
mail (infraestructura) ← auth
```

1. **`auth → users`.** `auth` importa `users_service`; `users` no importa `auth`. La invitación
   no la emite `users`: la orquesta `auth_service.invite_many`, que el controller de `users`
   llama después de `users_service.create_many`. Las altas del seed y del bootstrap usan
   `create_many` sin invitación.
2. **`users → units`.** `users_service` importa `units_service` (valida que la unidad exista y
   esté activa, y obtiene los ids de un subárbol para filtrar). `units_service` **no importa
   `users`**: lo que necesita de usuarios llega como **parámetro que calcula el controller**
   (por ejemplo `units_service.deactivate(unit_id, active_users=n)`), el mismo patrón que
   `include_sensitive`.
3. `users` importa `platforms` (validar roles), `establishments` (validar `rbd`) y `audit`.
   `audit` no importa a nadie. `counterparts → users` valida `user_id`.
4. Un test recorre los imports de `backend/app` y falla ante un ciclo o una arista no
   declarada aquí.

**Consecuencias.** Dos controllers (`units`, `auth`/`users`) componen la llamada a dos services
en lecturas simples; es el costo de no tener ciclos. Cada nuevo módulo de dominio debe
agregarse a este grafo en su ADR.

**Alternativas descartadas.** Imports dentro de funciones para ocultar el ciclo (lo esconde, no
lo resuelve). Fusionar `units` y `users` (mezcla dos dominios con ciclo de vida distinto).
Duplicar el conteo de usuarios dentro de `units` (rompe la propiedad de la colección `users`,
C2). Que `users` emita las invitaciones (haría que `users` importe `auth`).

---

## ADR-014 · Auditoría y rate limiting sin infraestructura nueva

> **Estado:** aprobada por el usuario el 2026-10-06. Auditoría y rate limiting **entran en F4**.

**Contexto.** `04` §7 registra que no hay ninguna auditoría y que el login admite intentos
ilimitados. Para un sistema de identidad, saber quién dio acceso a quién es un mínimo.

**Decisión.**
1. Colección **`audit_log`**, módulo `audit` de tres archivos. Solo se agregan registros: el
   service no expone ninguna operación que edite o borre. `changes` jamás contiene hashes,
   contraseñas ni tokens. Toda operación masiva comparte un `bulk_id`. Si la escritura de
   auditoría falla, el cambio ya hecho **no se revierte** (no hay transacciones multi-colección
   en este diseño); se registra en nivel CRITICAL y la respuesta lo indica.
2. **Rate limiting** en login, restablecimiento, reenvío y canje de enlaces, con contadores en
   una colección **`rate_limits`** con índice TTL, compartida entre los 2 workers de Gunicorn.
   **Sin Redis.** El límite es por cuenta **e** IP (no bloquea globalmente la cuenta, para que
   un tercero no pueda dejarla inutilizable), responde `429` con `Retry-After` y trata igual a
   las cuentas inexistentes. La IP sale de `X-Forwarded-For`, que nginx ya envía
   (`frontend/nginx.conf:32`); el backend la confía solo desde la red interna
   (`--forwarded-allow-ips` en el comando de Gunicorn).

**Consecuencias.** Dos colecciones nuevas. Un cambio en `Dockerfile.prod` (regla 3). Los límites
efectivos son por cuenta+IP; una IP compartida (por ejemplo, la de una oficina) comparte contador.

**Alternativas descartadas.** Redis (prohibido para esta feature, una pieza más que operar).
Contadores en memoria de cada worker (el límite efectivo se multiplica por el número de
workers). Bloqueo de la cuenta tras N fallos (permite denegación de servicio dirigida).
Auditar lecturas (volumen sin requisito que lo pida).
