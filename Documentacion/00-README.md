# 00 · Índice y glosario — Sistema de Gestión de Establecimientos (SLEP Llanquihue)

> **Alcance de este documento.** Puerta de entrada a la base de conocimiento técnica.
> Define qué es el sistema, el vocabulario de dominio necesario para leer el código, y
> a qué documento ir según lo que se quiera hacer. No contiene detalle de implementación.
>
> **Estado:** verificado contra el repositorio el 2026-09-23, rama `master`, commit `5b0984e`.
> El 2026-10-02 se documentó la feature de usuarios e IAM. **Fase F3 implementada** (identidad,
> acceso por plataforma, unidades, perfil, contraseñas): `04` §1, §2 y §6, `03` §8, `02` §6 y
> `07` §1.3 describen el código nuevo. Siguen marcadas `🧭 DISEÑO` las partes de F4 a F7
> (correo, CSV, masivas, Google, auditoría, interconexión). Fuera de eso no se re-verificó
> el resto contra el código.

---

## 1. Qué es este sistema

Plataforma web interna del **SLEP Llanquihue** (Servicio Local de Educación Pública) para
consultar y mantener la ficha técnica de los establecimientos educacionales de los que el
servicio es sostenedor, junto con sus métricas anuales y sus contrapartes técnicas.

Se compone de tres piezas:

- **Backend** — API REST en FastAPI sobre MongoDB (`backend/`).
- **Frontend** — SPA React + Vite que consume esa API (`frontend/`).
- **Datos semilla** — `backend/establishments.json`, exportado desde las planillas del
  servicio, que puebla la base en el primer arranque.

**Lo que este sistema NO es** (frontera de diseño explícita): no es un libro de clases
digital, no gestiona asistencia diaria, notas ni matrícula transaccional. Consume esos
datos ya agregados. Toda propuesta de feature que cruce esa frontera debe discutirse como
decisión de arquitectura, no implementarse directamente.

**Escala actual:** 78 establecimientos en 5 comunas (`FRESIA`, `FRUTILLAR`, `LLANQUIHUE`,
`LOS MUERMOS`, `PUERTO VARAS`). Esta cifra importa: varias decisiones de diseño (paginación
con `page_size=100` por defecto, búsquedas con `$regex` sin anclar, agregaciones sin caché)
son correctas *a esta escala* y dejan de serlo un orden de magnitud más arriba. Ver
`05-guia-de-extension.md` §5.

> ⚠️ **Inconsistencia detectada.** Los tests y el plan histórico hablan de **79**
> establecimientos; `backend/establishments.json` contiene **78** registros al día de hoy.
> Ninguna aserción de test depende del número exacto, pero los comentarios que lo citan
> están desactualizados.

---

## 2. Mapa de documentos

| Documento | Responde a |
|---|---|
| `00-README.md` (este) | ¿Qué es esto? ¿Qué significa cada término? ¿Dónde busco? |
| `01-arquitectura.md` | ¿Cómo está construido? ¿Qué capa hace qué? ¿Cómo viaja una request? |
| `02-modelo-datos.md` | ¿Qué colecciones hay, qué forma tienen y por qué esa forma? |
| `03-api-contract.md` | ¿Qué endpoints existen, qué reciben, qué devuelven y qué garantías ofrecen? |
| `04-seguridad-y-acceso.md` | ¿Cómo se autentica? ¿Quién puede ver qué? ¿Qué invariantes protegen los tests? |
| `05-guia-de-extension.md` | ¿Cómo agrego una feature sin romper la arquitectura? |
| `06-decisiones-adr.md` | ¿Por qué está hecho así y no de otra forma? |
| `07-operacion.md` | ¿Cómo lo levanto, lo pruebo y lo despliego? |
| `historico/implementation_plan_iter1.md` | Intención original de la iteración 1. **No es estado actual.** |

## 3. Tabla "quiero hacer X → lee Y"

