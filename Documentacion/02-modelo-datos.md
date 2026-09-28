# 02 · Modelo de datos

> **Alcance.** Las cuatro colecciones de MongoDB, su esquema real derivado de los modelos
> Pydantic, sus índices, sus relaciones y el razonamiento documental detrás. Incluye el mapa
> de campos sensibles. No cubre cómo se exponen por HTTP (`03`) ni quién puede verlos (`04`).
>
> **Verificado contra:** `backend/app/*/*_entity.py`, `backend/app/database/database_service.py`,
> `backend/app/database/seed_service.py`, `backend/app/establishments/establishments_service.py`,
> `backend/establishments.json`.

---

## 1. Panorama

Base de datos `slep_llanquihue` (`config.py:6`, override por `DATABASE_NAME`). Cuatro
colecciones:

```mermaid
erDiagram
    establishments {
        ObjectId _id PK
        string rbd UK "clave de negocio"
        string rbd_dv
        string rbd_full
        string name
        string comuna
        string area_type "URBANO | RURAL"
        string address
        object location "lat, lng - opcional"
        object general_info "embebido"
        object connectivity "embebido"
        object printers "embebido"
        array licenses "embebido - SENSIBLE"
    }
    counterparts {
        ObjectId _id PK
        string rbd FK
        string role "enum CounterpartRole"
        string origin "enum CounterpartOrigin"
        string name
        string email
        string phone
    }
    metrics {
        ObjectId _id PK
        string rbd FK
        int year
        int enrollment
        string attendance_avg
        float ive_basica
        float ive_media
        int num_teachers
        int num_assistants
    }
    users {
        ObjectId _id PK
        string username UK
        string hashed_password "SENSIBLE"
        string full_name
        string role "admin | otro"
    }

    establishments ||--o{ counterparts : "rbd"
    establishments ||--o{ metrics : "rbd (1 por año)"
```

**Lo que el diagrama dice y conviene no perder de vista:** la clave que une todo no es el
`ObjectId` de Mongo sino el **`rbd`**, un identificador de negocio externo asignado por el
MINEDUC. `counterparts.rbd` y `metrics.rbd` referencian `establishments.rbd`, no `_id`. No
existe integridad referencial declarada — MongoDB no la ofrece y el código no la simula:
borrar un establecimiento dejaría sus contrapartes y métricas huérfanas (hoy no existe
endpoint de borrado de establecimientos, así que el escenario no es alcanzable por la API).

`users` no tiene relación con las otras tres. Es una colección de autenticación aislada.

---

## 2. Principio de modelado: qué se embebe y qué se referencia

La regla aplicada, y la razón por la que este modelo se ve como se ve:

**Se embebe lo que solo tiene sentido dentro de un establecimiento y se lee siempre junto a él.**
`general_info`, `connectivity`, `printers` y `licenses` no se consultan nunca por sí solos —
no hay una pregunta legítima como "todas las impresoras arrendadas del servicio" que no pase
por el establecimiento. Además su cardinalidad es acotada y no crece con el tiempo. Embebidos
significan una sola lectura para armar la ficha completa.

**Se referencia lo que tiene vida propia o crece indefinidamente.** `counterparts` y `metrics`
son colecciones separadas por dos razones distintas, no por una:

- `counterparts` porque se consulta **transversalmente**: "todos los encargados TI de la red"
  es una pregunta real y frecuente, y embebida sería un `$unwind` sobre 78 documentos. Ver
  `06-decisiones-adr.md` ADR-002.
- `metrics` porque **crece un documento por año y por establecimiento, para siempre**. Embebido
  sería un array que crece sin techo dentro de un documento con límite de 16 MB, y obligaría a
  traer toda la historia para leer el año actual. Ver ADR-003.

El criterio para una entidad nueva es ese, en ese orden: *¿se consulta sin su establecimiento?*
→ colección. *¿crece sin límite?* → colección. Si ninguna de las dos, se embebe.

---

## 3. `establishments`

Origen del esquema: `backend/app/establishments/establishments_entity.py`.

### 3.1 Nivel raíz — `Establishment`

