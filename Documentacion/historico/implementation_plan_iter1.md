# Plan de Implementación: Sistema de Gestión de Establecimientos (SLEP Llanquihue)
## Iteración 1 – Versión 2 (Modelo de Datos Revisado)

---

## 1. Rediseño del Modelo de Datos

### Principios aplicados
Viniendo de un contexto relacional, el modelo documental de MongoDB puede pensarse como **documentos que embeben colecciones de subdocumentos tipados** en vez de tablas planas con columnas fijas.

Los tres rediseños principales son:

| Problema identificado | Solución aplicada |
|---|---|
| `counterparts` era un objeto con 20+ campos fijos | Array de `Counterpart` con campo discriminador `role` y `origin` (Strategy Pattern) |
| `metrics` era un bloque plano sin historia | Colección separada `metrics` con `rbd` + `year` como clave compuesta → permite cruces |
| Impresoras incompletas (faltan campos de arriendo) | Dos sub-modelos separados y completos: `OwnedPrinter` y `LeasedPrinter` |

---

## 2. Diagrama Entidad-Relación (Modelo Documental Revisado)

### 2.1 Colecciones MongoDB

```mermaid
erDiagram
    establishments {
        string _id PK
        string rbd UK
        string rbd_dv
        string rbd_full
        string name
        string comuna
        string area_type
        string address
        object general_info
        object connectivity
        object printers
    }

    counterparts {
        string _id PK
        string rbd FK
        string role
        string origin
        string name
        string email
        string phone
    }

    metrics {
        string _id PK
        string rbd FK
        int year
        int enrollment
        float attendance_avg
        float ive_basica
        float ive_media
        int num_teachers
        int num_assistants
        float grade_avg
        int promoted
        int failed
        int transferred
        int dropouts
        string desempeno_basica
        string desempeno_media
        float ptje_nem
        float ptje_ranking
        float score_lectura
        float score_matematica1
        float score_matematica2
        float score_historia
        float score_ciencia
        int total_rendidores
        float tasa_promocion
        float tasa_reprobacion
        float tasa_desercion
        float tasa_retencion
    }

    users {
        string _id PK
        string username UK
        string hashed_password
        string full_name
        string role
    }

    establishments ||--o{ counterparts : "rbd"
    establishments ||--o{ metrics : "rbd"
```

---

### 2.2 Sub-esquema de `establishments` expandido

```mermaid
erDiagram
    establishments {
        string rbd PK
        string rbd_dv
        string rbd_full
        string name
        string comuna
        string area_type
        string address
    }

    general_info {
        string category
        string covertura
        string adp
        string uni_bi_tridocente
        string microcentro
        string coordinador_microcentro
        string detalle_niveles_combinados
        string nivel_transicion_nt
        string priorizado_asistencia
        string distancia_cafra
    }

    connectivity {
        int num_connections
    }

    telsur_2030 {
        bool active
        string status
        string ssid
        string ssid_password
        string test_date
        float download_speed_mbps
    }

    mobile_broadband_bam {
        bool active
        int qty
    }

    bam_entry {
        int num_bam
        string oc
        string imei
        string device
        string holder
        date start_date
        string term
        date end_date
        string status
    }

    starlink {
        bool installed
        date install_date
        string provider
    }

    other_connection {
        bool active
        string provider
        string password
        string connection_type
        float speed_mbps
        string obs
    }

    oc_version {
        string oc_number
        date date
        string obs
    }

    internal_network {
        string name
        int install_year
        int points_count
        string status
        string obs
    }

    phone_extension {
        string number
        string location
        bool verified
    }

    owned_printer {
        string model
        int qty
        string type
        string provider
        string licitation_code
        date expiry_date
        string obs
    }

    leased_printer {
        string type
        string brand
        string model
        string serial_number
        string bandeja_serial
        string oc_equipo
        string oc_bandeja
        bool has_furniture
        string location
        string support_contact
        string support_mail
        string support_phone
        string director
        string director_email
        string director_phone2
        string ip_address
        string sds_kfs
        string obs
        date install_date
        int initial_counter
    }

    license_credential {
        string name
        string email
        string password
        string url
        string obs
        bool is_new
    }

    establishments ||--|| general_info : "embeds"
    establishments ||--|| connectivity : "embeds"
    connectivity ||--|| telsur_2030 : "embeds"
    connectivity ||--|| mobile_broadband_bam : "embeds"
    mobile_broadband_bam ||--o{ bam_entry : "entries"
    other_connection ||--o{ oc_version : "versions"
    connectivity ||--o| other_connection : "embeds"
    connectivity ||--o| starlink : "embeds"
    connectivity ||--o{ internal_network : "embeds"
    connectivity ||--o{ phone_extension : "embeds"
    establishments ||--o{ owned_printer : "printers.owned"
    establishments ||--o{ leased_printer : "printers.leased"
    establishments ||--o{ license_credential : "licenses"
```

