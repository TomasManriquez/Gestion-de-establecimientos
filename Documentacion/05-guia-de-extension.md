# 05 · Guía de extensión

> **Alcance.** Documento operativo y prescriptivo: cómo agregar funcionalidad sin degradar la
> arquitectura. Está escrito para ser **autosuficiente** — un desarrollador o un agente debería
> poder agregar un módulo de dominio completo siguiendo §1 sin abrir ningún módulo existente.
>
> **Verificado contra:** los cinco módulos de `backend/app/`, `backend/tests/`, `frontend/src/`,
> `GEMINI.md`.

---

## 1. Receta: agregar un módulo de dominio nuevo

Ejemplo de trabajo: módulo `inventario` para registrar equipamiento por establecimiento.
Sustituye `inventario`/`Inventory` por tu dominio. **El orden importa**: cada paso depende del
anterior y el último es el que lo hace real.

### Paso 0 — Decidir si corresponde un módulo

Un módulo nuevo se justifica cuando la entidad **se consulta por sí sola** (no siempre a través
de su establecimiento) o **crece sin límite**. Si no cumple ninguna de las dos, es un
sub-esquema embebido en `Establishment` y esta receta no aplica: ve a §2.1. El criterio
completo y su razón están en `02-modelo-datos.md` §2.

### Paso 1 — Crear la estructura

```
backend/app/inventario/
├── __init__.py                 # una línea de comentario basta
├── inventario_entity.py
├── inventario_service.py
└── inventario_controller.py
```

> 🔸 **BRECHA (D23, nombre de carpeta):** esta receta dice «en español», pero el código usa
> inglés en todos los módulos. Para los módulos nuevos de la feature de usuarios se sigue el
> código (`users`, `units`, `platforms`, `audit`).
>
> 🧭 **DISEÑO F2:** dos excepciones acotadas a «exactamente tres archivos», ambas decididas en
> ADR: `units` es dueño de dos colecciones (`units`, `subrogations`, ADR-010) y
> `backend/app/mail/` es infraestructura con un solo archivo `mail_service.py` (ADR-012).

Convenciones **no negociables**, porque son las que hacen predecible el árbol:
carpeta en **singular o plural según el nombre del dominio, en español**, coherente con el
resto; los tres archivos con el prefijo **exacto** del nombre de la carpeta; sufijos
`_entity` / `_service` / `_controller`.

### Paso 2 — `inventario_entity.py`

Declara los modelos Pydantic. **Cuatro modelos, no uno**, siguiendo la separación de
`02-modelo-datos.md` §3.3:

```python
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, List

class InventoryType(str, Enum):          # enums del dominio: hereda de (str, Enum)
    NOTEBOOK = "NOTEBOOK"
    PROYECTOR = "PROYECTOR"

class InventoryBase(BaseModel):          # campos comunes
    rbd: str                              # SIEMPRE str — es la clave de negocio
    type: InventoryType
    description: str
    qty: int = 1
    obs: Optional[str] = ""

class InventoryCreate(InventoryBase):    # body del POST
    pass

class InventoryUpdate(BaseModel):        # body del PUT: TODO opcional, default None
    type: Optional[InventoryType] = None
    description: Optional[str] = None
    qty: Optional[int] = None
    obs: Optional[str] = None

class Inventory(InventoryBase):          # respuesta: agrega el _id
    id: str = Field(..., alias="_id")

    class Config:
        populate_by_name = True
```

Reglas que este archivo debe respetar:

- **No importa `db_service` ni `fastapi`.** Solo `pydantic`, `enum`, `typing`.
- **Todo enum del dominio hereda de `(str, Enum)`** para que serialice como string y FastAPI
  lo valide automáticamente (un valor fuera del enum devuelve `422` sin escribir nada).
- **`rbd` es `str`.** Cambiar eso rompe el contrato completo (`03-api-contract.md` §4).
- **El modelo de actualización tiene todos los campos `Optional` con default `None`**, porque
  el service filtra los `None` para construir el `$set` parcial.
- **El `_id` se expone con `alias="_id"` y `populate_by_name = True`**, igual que en
  `counterparts` y `metrics`, para que el JSON de salida lleve `_id` y el frontend lo consuma
  igual en todas partes.