| Campo | Tipo | Default | Notas |
|---|---|---|---|
| `rbd` | `str` | requerido | Clave de negocio. Índice único. **Es string, no int**, aunque el dato sea numérico. |
| `rbd_dv` | `str` | `""` | Dígito verificador. |
| `rbd_full` | `str` | requerido | Formato `7722-3`. En el seeding cae a `f"{rbd}"` si falta (`seed_service.py:197`). |
| `name` | `str` | requerido | Índice simple. |
| `comuna` | `str` | requerido | Índice compuesto con `area_type`. |
| `area_type` | `str` | requerido | `URBANO` / `RURAL`. **Sin `Enum`** — es texto libre validado solo por convención. |
| `address` | `str` | requerido | |
| `location` | `Location \| None` | `None` | `{lat: float, lng: float}`. Poblado por el script KMZ. |
| `general_info` | `GeneralInfo` | instancia vacía | Embebido 1:1. |
| `connectivity` | `Connectivity` | instancia vacía | Embebido 1:1. |
| `printers` | `Printers` | instancia vacía | Embebido: `{owned: [], leased: []}`. |
| `licenses` | `List[LicenseCredential]` | `[]` | **Embebido y sensible.** |

### 3.2 Sub-esquemas embebidos

```mermaid
classDiagram
    class Establishment {
        +rbd: str
        +rbd_full: str
        +name: str
        +comuna: str
        +area_type: str
        +address: str
        +location: Location?
    }
    class Location {
        +lat: float
        +lng: float
    }
    class GeneralInfo {
        +director: str
        +director_email: str
        +director_phone: str
        +category: str
        +covertura: str
        +adp: str
        +pame: str
        +uni_bi_tridocente: str
        +microcentro: str
        +coordinador_microcentro: str
        +detalle_niveles_combinados: str
        +nivel_transicion_nt: str
        +priorizado_asistencia: str
        +distancia_cafra: str
    }
    class Connectivity {
        +internet_provider: str
        +internet_status: str
        +ssid: str
        +ssid_password: str
        +test_date: str
        +download_speed_2030: str
        +phone_extensions: str[]
    }
    class BamEntry {
        +number: str
        +oc: str
        +imei: str
        +device: str
        +holder: str
        +start: str
        +term: str
        +end: str
    }
    class Starlink {
        +installed: bool
        +date: str
    }
    class InternalNetwork {
        +installed_year: str
        +points_count: str
        +status: str
        +obs: str
    }
    class Printers {
        +owned: OwnedPrinter[]
        +leased: LeasedPrinter[]
    }
    class OwnedPrinter {
        +model: str
        +qty: int
        +type: str
        +provider: str
        +licitation: str
        +expiry_date: str
        +obs: str
    }
    class LeasedPrinter {
        +type: str
        +brand: str
        +model: str
        +serie: str
        +location: str
        +support_contact: str
        +ip_address: str
        +install_date: str
        +initial_counter: int
    }
    class LicenseCredential {
        +name: str
        +email: str
        +password: str
        +url: str
        +obs: str
        +is_new: bool
    }

    Establishment o-- Location
    Establishment *-- GeneralInfo
    Establishment *-- Connectivity
    Establishment *-- Printers
    Establishment *-- "0..*" LicenseCredential
    Connectivity *-- "0..*" BamEntry
    Connectivity *-- Starlink
    Connectivity *-- InternalNetwork
    Printers *-- "0..*" OwnedPrinter
    Printers *-- "0..*" LeasedPrinter
```

Dos detalles del diagrama que no se ven a simple vista pero determinan el comportamiento:

**Casi todo es `str`, incluso lo que parece numérico o de fecha.** `InternalNetwork.points_count`
es un string, `Connectivity.download_speed_2030` es un string, todas las fechas
(`test_date`, `install_date`, `expiry_date`, `BamEntry.start/term/end`) son strings. Esto es
deliberado: el dato viene de planillas donde una celda puede contener `"30"`, `"30 puntos"` o
`"s/i"`, y tipar fuerte habría hecho fallar el seeding masivamente. El costo es que no se puede
ordenar ni filtrar por rango sobre esos campos sin normalizar primero. Ver ADR-005.