---

### 2.3 Counterpart – Patrón tipado (Strategy)

En vez de campos fijos (`territorial`, `rrhh`, `ti`, ...) usamos una colección separada `counterparts` donde cada documento representa una asignación. El campo `origin` discrimina si el encargado pertenece al **establecimiento** o al **SLEP**.

```mermaid
classDiagram
    class Counterpart {
        +_id: ObjectId
        +rbd: String              %% FK → establishments
        +role: CounterpartRole    %% Discriminador
        +origin: CounterpartOrigin
        +name: String
        +email: String
        +phone: String
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
    }

    class CounterpartOrigin {
        <<enumeration>>
        ESTABLECIMIENTO
        SLEP
    }

    Counterpart --> CounterpartRole
    Counterpart --> CounterpartOrigin
```

**Ventaja:** Puedes filtrar `db.counterparts.find({role: "TI"})` para obtener todos los encargados TI de la red, o `db.counterparts.find({rbd: "7722"})` para la ficha completa. Esto es el equivalente directo a una tabla de relación `N:M` en SQL.

---

### 2.4 Metrics – Colección versionada por año

```mermaid
classDiagram
    class Metric {
        +_id: ObjectId
        +rbd: String       %% FK → establishments
        +year: Integer     %% 2022, 2023, 2024, 2025, 2026
        +enrollment: Integer
        +attendance_avg: Float
        +ive_basica: Float
        +ive_media: Float
        +num_teachers: Integer
        +num_assistants: Integer
        +grade_avg: Float
        +promoted: Integer
        +failed: Integer
        +transferred: Integer
        +dropouts: Integer
        +desempeno_basica: String
        +desempeno_media: String
        +ptje_nem: Float
        +ptje_ranking: Float
        +score_lectura: Float
        +score_matematica1: Float
        +score_matematica2: Float
        +score_historia: Float
        +score_ciencia: Float
        +total_rendidores: Integer
        +tasa_promocion: Float
        +tasa_reprobacion: Float
        +tasa_desercion: Float
        +tasa_retencion: Float
    }
```

**Ventaja para cruces de datos:** Las agregaciones analíticas como "Matrícula Urbana vs Rural 2025-2026" son consultas directas en MongoDB:
```js
db.metrics.aggregate([
  { $match: { year: 2026 } },
  { $lookup: { from: "establishments", localField: "rbd", foreignField: "rbd", as: "est" } },
  { $group: { _id: "$est.area_type", total: { $sum: "$enrollment" } } }
])
```

---