| Quiero… | Leer |
|---|---|
| Entender el sistema por primera vez | `00`, luego `01` |
| Levantar el entorno en mi máquina | `07` §1 |
| Agregar un campo a la ficha del establecimiento | `05` §2.1, luego `02` §3 |
| Agregar un módulo de dominio nuevo (ej. `inventario`) | `05` §1 — es autocontenido |
| Consumir la API desde otro sistema | `03` completo |
| Entender por qué las contrapartes son una colección aparte | `06` ADR-002 |
| Averiguar por qué un campo aparece como `[REDACTED]` | `04` §3 |
| Agregar un gráfico nuevo al dashboard | `05` §2.4 |
| Cambiar algo del despliegue o las variables de entorno | `07` §2 y §5 |
| Saber qué está mal hoy y qué falta | `05` §5 y las marcas `🔸 BRECHA` de cada documento |
| Entender la feature de usuarios e IAM (F3 implementada; F4 a F7 diseñadas) | `06` ADR-009 a ADR-014, luego `02` §9, `03` §8 y `04` §9 |
| Entender cómo se conectarán otras plataformas (`selloverde`) | `04` §10 |
| Configurar el correo de invitaciones (Gmail) | `07` §9 |

---

## 4. Glosario de dominio

Sin este vocabulario el código es ilegible: los nombres de campo mezclan español e inglés
según de dónde vino el dato.