**Los defaults mutables son instancias compartidas.** `Connectivity.starlink: Starlink = Starlink()`
(`establishments_entity.py:69`) evalúa el default una sola vez al importar el módulo. Pydantic v2
hace copia profunda de los defaults al instanciar, así que en la práctica no hay fuga entre
instancias — pero es un patrón que en Pydantic v1 o en dataclasses puras sería un bug clásico.
Quien copie este estilo a otro módulo debe saber por qué funciona.

### 3.3 Variantes del modelo

`establishments_entity.py` declara cuatro modelos sobre la misma entidad, y la distinción es
central para todo lo demás:

| Modelo | Uso | Campos |
|---|---|---|
| `Establishment` | Respuesta del detalle y del PUT | Todo, incluido `licenses` |
| `EstablishmentUpdate` | Body del PUT | Los mismos que `Establishment` menos `rbd`/`rbd_dv`/`rbd_full`, **todos `Optional` con default `None`** |
| `EstablishmentSummary` | Ítem del listado | `rbd`, `rbd_full`, `name`, `comuna`, `area_type`, `address`, `category`, `adp`, `covertura` |
| `EstablishmentListResponse` | Envoltorio del listado | `items`, `total`, `page`, `page_size`, `total_pages` |

`EstablishmentSummary` **aplana** tres campos: `category`, `adp` y `covertura` viven dentro de
`general_info` en el documento, pero salen al mismo nivel en el listado. Ese aplanamiento lo
hace el service a mano (`establishments_service.py:70-73`), no Pydantic. Es el punto exacto
donde un campo nuevo de `general_info` que deba aparecer en el directorio necesita tres
cambios coordinados: la proyección, el aplanamiento y el modelo.

> 🔸 **BRECHA:** `EstablishmentSummary` no incluye `location`, y `LISTING_PROJECTION`
> (`establishments_service.py:6-17`) tampoco lo proyecta. Un mapa con todos los establecimientos
> del directorio requeriría hoy 78 llamadas al endpoint de detalle. El mapa existente
> (`EstablishmentMap.jsx`) es por eso de un solo establecimiento, alimentado desde la ficha.

### 3.4 Índices

`database_service.py:37-56`, función `ensure_indexes()`:

| Colección | Índice | Opciones | Motivo |
|---|---|---|---|
| `establishments` | `rbd` | **unique** | Clave de negocio; garantiza unicidad y acelera el detalle |
| `establishments` | `(comuna, area_type)` | compuesto | Filtros combinados del directorio |
| `establishments` | `name` | simple | Orden por defecto del listado (`sort("name", 1)`) |
| `establishments` | `general_info.category` | simple | Filtro por categoría |
| `counterparts` | `rbd` | simple | Contrapartes de una ficha |
| `counterparts` | `(rbd, role)` | compuesto | Búsqueda de un rol en un EE |
| `metrics` | `(rbd, year)` | **unique**, `year` descendente | Clave compuesta de negocio; impide dos registros del mismo año |
| `metrics` | `year` | simple | `$match: {year: 2026}` de los pipelines de analytics |

Todos con `background=True`.

> 🔸 **BRECHA:** no hay índice sobre `counterparts.role` por sí solo. La consulta transversal
> que justifica la existencia de la colección ("todos los TI de la red", ver ADR-002) hace
> hoy un collection scan. A 78 establecimientos es irrelevante; es el primer índice a agregar
> si esa consulta se expone como endpoint.
>
> 🔸 **BRECHA:** no existe índice único sobre `(rbd, role, origin)` en `counterparts`. El
> `POST /api/counterparts` no valida duplicados, así que la API permite crear dos directores
> para el mismo establecimiento. El seeding sí se protege con un `seen_roles` en memoria
> (`seed_service.py:137`), pero esa protección no existe en tiempo de ejecución.

---

## 4. `counterparts`

Origen: `backend/app/counterparts/counterparts_entity.py`.