- **Los campos textuales que vengan de planillas se tipan `str`, no `int`/`date`.** Ver
  `02-modelo-datos.md` §3.2 y ADR-005.

### Paso 3 — `inventario_service.py`

Toda la interacción con MongoDB y toda la lógica de negocio.

```python
from bson import ObjectId
from typing import List, Optional
from app.database.database_service import db_service
from app.inventario.inventario_entity import InventoryCreate, InventoryUpdate

class InventarioService:
    async def find_by_rbd(self, rbd: str) -> List[dict]:
        cursor = db_service.db.inventario.find({"rbd": rbd})
        items = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])      # ObjectId no es serializable a JSON
            items.append(doc)
        return items

    async def find_by_id(self, item_id: str) -> Optional[dict]:
        doc = await db_service.db.inventario.find_one({"_id": ObjectId(item_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
            return doc
        return None

    async def create(self, data: InventoryCreate) -> dict:
        doc = data.model_dump()               # Pydantic v2: model_dump(), NO dict()
        result = await db_service.db.inventario.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        return doc

    async def update(self, item_id: str, data: InventoryUpdate) -> Optional[dict]:
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        if not update_dict:                   # guarda obligatoria: $set vacío = excepción
            return await self.find_by_id(item_id)
        result = await db_service.db.inventario.update_one(
            {"_id": ObjectId(item_id)}, {"$set": update_dict}
        )
        if result.matched_count > 0:
            return await self.find_by_id(item_id)   # BE-07: devolver el documento, no un ack
        return None

    async def delete(self, item_id: str) -> bool:
        result = await db_service.db.inventario.delete_one({"_id": ObjectId(item_id)})
        return result.deleted_count > 0

inventario_service = InventarioService()      # singleton al final del archivo
```

Reglas que este archivo debe respetar:

- **No importa `fastapi`.** No lanza `HTTPException`. Ausencia de resultado se comunica con
  `None` o `[]`, y el controller decide el código HTTP.
- **No recibe `current_user`.** Si necesita comportarse distinto según el rol, recibe un
  **booleano explícito** (`include_sensitive: bool = False`), como `establishments_service`.
- **Siempre `doc["_id"] = str(doc["_id"])`** antes de devolver: el `ObjectId` de bson no es
  serializable a JSON y produce un 500 poco informativo.
- **Toda actualización parcial filtra los `None` y guarda contra el `$set` vacío.**
- **Toda escritura devuelve el documento resultante completo**, no `{"ok": true}` — es el
  invariante BE-07 y el frontend depende de él.
- **Un singleton al final**, sin clase abstracta ni inyección: es el patrón del proyecto.
- **Pydantic v2:** `model_dump()`, no `.dict()`; `populate_by_name`, no `allow_population_by_field_name`.

### Paso 4 — `inventario_controller.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List
from app.auth.auth_service import auth_service
from app.inventario.inventario_service import inventario_service
from app.inventario.inventario_entity import Inventory, InventoryCreate, InventoryUpdate

router = APIRouter(prefix="/api/inventario", tags=["inventario"])

@router.get("/establishment/{rbd}", response_model=List[Inventory])
async def get_by_establishment(
    rbd: str,
    current_user: dict = Depends(auth_service.get_current_user),
):
    return await inventario_service.find_by_rbd(rbd)

@router.post("", response_model=Inventory, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: InventoryCreate,
    current_user: dict = Depends(auth_service.get_current_user),
):
    return await inventario_service.create(payload)

@router.put("/{item_id}", response_model=Inventory)
async def update_item(
    item_id: str,
    payload: InventoryUpdate,
    current_user: dict = Depends(auth_service.get_current_user),
):
    updated = await inventario_service.update(item_id, payload)
    if not updated:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Item {item_id} not found")
    return updated

