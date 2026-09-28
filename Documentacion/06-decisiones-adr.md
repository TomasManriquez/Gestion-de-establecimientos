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