```mermaid
classDiagram
    class Counterpart {
        +_id: ObjectId
        +rbd: str
        +role: CounterpartRole
        +origin: CounterpartOrigin
        +name: str
        +email: str
        +phone: str
    }
    class CounterpartRole {
        <<enumeration>>
        DIRECTOR
        UTP_JEFE
        PIE_ENCARGADO
        CONVIVENCIA_ESCOLAR
        INSPECTOR_GENERAL
        SIGE_ENCARGADO
        TERRITORIAL
        RRHH
        INFRAESTRUCTURA
        COMPRAS
        TI
        PAME
        PROFESIONAL_INCLUSION
        PROFESIONAL_AME_NT
        PERSONAL_PROCESOS_ADM
        GESTOR_INFRAESTRUCTURA
        COMPRADOR
    }
    class CounterpartOrigin {
        <<enumeration>>
        ESTABLECIMIENTO
        SLEP
    }
    Counterpart --> CounterpartRole
    Counterpart --> CounterpartOrigin
```

Cada documento es **una asignación**, no una persona: un profesional del SLEP que atiende
cinco establecimientos aparece como cinco documentos con el mismo `name` y `email`. No hay
entidad "persona" ni deduplicación. Es la consecuencia directa de modelar la relación y no
las entidades — aceptable mientras nadie necesite "todos los EE que atiende Fulano"
consultando por identidad en vez de por nombre literal.

`role` es el **discriminador**: agregar un tipo de contraparte es agregar un valor al `Enum`,
no una columna ni un campo nuevo. `origin` responde a quién emplea a esa persona, y es lo que
permite separar la ficha en "contrapartes del establecimiento" y "contrapartes del SLEP".

`Counterpart` (`counterparts_entity.py:46-50`) expone `_id` como `id` vía
`Field(..., alias="_id")` + `populate_by_name = True`. **El JSON de salida usa `_id`**, no `id`,
porque FastAPI serializa por alias. El frontend lo consume así (`EditFicha.jsx:179,194`).

### 4.1 El mapeo de seeding, y por qué es frágil

`seed_service.py:109-190` traduce el bloque `counterparts` plano de `establishments.json`
a documentos tipados. Tiene tres partes que conviene conocer antes de tocarlo:

1. **`role_mappings`** (`:113-128`): diccionario de `campo_en_json → (ROLE, ORIGIN)`. Catorce
   roles fijos. Para cada uno busca además `{campo}_email` y `{campo}_phone`.
2. **`year_variant_roles`** (`:133-135`): solo `territorial`. El dato origen trae claves con
   sufijo de año (`territorial_2026`) porque el profesional rota. El código ordena las claves
   candidatas en reversa para preferir la más reciente, en vez de hardcodear el año. Es el
   único lugar del backend que resuelve una clave dinámicamente.
3. **El director** (`:181-190`) no viene del bloque `counterparts` sino de
   `general_info.director`. Se inserta como contraparte `DIRECTOR`/`ESTABLECIMIENTO` **y**
   permanece duplicado dentro de `general_info` del establecimiento.

> 🔸 **BRECHA (duplicación conocida):** el director existe en dos lugares —
> `establishments.general_info.director` y un documento en `counterparts`. Editar uno no
> actualiza el otro. El frontend lee el de `general_info` en la cabecera de la ficha y el de
> `counterparts` en la pestaña de contrapartes, así que pueden divergir visiblemente.
>
> 🔸 **BRECHA:** `role_mappings` descarta el valor literal `"-"` como "sin dato"
> (`seed_service.py:142`). Ese centinela no está documentado en ninguna parte del modelo
> y no se aplica en ningún otro campo.

---

## 5. `metrics`

Origen: `backend/app/metrics/metrics_entity.py`.

Clave compuesta de negocio **`(rbd, year)`**, con índice único. Un documento por
establecimiento y año. 26 campos, agrupables en:

| Grupo | Campos | Tipo |
|---|---|---|
| Clave | `rbd`, `year` | `str`, `int` |
| Matrícula y dotación | `enrollment`, `num_teachers`, `num_assistants` | `int` |
| Asistencia | `attendance_avg` | **`str`** |
| Vulnerabilidad | `ive_basica`, `ive_media` | `float` |
| Resultados de curso | `grade_avg`, `promoted`, `failed`, `transferred`, `dropouts` | `float`/`int` |
| Categoría de desempeño | `desempeno_basica`, `desempeno_media` | `str` |
| Prueba de admisión | `ptje_nem`, `ptje_ranking`, `score_lectura`, `score_matematica1`, `score_matematica2`, `score_historia`, `score_ciencia`, `total_rendidores` | `float`/`int` |
| Tasas derivadas | `tasa_promocion`, `tasa_reprobacion`, `tasa_desercion`, `tasa_retencion` | `float` |

Salvo `rbd`, `year` y `enrollment`, todos son `Optional` con default numérico `0` o `0.0`.
Eso significa que **un cero no distingue "valor real cero" de "sin dato"**: un establecimiento
sin educación media tiene `ive_media = 0.0` igual que uno cuyo IVE no se ha cargado. Toda
agregación sobre estos campos hereda esa ambigüedad.

Las tasas (`tasa_*`) son **derivadas y almacenadas**, no calculadas al vuelo. Vienen ya
computadas desde la planilla origen. Nada en el backend verifica que `tasa_promocion` sea
coherente con `promoted / enrollment`.

`MetricUpdate` (`:36-61`) repite los 24 campos no-clave como `Optional[...] = None`. Es
duplicación literal de `MetricBase`, mantenida a mano.

> 🔸 **BRECHA:** `attendance_avg` es `str` y contiene valores como `"92%"`. No se puede sumar
> ni promediar en un pipeline de agregación sin parseo previo. Es el único campo de la familia
> "porcentaje" que no es `float`, y proviene de que la planilla lo traía formateado.
>
> 🔸 **BRECHA:** el seeding histórico (`seed_service.py:94-105`) inserta los años 2022-2025
> con **solo 5 campos** (`enrollment`, `attendance_avg`, `ive_*`, `num_*`), dejando los 20
> restantes ausentes del documento. Al leerlos por `GET /api/metrics/establishment/{rbd}`,
> `response_model=Metric` los rellena con sus defaults, así que el cliente recibe ceros
> indistinguibles de datos reales. Solo el año 2026 tiene el documento completo.
>
> 🔸 **BRECHA:** `MetricUpdate` duplica la lista de campos de `MetricBase`. Agregar una métrica
> exige editar ambos modelos; olvidar uno hace que el campo sea legible pero no editable, sin
> error visible. Ver `05-guia-de-extension.md` §2.3.

---

## 6. `users`

No tiene modelo Pydantic de persistencia. El documento se define inline en el seeding
(`seed_service.py:23-29`, función `_seed_admin_user`) y se lee como `dict` crudo en
`auth_service.py:25,57`.

```json
{
  "username": "admin",
  "hashed_password": "$2b$12$...",
  "full_name": "Administrador SLEP",
  "role": "admin"
}
```

`auth_entity.py` solo modela el tránsito HTTP (`LoginRequest`, `Token`, `TokenData`,
`UserResponse`), no la persistencia.

> 🔸 **BRECHA:** no existe `users_entity.py`, `users_service.py` ni endpoint de gestión de
> usuarios. El único usuario se crea por seeding con la contraseña de `ADMIN_PASSWORD`. Crear
> un segundo usuario requiere insertarlo a mano en MongoDB. No hay índice único sobre
> `users.username`, pese a que `auth_service.authenticate_user` asume unicidad usando
> `find_one`.

---

## 7. Mapa de campos sensibles

Este es el inventario que cualquier cambio debe respetar. Su enforcement está en
`04-seguridad-y-acceso.md` §3; aquí solo se listan **dónde viven**.