@router.delete("/{item_id}")
async def delete_item(
    item_id: str,
    current_user: dict = Depends(auth_service.get_current_user),
):
    if not await inventario_service.delete(item_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Item {item_id} not found")
    return {"message": "Item deleted successfully"}
```

Reglas que este archivo debe respetar:

- **El prefijo de ruta vive aquí**, en `APIRouter(prefix=...)`, no en `main.py`.
- **`tags=[...]` siempre**, para que OpenAPI agrupe las operaciones.
- **`response_model` en toda operación.** Es lo que filtra los campos internos (`03` §3.6) y lo
  que documenta el contrato. Los endpoints de analytics no lo tienen y es una brecha registrada;
  no la repliques.
- **`Depends(auth_service.get_current_user)` en toda ruta**, salvo que la ruta deba ser pública
  y eso esté justificado en este documento.
- **Convención de ruta por establecimiento: `/establishment/{rbd}`.** Así lo hacen
  `counterparts` y `metrics`. No uses `/{rbd}` a secas: colisiona con `/{item_id}`.
- **Ninguna consulta a MongoDB ni transformación de datos aquí.** Solo traducir `None`/`False`
  a código HTTP.

### Paso 5 — Registrar el router en `main.py`

Exactamente dos líneas, junto a las existentes:

```python
from app.inventario.inventario_controller import router as inventario_router
...
app.include_router(inventario_router)
```

**Este es el paso que hace real el módulo.** Sin él, todo lo anterior es código muerto que no
falla ni avisa.

### Paso 6 — Índices

Si el módulo tiene consultas recurrentes, agrega sus índices en
`database_service.py:ensure_indexes()`, siguiendo el patrón existente:

```python
await self.db.inventario.create_index("rbd", background=True)
await self.db.inventario.create_index([("rbd", 1), ("type", 1)], background=True)
```

Se materializan al reiniciar. `ensure_indexes` debe seguir siendo idempotente
(`test_BE01_ensure_indexes_is_idempotent`).

### Paso 7 — Tests mínimos

Crear `backend/tests/test_INV01_inventario_crud.py` siguiendo la nomenclatura del proyecto
(`test_<CODIGO><NN>_<descripcion>.py`, con docstring de cabecera que declare **qué verifica**).
El conjunto mínimo para un módulo CRUD:

1. `create()` devuelve el documento con `_id` asignado.
2. `update()` devuelve el documento actualizado completo — no un ack (BE-07).
3. `update()` con payload vacío no lanza excepción.
4. `delete()` devuelve `True` al borrar y `False` si el id no existe.
5. El controller expone las rutas esperadas y exige autenticación.
6. **Si el módulo toca campos sensibles:** un test de integración estilo INT-02 que verifique
   que no se filtran en ninguna respuesta.

Los tests mockean MongoDB con `AsyncMock`/`MagicMock` sobre `db_service.db` — ver
`tests/conftest.py` para las fixtures de datos y el patrón de cursor asíncrono simulado.

### Paso 8 — Frontend (si aplica)

El frontend no tiene capa de cliente API: cada componente llama `axios` con rutas relativas
(`03` §1). Para consumir el módulo nuevo, en el componente correspondiente:

```jsx
const { data } = await axios.get(`/api/inventario/establishment/${rbd}`);
```

No hace falta configurar nada: el token va en `axios.defaults.headers.common` desde `App.jsx`, y
el proxy (Vite en dev, Nginx en prod) resuelve el destino.

### Paso 9 — Verificar y documentar

```bash
cd backend && python -m pytest -v          # presentar la salida real (GEMINI.md regla 1)
cd frontend && npm test
```

Actualizar en esta documentación: la tabla de endpoints de `03-api-contract.md` §1 y §5, el
esquema en `02-modelo-datos.md`, y un ADR en `06` si la decisión de crear el módulo tuvo
alternativas descartadas.

---

## 2. Recetas de cambio frecuente

### 2.1 Agregar un campo a la ficha del establecimiento

El caso con más pasos olvidables. Un campo nuevo en `general_info`, por ejemplo `telefono_central`:

| # | Dónde | Qué |
|---|---|---|
| 1 | `establishments_entity.py` → `GeneralInfo` | Agregar `telefono_central: Optional[str] = ""`. **Con default**, o los documentos existentes fallan la validación al leerse. |
| 2 | `EstablishmentUpdate` | Nada: hereda `general_info: Optional[GeneralInfo]`, que ya incluye el campo nuevo. |
| 3 | *Solo si debe salir en el listado* → `LISTING_PROJECTION` | Agregar `"general_info.telefono_central": 1`. **Verifica antes que no sea sensible** (`04` §3.1). |
| 4 | *Solo si va en el listado* → `establishments_service.py:70-73` | Agregar el aplanamiento: `doc["telefono_central"] = gi.get("telefono_central", "")`. |
| 5 | *Solo si va en el listado* → `EstablishmentSummary` | Declarar el campo, o Pydantic lo descarta en silencio. |
| 6 | Datos existentes | Los documentos ya en MongoDB **no tienen el campo**. Pydantic lo rellena con el default al leer, así que la API funciona — pero una consulta `{"general_info.telefono_central": {"$exists": true}}` no los encuentra. Si el campo debe ser consultable, corre un `updateMany` con `$set` del default. |
| 7 | `frontend/src/components/FichaEstablecimiento.jsx` y `EditFicha.jsx` | Mostrar y editar. Recuerda que el PUT reemplaza el bloque `general_info` **entero** (`03` §3.5): el formulario debe enviarlo completo. |
| 8 | `02-modelo-datos.md` §3 | Documentar el campo. |

Los pasos 3-5 son los tres que hay que hacer juntos o no hacer. Omitir el 5 es el error más
común y el más silencioso: el dato llega del backend y desaparece sin error.

### 2.2 Agregar un rol de contraparte

1. `counterparts_entity.py` → `CounterpartRole`: agregar el valor (mayúsculas, `snake_case` en
   mayúsculas, igual a los existentes).
2. *Solo si el rol viene en los datos semilla:* `seed_service.py:113-128` → `role_mappings`,
   mapeando `clave_en_json → ("ROL", "ORIGEN")`. El seeding busca además `{clave}_email` y
   `{clave}_phone`.
3. Si el rol rota por año en la fuente (como `territorial`), va en `year_variant_roles`
   (`:133-135`), no en `role_mappings`.
4. Frontend: revisar si hay listas de roles hardcodeadas en `EditFicha.jsx` /
   `FichaEstablecimiento.jsx`.
5. `02-modelo-datos.md` §4 y `03-api-contract.md` §4 (ampliar un enum de salida es no-breaking
   para el servidor pero se documenta).

**No agregues un campo nuevo al documento de contraparte para un rol nuevo.** El discriminador
`role` existe precisamente para eso (ADR-002). Ver §4.

### 2.3 Agregar una métrica anual

1. `metrics_entity.py` → `MetricBase`: agregar `Optional[tipo] = <default>`.
2. `metrics_entity.py` → `MetricUpdate`: **agregar el mismo campo como `Optional[tipo] = None`.**
   Son dos listas mantenidas a mano. Olvidar la segunda deja el campo legible pero no editable,
   sin ningún error.
3. `seed_service.py:60-105` → mapeo del seeding, si el dato viene en `establishments.json`.
4. Frontend: pestaña de métricas de la ficha.
5. `02-modelo-datos.md` §5.

Elige el tipo con cuidado: un porcentaje va como `float`, no como `str`. `attendance_avg` es
`str` y por eso no se puede agregar (`02` §5) — no repitas ese error.

### 2.4 Agregar una agregación o un gráfico

1. `analytics_service.py`: método nuevo o pipeline nuevo dentro de `get_charts_data()`,
   devolviendo `[{label, value}]` como las cuatro series existentes.
2. Verifica que exista índice para el `$match` inicial (`02` §3.4). `metrics.year` ya está.
3. `analytics_controller.py`: si es un endpoint nuevo, **declárale `response_model`** — los dos
   existentes no lo tienen y es una brecha registrada (`03` §5.17), no un patrón a seguir.
4. **No hardcodees el año.** Los cuatro pipelines actuales fijan `2026` y es el acoplamiento
   temporal conocido del backend. Usa un parámetro con default calculado.
5. Frontend: `Dashboard.jsx` consume `/api/analytics/charts` y grafica con `recharts`.

### 2.5 Agregar un filtro al listado

1. `establishments_controller.py`: un `Query(None, description="...")` nuevo, y pasarlo al service.
2. `establishments_service.find_all()`: parámetro nuevo y su rama en la construcción de `query`.
3. **Escapa el valor** si vas a usar `$regex` (`re.escape`) — el código actual no lo hace y es
   una brecha registrada (`03` §3.4). No la propagues.
4. Verifica que exista índice para el campo filtrado.
5. Frontend: `Directory.jsx:68-76` arma el objeto `params`.
6. `03-api-contract.md` §3.4.

### 2.6 Agregar un campo sensible

Lee `04-seguridad-y-acceso.md` §3 completo primero. Resumen: **no** agregarlo a
`LISTING_PROJECTION`, **sí** agregarlo a la redacción de `find_by_rbd`
(`establishments_service.py:88-93`), **sí** escribir un test estilo BE-05 e INT-02, y revisar
que el `PUT` correspondiente no lo devuelva sin redactar (brecha conocida, `04` §2).

---

## 3. Límites arquitectónicos

Reglas que no se negocian, con la consecuencia concreta de violarlas.

| # | Regla | Consecuencia de violarla |
|---|---|---|
| L1 | **Un controller no consulta MongoDB.** Ni `db_service` ni pipelines de agregación. | La lógica deja de ser testeable sin levantar HTTP, y queda invisible para quien lea el service. Los tests BE-0x prueban services aislados; una consulta en el controller no queda cubierta por ninguno. |
| L2 | **Un service no importa `fastapi` ni lanza `HTTPException`.** Devuelve `None`, `[]` o `False`. | El service deja de ser reutilizable desde un script, un job o un test que no monte la app. Acopla la lógica de negocio al transporte HTTP. |
| L3 | **Un service no recibe `current_user`.** Recibe booleanos explícitos (`include_sensitive`). | La política de autorización se dispersa por toda la capa de datos y deja de ser auditable en un solo lugar. Hoy hay un único punto de decisión de rol (`establishments_controller.py:40`); ese es el activo a proteger. |
| L4 | **Un service no importa otro controller.** Jamás. | Ciclo de importación inmediato y, peor, inversión de la jerarquía: la capa de datos pasaría a depender de la de transporte. |
| L5 | **Un service puede importar otro service**, pero solo hacia abajo y sin ciclos. Si dos services se necesitan mutuamente, el dominio está mal cortado. | Ciclos de importación, y una señal de que faltó un tercer módulo o que las dos entidades son una. |
| L6 | **Una entity no importa `db_service` ni `fastapi`.** Solo `pydantic`, `enum`, `typing`. | Las entities dejan de ser importables desde tests unitarios puros y desde scripts. `tests/test_BE08` las importa directamente. |
| L7 | **Toda ruta declara `response_model`.** | Los campos internos se filtran al cliente por omisión — es el tercer filtro de `03` §3.6, y el único que protege de exponer un campo agregado al documento sin pensarlo. |
| L8 | **Toda ruta no pública declara `Depends(auth_service.get_current_user)`.** | Un endpoint anónimo sobre datos de establecimientos. No hay middleware que lo supla: la autenticación es por dependencia explícita, ruta por ruta. |
| L9 | **Las escrituras devuelven el documento completo resultante.** | Rompe `test_BE07` y obliga al frontend a re-consultar o a esperar con temporizadores — el problema que BE-07 existe para haber eliminado. |
| L10 | **El `rbd` es `str` en todo el stack.** | Cambio breaking del contrato (`03` §4), invalidación del índice único y rotura de las referencias de `counterparts` y `metrics`. |
| L11 | **La lógica compartida entre módulos vive en el módulo dueño del dato**, y se consume importando su service (L5). No hay carpeta `utils/` ni `shared/`, y no debe crearse una sin un ADR. | Una carpeta `utils/` sin dueño acumula lógica de negocio huérfana; es como se pierde la trazabilidad de qué módulo es responsable de qué regla. |

> 🧭 **DISEÑO F2 (norma propuesta para L5):** el grafo de imports entre los módulos de la
> feature está fijado en ADR-013 (`auth → users → {units, platforms, establishments, audit}`).
> Un test recorrerá los imports y fallará ante un ciclo o una arista no declarada. Cuando una
> regla de un módulo necesita un dato de otro que está **por encima** en el grafo, el controller
> lo calcula y se lo pasa al service como parámetro (mismo patrón que `include_sensitive`).

---

## 4. Puntos de extensión ya previstos

Antes de agregar un campo, revisa si el modelo ya tiene un lugar para lo que necesitas. Estos
tres puntos existen precisamente para absorber crecimiento sin cambiar el esquema:

**El discriminador `role` de `counterparts`.** Un tipo nuevo de responsable es un valor nuevo del
enum, punto. No un campo nuevo en `establishments`, no una colección nueva. Es exactamente el
problema que el rediseño de la iteración 1 resolvió: el modelo anterior tenía 20+ campos fijos
de contraparte dentro del establecimiento. Volver a ese patrón es la regresión más fácil de
cometer. Ver ADR-002.

**`metrics` versionada por `(rbd, year)`.** Un año nuevo es un documento nuevo. Nada en el
backend necesita cambiar para registrar 2027 — salvo el hardcode de `2026` en `analytics_service`,
que es justamente la brecha que impide que ese punto de extensión funcione solo. Ver ADR-003.

**Los arrays embebidos de `connectivity` y `printers`.** `bam[]`, `phone_extensions[]`,
`printers.owned[]`, `printers.leased[]` admiten N elementos sin cambio de esquema. Un segundo
proveedor de internet, una impresora más, un anexo telefónico nuevo: todos caben.

**Lo que NO existe todavía, aunque el proyecto lo mencione:** las "etiquetas configurables" que
el objetivo del proyecto describe no tienen soporte en el modelo. No hay campo `tags` ni
colección de taxonomías. Agregarlas es una decisión de modelado con ADR, no un campo más.

---

## 5. Deuda técnica y acoplamientos conocidos

Registro ordenado por consecuencia. Cada entrada apunta al documento donde está el detalle.

### 5.1 Pérdida de datos y corrección

| # | Deuda | Ubicación | Consecuencia |
|---|---|---|---|
| ~~D1~~ | ✅ Resuelto: el seeding ya incluye `location` en `est_doc` | `seed_service.py:194-207` | Recrear la base ya conserva las coordenadas de los 74/78 registros que las traen. `02` §8 |
| D2 | `JWT_SECRET` y `ADMIN_PASSWORD` con defaults funcionales en el repositorio | `config.py:9,14` | Un despliegue que los olvide arranca con secreto público y `admin123`. `04` §6 |
| D3 | El rol `viewer` puede escribir todo | todos los controllers | El nombre del rol no corresponde a su poder. `04` §2 |
| D4 | El `PUT` de establecimiento devuelve credenciales sin redactar a cualquier autenticado | `establishments_service.py:110,118` | Elude BE-05. Sin test. `04` §2 |
| D5 | `$regex` construido con valores sin escapar | `establishments_service.py:35-58` | ReDoS por petición autenticada. `03` §3.4 |

### 5.2 Acoplamiento temporal y duplicación

| # | Deuda | Ubicación | Consecuencia |
|---|---|---|---|
| D6 | El año **2026 hardcodeado** en los pipelines | `analytics_service.py:10,48,74` | En 2027 el dashboard informa datos de 2026 en silencio. `03` §5.16 |
| D7 | El director existe duplicado en `general_info` y en `counterparts` | `seed_service.py:181-190` | Divergen al editar uno solo; ambos se muestran en la UI. `02` §4.1 |
| D8 | `MetricBase` y `MetricUpdate` repiten 24 campos a mano | `metrics_entity.py` | Agregar una métrica y olvidar el segundo modelo la deja no editable, sin error. `02` §5 |
| D9 | `EstablishmentSummary` requiere tres cambios coordinados (proyección, aplanamiento, modelo) | `establishments_service.py:6-17,70-73` | Un campo del listado se pierde en silencio si falta uno de los tres. §2.1 |

### 5.3 Contrato y operación

| # | Deuda | Ubicación | Consecuencia |
|---|---|---|---|
| D10 | **Sin versionado de API** | los cinco controllers | Todo cambio breaking es un corte duro coordinado. `03` §3.1 |
| D11 | Los endpoints de analytics no tienen `response_model` | `analytics_controller.py:7,11` | Sin contrato declarado; cambian de forma sin aviso. `03` §5.17 |
| D12 | Sin manejador global de excepciones; `ObjectId` inválido → 500 | `counterparts_service.py:27,35,39` | Errores de cliente se reportan como fallo del servidor. `03` §3.3 |
| D13 | `metrics_service.find_by_year()` implementado y no expuesto | `metrics_service.py:22` | Código muerto alcanzable; el plan histórico lo documenta como endpoint. `03` §7 |
| D14 | El healthcheck no consulta MongoDB | `main.py:50` | Un backend sin base pasa como sano. `03` §5.1 |
| D15 | El seeding **no es una migración**: solo corre con la colección vacía | `seed_service.py:9` | No hay forma reproducible de cargar datos nuevos. `07` §4 |
| D16 | Sin pines de versión en `requirements.txt`; tres dependencias declaradas sin uso | `requirements.txt` | Builds no reproducibles. `01` §3 |
| ~~D17~~ | ✅ Resuelto: `.gitignore` ya solo ignora `Documentacion/*.xlsx`, `Documentacion/*.json` y `Documentacion/establishments.json` | `.gitignore:5-7` | Los `.md` de `Documentacion/` están versionados (`git ls-files Documentacion`). Ver abajo. |

> ✅ **RESUELTO (D17):** `.gitignore:5-7` ignora por extensión los `.xlsx` y `.json` de
> `Documentacion/` y deja versionar los `.md`. Verificado con `git ls-files Documentacion`
> (nueve archivos `.md`, incluido `historico/`). Cumple la política de versionado del estándar
> de documentación (`.agents/skills/project-documentation-standard.md` §3).

### 5.3b Deuda registrada al diseñar la feature de usuarios (F2)

Brechas encontradas al verificar el prompt de la feature contra el repositorio el 2026-10-02.
Son un registro, no un plan: ninguna se corrigió al documentarla (salvo que una historia de la
feature lo diga, indicada en la última columna).

| # | Deuda | Ubicación | Consecuencia | Se atiende en |
|---|---|---|---|---|
| D18 | `components.json` empieza con un BOM UTF-8 y declara `baseColor: "sky"`, que el registro de shadcn no tiene | `frontend/components.json:1,9` | `npx shadcn@latest info` falla con «Invalid configuration»; sin el CLI no se puede cumplir la regla de agregar componentes solo con el CLI. Reproducido y corregido en una copia de trabajo | US-39 (F5) |
| D19 | No existe `frontend/src/lib/api.js` (ADR-008 lo recomienda) | `frontend/src/lib/` (solo `utils.js`) | Las ~14 llamadas siguen dispersas; sin un lugar donde cambiar el prefijo. La feature crea el módulo solo para pantallas nuevas | US-40 (F5) |
| D20 | `npm run lint` no se puede ejecutar: el script existe, `eslint` no está en `devDependencies` ni instalado, y no hay configuración | `frontend/package.json:9` | CLAUDE.md §2 lista el lint como verificación, pero no hay forma de correrlo. No se declara nunca que el lint pasó | sin historia (decisión pendiente) |
| D21 | 513 clases de color crudas (`bg-slate-900`, `text-sky-500`…) y 57 líneas con `space-x/y-*` en los nueve componentes | `frontend/src/components/*.jsx` | Viola la regla de estilos de la skill de shadcn. Las pantallas nuevas no lo replican; las existentes **no se refactorizan** en la feature | fuera de alcance |
| D22 | `pytest`, `pytest-asyncio` y `httpx` no están en `requirements.txt`; el docstring de `conftest.py` dice mongomock pero el código usa `unittest.mock` | `backend/requirements.txt`; `backend/tests/conftest.py:4` | Un entorno limpio no puede correr los tests. Ya registrado en `07` §3 | US-07 propone `requirements-dev.txt` |
| D23 | El paso 1 de la receta (§1) pide carpetas en español, pero los cinco módulos existentes usan inglés (`establishments`, `counterparts`, `metrics`, `analytics`, `auth`) | `05` §1 «Paso 1»; `backend/app/*` | Los módulos nuevos (`users`, `units`, `platforms`, `audit`) siguen el **código** (inglés). Esta es la 🔸 **BRECHA** de documentación: la receta debe decir inglés | US-60 |

### 5.4 Qué escala mal a partir de aquí

A 78 establecimientos todo lo siguiente es correcto. Estos son los puntos que hay que revisar
si el sistema crece un orden de magnitud (otro SLEP, o granularidad por curso):

| Punto | Por qué aguanta hoy | Qué pasa a 10× |
|---|---|---|
| `search` con `$regex` sin anclar | Collection scan de 78 documentos | Scan de miles por pulsación de tecla, con debounce de 300 ms. Necesita índice de texto |
| `page_size` por defecto de 100 | Trae todo el directorio de una vez | Deja de cubrir el total; la paginación real del frontend (`Directory.jsx`) queda expuesta |
| Pipelines de analytics sin caché | `$lookup` sobre decenas de documentos por carga del dashboard | `$lookup` sobre miles en cada carga. Necesita caché o colección materializada |
| `find_by_rbd` lee el documento completo | Documentos pequeños | Documentos grandes leídos enteros para redactar dos campos. Necesita proyección de exclusión |
| Una consulta a `users` por request autenticada | Colección de un documento | Una lectura extra por request. Necesita caché con ventana de propagación explícita |
| `counterparts` sin índice sobre `role` | Colección pequeña | La consulta transversal que justifica la colección deja de ser viable |
| Seeding en el `lifespan` con 2 workers | Carrera teórica sin consecuencia visible | Arranques en frío más largos y la carrera se vuelve alcanzable |

---

## 6. Definition of Done

Adaptado de las reglas de `GEMINI.md`, que son vinculantes para este repositorio.

**Antes de empezar**

- [ ] ¿Toco un punto único de falla (`auth/`, `ProtectedRoute`, `database_service`)? Entonces:
      rama aislada y punto de restauración de git definidos **antes** del primer cambio, y los
      tests del flujo de autenticación pasando **antes** de tocar nada (regla 3).
- [ ] ¿La entidad nueva merece módulo o es un sub-esquema embebido? (§1 paso 0)
- [ ] ¿Existe ya un punto de extensión que absorba el cambio? (§4)

**Durante**

- [ ] Los límites arquitectónicos de §3 se respetan.
- [ ] No se replica ninguna brecha registrada en §5 (especialmente: `response_model` ausente,
      año hardcodeado, `$regex` sin escapar).
- [ ] Los campos sensibles siguen el protocolo de `04` §3.

**Verificación — evidencia observable (regla 1 de `GEMINI.md`)**

- [ ] `cd backend && python -m pytest -v` ejecutado, **con la salida real presentada**. Un
      código de salida sin stdout visible no cuenta como verificación.
- [ ] `cd frontend && npm test` ejecutado, con la salida real.
- [ ] Si el agente no puede ejecutar los tests en su entorno, **pedir explícitamente al usuario
      que ejecute el comando exacto y esperar su respuesta** antes de dar el paso por concluido.
- [ ] Verificación manual del flujo afectado en la UI, si aplica.

**Impacto en el despliegue (regla 2 de `GEMINI.md`)**

- [ ] ¿Se agregó una dependencia? → rebuild de imagen; `requirements.txt` o `package.json`
      actualizados.
- [ ] ¿Se agregó una variable de entorno? → `config.py`, `docker-compose.yml`,
      `docker-compose.prod.yml` **y** `.env.production.template`. Los cuatro.
- [ ] ¿Se agregó un índice? → confirmar que `ensure_indexes` sigue siendo idempotente y que el
      índice se materializa al reiniciar.
- [ ] ¿Cambió el esquema de un documento existente? → definir qué pasa con los documentos ya
      almacenados (§2.1 paso 6). El seeding **no** los migra.
- [ ] ¿Cambió un alias de importación, un puerto o la configuración del proxy? → revisar
      `vite.config.js` y `nginx.conf`.

**Rollback (regla 3 de `GEMINI.md`)**

- [ ] Punto de restauración identificado (commit, rama o feature flag).
- [ ] Para cambios de esquema: definido cómo se revierte el dato, no solo el código.

**Documentación**

- [ ] `03-api-contract.md` actualizado si cambió cualquier ruta, parámetro o forma de respuesta.
- [ ] `02-modelo-datos.md` actualizado si cambió un esquema o un índice.
- [ ] ADR nuevo en `06-decisiones-adr.md` si hubo una alternativa real descartada.
- [ ] Brecha nueva registrada en §5 si se dejó algo conscientemente pendiente.