## 3. Estructura Modular del Backend (NestJS-like)

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                          # Inicialización FastAPI, montaje CORS y routers
│   ├── config.py                        # Constantes: JWT_SECRET, DB_URL, DB_NAME, TOKEN_EXPIRE_MIN
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   └── database_service.py          # Motor asyncio, seeding desde establishments.json
│   │
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── auth_entity.py               # Pydantic: User, Token, TokenData
│   │   ├── auth_service.py              # bcrypt + JWT create/verify + get_current_user()
│   │   └── auth_controller.py           # POST /api/auth/login, POST /api/auth/logout
│   │
│   ├── establishments/
│   │   ├── __init__.py
│   │   ├── establishments_entity.py     # Pydantic: Establishment, GeneralInfo, Connectivity...
│   │   ├── establishments_service.py    # find_all(filters), find_by_rbd(), update_by_rbd()
│   │   └── establishments_controller.py # GET /api/establishments, GET /{rbd}, PUT /{rbd}
│   │
│   ├── counterparts/
│   │   ├── __init__.py
│   │   ├── counterparts_entity.py       # Pydantic: Counterpart, CounterpartRole (Enum), CounterpartOrigin (Enum)
│   │   ├── counterparts_service.py      # find_by_rbd(), upsert(), delete()
│   │   └── counterparts_controller.py   # GET /api/counterparts/{rbd}, POST, PUT, DELETE
│   │
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── metrics_entity.py            # Pydantic: Metric (con rbd + year como clave única)
│   │   ├── metrics_service.py           # find_by_rbd(), find_by_year(), upsert()
│   │   └── metrics_controller.py        # GET /api/metrics/{rbd}, GET /api/metrics?year=2026
│   │
│   └── analytics/
│       ├── __init__.py
│       ├── analytics_service.py         # Agregaciones MongoDB: KPIs, gráficos, cruces
│       └── analytics_controller.py      # GET /api/analytics/kpis, GET /api/analytics/charts
│
├── requirements.txt
└── run.py
```

---

## 4. Diagrama de Componentes (Actualizado)

```mermaid
graph TD
    subgraph Frontend["Frontend React + Tailwind v3 + Recharts"]
        Login[Login View]
        Dashboard[Dashboard View - KPIs y Gráficos]
        Directory[Directory View - Filtros y Búsqueda]
        Ficha[Ficha View]
        subgraph FichaTabs["Pestañas Ficha"]
            T1[General e Historial]
            T2[Contrapartes Técnicas]
            T3[Conectividad]
            T4[Inventario Impresoras]
        end
        Ficha --> FichaTabs
        AxiosClient[Axios Client con JWT interceptor]
        Login & Dashboard & Directory & Ficha --> AxiosClient
    end

    subgraph Backend["FastAPI Modular Backend :8000"]
        GW[API Gateway / CORS Middleware]
        AuthCtrl[Auth Controller - /api/auth]
        EstCtrl[Establishments Controller - /api/establishments]
        CpCtrl[Counterparts Controller - /api/counterparts]
        MetCtrl[Metrics Controller - /api/metrics]
        AnaCtrl[Analytics Controller - /api/analytics]
        
        AuthSvc[Auth Service - JWT + bcrypt]
        EstSvc[Establishments Service]
        CpSvc[Counterparts Service]
        MetSvc[Metrics Service]
        AnaSvc[Analytics Service - Aggregation Pipeline]

        GW --> AuthCtrl & EstCtrl & CpCtrl & MetCtrl & AnaCtrl
        AuthCtrl --> AuthSvc
        EstCtrl --> EstSvc
        CpCtrl --> CpSvc
        MetCtrl --> MetSvc
        AnaCtrl --> AnaSvc
    end

    subgraph DB["MongoDB - slep_llanquihue"]
        C_Est[(establishments)]
        C_Cp[(counterparts)]
        C_Met[(metrics)]
        C_Usr[(users)]
    end

    AxiosClient -->|HTTPS + Bearer Token| GW
    AuthSvc --> C_Usr
    EstSvc --> C_Est
    CpSvc --> C_Cp
    MetSvc --> C_Met
    AnaSvc --> C_Est & C_Cp & C_Met
```

---

## 5. Endpoints de la API

| Módulo | Método | Ruta | Descripción |
|---|---|---|---|
| Auth | POST | `/api/auth/login` | Login con usuario/contraseña → retorna JWT |
| Auth | POST | `/api/auth/logout` | Invalida sesión en el frontend |
| Establishments | GET | `/api/establishments` | Listar con filtros: `search`, `comuna`, `area_type`, `category`, `adp` |
| Establishments | GET | `/api/establishments/{rbd}` | Ficha completa del establecimiento |
| Establishments | PUT | `/api/establishments/{rbd}` | Actualizar datos generales / conectividad / impresoras |
| Counterparts | GET | `/api/counterparts/{rbd}` | Todas las contrapartes de un EE |
| Counterparts | POST | `/api/counterparts` | Crear nueva contraparte |
| Counterparts | PUT | `/api/counterparts/{id}` | Editar contraparte existente |
| Counterparts | DELETE | `/api/counterparts/{id}` | Eliminar asignación |
| Metrics | GET | `/api/metrics/{rbd}` | Historial de métricas de un EE (todos los años) |
| Metrics | GET | `/api/metrics?year=2026` | Métricas de toda la red para un año |
| Metrics | PUT | `/api/metrics/{rbd}/{year}` | Actualizar/crear registro de métricas |
| Analytics | GET | `/api/analytics/kpis` | Contadores globales: EE, matrícula total, docentes, comunas |
| Analytics | GET | `/api/analytics/charts` | Datos para gráficos: matricula por area_type, por comuna, por categoría |

---

## 6. Plan de Verificación

### Pruebas de integración
1. **Database seed:** Verificar 79 documentos en `establishments`, 79×N en `counterparts`, 79×5 en `metrics`.
2. **Auth:** Login correcto → Token; Login incorrecto → 401; Token expirado → 401.
3. **Establishments:** Filtro `area_type=RURAL` → solo rurales; búsqueda por RBD exacto.
4. **Counterparts:** Buscar todas las contrapartes TI de la red (`role=TI`, `origin=SLEP`).
5. **Analytics:** Cruce urbano vs rural para matrícula 2026 retorna dos grupos.

### Manual (Usuario)
1. Iniciar sesión → navegar al Dashboard → validar KPIs y gráficos.
2. Filtrar por Comuna "Frutillar" en el Directorio → verificar resultados.
3. Abrir Ficha RBD 7722 → recorrer las 4 pestañas → editar un campo → confirmar persistencia.