| Campo | Ubicación | Naturaleza | Tratamiento |
|---|---|---|---|
| `licenses[].password` | `establishments` (embebido) | Credencial de plataforma externa (SIGE, etc.) | `[REDACTED]` para no-admin (`establishments_service.py:89-91`) |
| `licenses[].email` | `establishments` | Usuario de esa credencial | **Sin redactar.** Viaja completo a cualquier autenticado. |
| `connectivity.ssid_password` | `establishments` | Clave de la red WiFi del establecimiento | `[REDACTED]` para no-admin (`:92-93`) |
| `licenses` (array completo) | `establishments` | — | **Excluido de `LISTING_PROJECTION`**: nunca aparece en el listado, para ningún rol |
| `connectivity` (bloque) | `establishments` | Contiene el SSID y su clave | Excluido de `LISTING_PROJECTION` |
| `general_info.director_email`, `director_phone` | `establishments` | Datos personales | Sin redactar. Excluidos del listado solo por no estar proyectados. |
| `counterparts[].email`, `.phone` | `counterparts` | Datos personales de funcionarios | **Sin redactar ni restringir.** Cualquier autenticado lee todas las contrapartes. |
| `LeasedPrinter.ip_address`, `.support_*`, `.director_*` | `establishments` | Dirección IP interna y contactos | Sin redactar. Excluidos del listado por proyección. |
| `users.hashed_password` | `users` | Hash bcrypt | Nunca sale: `UserResponse` solo expone `username`, `full_name`, `role` |

> 🔸 **BRECHA:** la redacción es una **lista blanca de dos campos**, codificada como dos `if`
> literales en `find_by_rbd`. Un campo sensible nuevo no queda protegido por omisión: hay que
> acordarse de agregarlo ahí. El dato personal de las contrapartes (correo y teléfono de
> funcionarios identificados) no tiene ninguna protección por rol.

---

## 8. Datos semilla y su ciclo de vida

`backend/establishments.json` (78 registros, **git-ignored** por `.gitignore:4`) es la fuente.
Claves de nivel raíz por registro: `rbd`, `rbd_dv`, `name`, `comuna`, `area_type`, `address`,
`general_info`, `metrics`, `counterparts`, `connectivity`, `printers`, `location`.

`seed_if_empty` (`database_service.py:32`, delega en `seed_service.seed_if_empty`,
`database/seed_service.py:9`) descompone cada registro en tres destinos: `metrics` y
`counterparts` salen a sus colecciones, y el resto arma el documento de `establishments`
(`seed_service.py:194-207`).

**Hallazgos verificados sobre esa descomposición:**

> ✅ **RESUELTO:** el documento que arma el seeding (`est_doc`, `seed_service.py:202`) incluye
> `"location": item.get("location")`. Sembrar una base desde cero ya carga las coordenadas de
> los 74/78 registros que las traen en `establishments.json` — antes se perdían porque
> `scripts/import_kmz_locations.py` solo escribía directamente en MongoDB (además del JSON), y
> esa escritura no sobrevivía a una recreación de la base. El script KMZ sigue siendo la única
> vía para *incorporar* coordenadas nuevas (lee el KMZ, actualiza `establishments.json` y, de
> paso, la base ya corriendo); el seeding ahora solo es responsable de *propagarlas* al crear
> la base desde cero.
>
> 🔸 **BRECHA:** `est_doc` incluye `"licenses": item.get("licenses", [])`, pero
> `establishments.json` **no tiene** la clave `licenses` en ningún registro. Todo el aparato
> de `LicenseCredential`, la redacción de `password` y los tests BE-05 / INT-02 protegen hoy
> un array que siempre se siembra vacío. La funcionalidad es correcta y los tests la cubren
> con datos sintéticos; simplemente no hay dato real cargado por esa vía.
>
> 🔸 **BRECHA:** `rbd_full` no existe en el JSON origen, así que el seeding cae al fallback
> `f"{rbd}"` (`:210`) y el `rbd_full` de todos los establecimientos queda igual al `rbd`, sin
> el dígito verificador — aunque `rbd_dv` sí esté presente y se guarde aparte.

**El seeding es todo-o-nada y no es una migración.** Solo corre si la colección está vacía.
No existe mecanismo de actualización incremental: cargar datos nuevos sobre una base ya
poblada requiere hoy vaciar las colecciones y reiniciar, o escribir en Mongo a mano. Ver
`07-operacion.md` §4.