| Término | Significado | Dónde aparece |
|---|---|---|
| **SLEP** | Servicio Local de Educación Pública. Organismo que asume el rol de sostenedor de los establecimientos públicos de un territorio, reemplazando a los municipios. Aquí: SLEP Llanquihue. | Nombre del proyecto, `CounterpartOrigin.SLEP` |
| **EE** | Establecimiento Educacional. La entidad central del sistema. | Colección `establishments` |
| **RBD** | Rol de Base de Datos. Identificador nacional único de un establecimiento, asignado por el MINEDUC. **Es la clave de negocio de todo el sistema**: se usa como clave foránea en lugar del `ObjectId` de Mongo. | `establishments.rbd`, `counterparts.rbd`, `metrics.rbd` |
| **DV** | Dígito verificador del RBD. Se guarda aparte (`rbd_dv`) y concatenado (`rbd_full`, formato `7722-3`). | `establishments.rbd_dv` |
| **Comuna** | División administrativa chilena (equivale a municipio). El SLEP Llanquihue abarca 5. | `establishments.comuna` |
| **Área (URBANO/RURAL)** | Clasificación territorial del establecimiento. Eje de análisis central del dashboard. | `establishments.area_type` |
| **Categoría** | Tipo de establecimiento en la taxonomía del servicio (ej. `"7. LICEO POLITÉCNICO"`, `"6. RURAL MULTIGRADO"`). Viene con prefijo numérico desde la planilla origen; el backend lo limpia solo al graficar. | `general_info.category` |
| **Cobertura / covertura** | Niveles educativos que imparte (BASICA, MEDIA, …). El campo está escrito con la falta de ortografía de la planilla origen (`covertura`) y se mantiene así por fidelidad al dato. | `general_info.covertura` |
| **IVE** | Índice de Vulnerabilidad Escolar. Porcentaje, calculado por JUNAEB, del alumnado en condición de vulnerabilidad socioeconómica. Se registra separado para básica y media. | `metrics.ive_basica`, `metrics.ive_media` |
| **ADP** | Alta Dirección Pública. Marca si el cargo de director del establecimiento fue provisto por concurso ADP. Valores `"Si"` / `"No"`. | `general_info.adp` |
| **Microcentro** | Agrupación de escuelas rurales pequeñas que coordinan trabajo pedagógico en conjunto. | `general_info.microcentro` |
| **Uni/Bi/Tridocente** | Escuela rural atendida por uno, dos o tres docentes para todos los niveles. | `general_info.uni_bi_tridocente` |
| **PAME** | Plan de Apoyo a la Mejora Educativa. | `general_info.pame`, `CounterpartRole.PAME` |
| **PIE** | Programa de Integración Escolar (educación inclusiva). | `CounterpartRole.PIE_ENCARGADO` |
| **SIGE** | Sistema de Información General de Estudiantes del MINEDUC. Plataforma externa. | `CounterpartRole.SIGE_ENCARGADO` |
| **UTP** | Unidad Técnico Pedagógica. | `CounterpartRole.UTP_JEFE` |
| **Contraparte** | Persona responsable de un rol respecto de un establecimiento. Puede pertenecer al establecimiento o al SLEP — esa distinción es el campo `origin`. | Colección `counterparts` |
| **Territorial** | Profesional del SLEP asignado como enlace de un establecimiento. Rota por año, de ahí el manejo especial en el seeding. | `CounterpartRole.TERRITORIAL` |
| **CAFRA** | Referencia geográfica usada para medir aislamiento (`distancia_cafra`). El dato viene de la planilla; su definición operativa no está documentada en el repo. | `general_info.distancia_cafra` |
| **BAM** | Banda Ancha Móvil. Módem/router móvil arrendado, con IMEI y orden de compra asociados. | `connectivity.bam[]` |
| **OC** | Orden de Compra (identificador de adquisición del Estado). | `BamEntry.oc`, `LeasedPrinter.oc_equipo` |
| **Telsur 2030 / Starlink / WOM** | Proveedores de conectividad presentes en el territorio. | `connectivity.internet_provider` |
| **Ficha** | Vista de detalle de un establecimiento en el frontend. | `frontend/src/components/FichaEstablecimiento.jsx` |
| **IAM** | *Identity and Access Management.* Gestión centralizada de usuarios, accesos y autenticación. 🧭 Diseño F2. | `04` §9 y §10 |
| **Plataforma** | Un sistema del SLEP bajo `*.slepllanquihue.gob.cl` (`datos`, `selloverde`) más la plataforma lógica `iam`. Cada usuario tiene un rol por plataforma. 🧭 | `users.access[]`, `platforms` |
| **Admin global** | Quien tiene `iam/admin`. Es un rol distinto de `datos/admin`. 🧭 | `04` §9.3 |
| **Unidad** | Unidad organizacional del SLEP, con nivel 1 a 5 (Dirección Ejecutiva, subdirecciones…). Los funcionarios SLEP pertenecen a una unidad; los usuarios de establecimiento, a un `rbd`. 🧭 | colección `units` |
| **Jefatura / subrogancia** | Quien dirige una unidad; y quien la reemplaza temporalmente. La subrogancia da visibilidad, no permisos. 🧭 | `units.head_user_id`, `subrogations` |
| **Invitación** | Estado `invited` de un usuario recién creado: recibe un correo con un enlace de un solo uso para definir su contraseña. 🧭 | `04` §9.5 |

---

## 5. Convenciones de esta documentación

- `> ⚠️ NO VERIFICADO:` — afirmación que no pudo confirmarse leyendo el repositorio. Dice
  qué falta leer o ejecutar para confirmarla.
- `> 🧭 DISEÑO F2:` — decisión aprobada que **todavía no está implementada**. El código actual
  no la cumple. Se retira la marca cuando la fase correspondiente la implementa y un test la
  verifica. Todo lo que no lleva esta marca describe el código actual.
- `> 🔸 BRECHA:` — el código actual no cumple una convención que este documento declara
  normativa, o presenta un riesgo conocido. **Es un registro, no un plan**: nada de lo
  marcado así fue corregido al escribir esta documentación.
- Toda afirmación técnica va acompañada de su origen en formato `ruta/archivo.py:símbolo`.
- Los diagramas Mermaid van siempre seguidos de prosa. Si el renderizador falla, la prosa
  debe bastar.
