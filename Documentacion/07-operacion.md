# 07 · Operación

> **Alcance.** Levantar, poblar, probar, construir y desplegar el sistema. Variables de
> entorno y su significado. Checklist de impacto en despliegue.
>
> **Verificado contra:** `docker-compose.yml`, `docker-compose.prod.yml`, `backend/Dockerfile*`,
> `frontend/Dockerfile.prod`, `frontend/nginx.conf`, `frontend/vite.config.js`, `backend/run.py`,
> `backend/pytest.ini`, `scripts/deploy.sh`, `scripts/backup-mongo.sh`, `scripts/restore-mongo.sh`,
> `backend/scripts/import_kmz_locations.py`, `.env.production.template`, `.gitignore`.

---

## 1. Levantar el entorno de desarrollo

### 1.1 Con Docker (recomendado)

```bash
docker compose up --build
```

Levanta tres servicios en la red `slep_network`:

| Servicio | URL | Notas |
|---|---|---|
| `slep_mongodb` | `localhost:27017` | Sin autenticación en desarrollo |
| `slep_backend` | `http://localhost:8000` | `uvicorn --reload`, código montado como volumen |
| `slep_frontend` | `http://localhost:5173` | Vite dev server, proxy de `/api` a `backend:8000` |

Documentación interactiva de la API en `http://localhost:8000/docs`.

**Prerrequisito no evidente:** `backend/establishments.json` debe existir. Está **git-ignored**
(`.gitignore:2-3`) porque contiene datos reales del servicio, así que un `git clone` limpio no
lo trae. Sin ese archivo el backend arranca igual, registra
`Seeding source file not found at ...` (`seed_service.py:44`) y la base queda vacía salvo
el usuario admin. Hay que pedirlo a quien mantiene el proyecto.

El código del backend está montado como volumen (`./backend:/app`), así que `--reload` recoge
los cambios sin rebuild. **Una dependencia nueva en `requirements.txt` sí exige rebuild**
(`docker compose up --build`).

> 🔸 **BRECHA (footgun de `node_modules`):** `frontend` monta `./frontend:/app` **y**
> `/app/node_modules` como volumen anónimo separado (`docker-compose.yml`), para que el bind
> mount del código no tape el `node_modules` instalado en la imagen. Ese volumen anónimo se
> crea **una sola vez por contenedor** y no se vuelve a poblar desde la imagen en reconstrucciones
> posteriores. Si se hace `docker compose build frontend` (o se edita `package.json`) y después
> se usa `docker compose restart frontend` en vez de recrear el contenedor, `npm run dev` sigue
> corriendo sobre el `node_modules` **viejo** — sin la dependencia nueva. El síntoma es una
> página en blanco en el navegador (el import falla en tiempo de módulo, sin `ErrorBoundary` que
> lo capture) mientras el backend sigue respondiendo con normalidad, porque el error es 100%
> del lado del bundling de Vite. **Correcto:** `docker compose up -d --build frontend` (recrea
> el contenedor, y con él el volumen anónimo) — nunca `restart` después de tocar dependencias
> del frontend.

### 1.2 Sin Docker

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# MongoDB debe estar corriendo en localhost:27017 (default de config.py)
python run.py        # uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

> 🔸 **BRECHA:** `vite.config.js` fija el proxy a `http://backend:8000` — el nombre de servicio
> **de Docker**. Fuera de Docker ese host no resuelve y todas las llamadas a `/api` fallan. El
> desarrollo sin Docker requiere editar `vite.config.js` a `http://localhost:8000` y acordarse
> de no comitear ese cambio. Una variable de entorno con default resolvería ambos casos; hoy no
> existe (ADR-008).

### 1.3 Credenciales iniciales

Usuario `admin`, contraseña `ADMIN_PASSWORD` — que en desarrollo cae al default `admin123`
(`config.py:14`). El usuario se siembra **solo si la colección `users` está vacía**
(`seed_service.py:19-20`, función `_seed_admin_user`). Cambiar `ADMIN_PASSWORD` después del primer arranque **no** cambia
la contraseña: hay que borrar el documento de `users` y reiniciar.

---

## 2. Variables de entorno

Todas se leen en `backend/app/config.py` con `os.getenv`. **Todas tienen default**, lo que
significa que ninguna omisión impide el arranque — ver la brecha de `04-seguridad-y-acceso.md` §6.

| Variable | Default | Significado | Dónde se define en prod |
|---|---|---|---|
| `MONGODB_URL` | `mongodb://localhost:27017` | Cadena de conexión completa. En producción incluye usuario, contraseña y `?authSource=admin` | `docker-compose.prod.yml`, compuesta |
| `DATABASE_NAME` | `slep_llanquihue` | Nombre de la base | `.env` |
| `JWT_SECRET` | *(valor público en el código)* | **Clave de firma HS256.** Debe ser único y secreto por despliegue. Generar con `python -c "import secrets; print(secrets.token_hex(64))"` | `.env` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `180` | Vigencia del token en minutos. No hay refresh: al expirar hay que reautenticarse | `.env` (default `180` en el compose) |
| `ADMIN_PASSWORD` | `admin123` | Contraseña del usuario admin **solo en el primer arranque**. Ignorada después | `.env` |
| `MONGO_ROOT_USERNAME` | — | Usuario root de MongoDB. **Solo producción**, no lo lee `config.py` | `.env` |
| `MONGO_ROOT_PASSWORD` | — | Contraseña root. **Solo producción** | `.env` |
| `BACKUP_RETENTION_DAYS` | `7` | Días de retención de los dumps. **Solo producción**, lo lee `backup-mongo.sh` | `.env` |

El frontend **no tiene variables de entorno** (ADR-008).

### 2.1 🧭 DISEÑO F2: variables de la feature de usuarios (no implementadas)

Cada una debe declararse en **los cuatro archivos** (`config.py`, `docker-compose.yml`,
`docker-compose.prod.yml`, `.env.production.template`; un test lo verifica) y evaluarse para el
paso 1 de `scripts/deploy.sh`. **Las de identidad y secreto no tienen default: si falta una, la app
no arranca.**

| Variable | Default | Significado |
|---|---|---|
| `ALLOWED_EMAIL_DOMAINS` | **ninguno** | Lista separada por comas (`slepllanquihue.cl`). Valida las altas y el claim `hd` de Google |
| `BOOTSTRAP_ADMIN_EMAIL` | **ninguno** | Correo del admin sembrado o migrado |
| `PUBLIC_BASE_URL` | **ninguno** | URL pública base (https, salvo `localhost`); forma el enlace de los correos |
| `MAIL_MODE` | **ninguno** | `gmail` (envío real) o `console` (escribe el mensaje en el log; solo desarrollo, el arranque lo rechaza si `PUBLIC_BASE_URL` no es `localhost` o `127.0.0.1`). Con `console` no hacen falta las cuatro variables de Gmail/Google siguientes |
| `GMAIL_SENDER_ADDRESS` | **ninguno** | Casilla remitente dedicada, no personal |
| `GMAIL_REFRESH_TOKEN` | **ninguno** | **Secreto.** Token de la casilla remitente, obtenido una vez (§9). Trátese como `JWT_SECRET` |
| `GOOGLE_CLIENT_ID` | **ninguno** | Cliente OAuth. Hoy está en el `.env` de la raíz pero **no llega al contenedor** (ningún compose lo nombra) |
| `GOOGLE_CLIENT_SECRET` | **ninguno** | **Secreto.** Lo usa el refresco del token de Gmail |
| `PASSWORD_MIN_LENGTH` | `15` | Mínimo ≥ 8 (NIST SP 800-63B-4: 15 sin MFA) |
| `PASSWORD_MAX_LENGTH` | `64` | Mínimo permitido 64; la política también rechaza lo que pase de 72 bytes (límite de bcrypt) |
| `PASSWORD_REQUIRE_CHAR_CLASSES` | `0` | De 0 a 4. NIST recomienda 0 |
| `JWT_SECRET`, `ADMIN_PASSWORD` | **ninguno** (hoy tienen default, D2) | Pasan a ser obligatorias; `docker-compose.yml` (desarrollo) debe definir `ADMIN_PASSWORD` |

**Cada variable pasa a ser obligatoria en la fase que la usa**, no antes: F3 exige
`BOOTSTRAP_ADMIN_EMAIL`, `ALLOWED_EMAIL_DOMAINS`, `JWT_SECRET`, `ADMIN_PASSWORD` y la política de
contraseñas; F4 agrega `MAIL_MODE` y `PUBLIC_BASE_URL` (y las de Gmail/Google si `MAIL_MODE=gmail`);
F6 agrega `GOOGLE_CLIENT_ID`. Mientras la cuenta remitente no exista se trabaja con
`MAIL_MODE=console`.

Un valor de la política fuera de rango impide el arranque con un mensaje claro. Los vencimientos
de los enlaces (72 h invitación, 24 h restablecimiento) y el tope de 200 ítems por lote son
constantes de código, no variables.

`.env.production.template` es la plantilla a copiar como `.env` en el servidor. `.env` está
git-ignored.

---

## 3. Ejecutar los tests

**Backend** — pytest con `asyncio_mode = auto` (`backend/pytest.ini`), MongoDB **mockeado**
(`AsyncMock`/`MagicMock` sobre `db_service.db` en `tests/conftest.py`). No requiere base ni
contenedores.

```bash
cd backend
python -m pytest -v                                    # toda la suite
python -m pytest tests/test_BE05_licenses_access_control.py -v   # un archivo
python -m pytest -k "INT02" -v                         # por patrón
```

`pytest.ini` ya incluye `-v --tb=short` en `addopts`. Nomenclatura:
`test_BE0x` = backend unitario, `test_INT0x` = integración con `TestClient`.

> 🔸 **BRECHA:** `pytest-asyncio`, `pytest`, `mongomock` y `httpx` **no están en
> `requirements.txt`**, pese a que `conftest.py` importa `pytest_asyncio` y `httpx`. No existe
> `requirements-dev.txt`. Un entorno limpio instalado desde `requirements.txt` no puede correr
> los tests: hay que instalar esas dependencias a mano. El docstring de `conftest.py` menciona
> `mongomock`, pero el código real usa `unittest.mock` — la estrategia descrita y la
> implementada no coinciden.

**Frontend** — vitest + Testing Library con jsdom:

```bash
cd frontend
npm test                # vitest run
```

Suites `test_FE00` a `test_FE05` e `test_INT01`, en `frontend/src/tests/`.

> 🧭 **DISEÑO F2:** los tests nuevos usan los IDs `BE09` en adelante, `INT03` en adelante y
> `FE06` en adelante (último existente: `BE08`, `INT02`, `FE05`). Se propone un
> `requirements-dev.txt` con `pytest`, `pytest-asyncio` y `httpx` (D22).

**Evidencia observable (regla 1 de `GEMINI.md`):** presentar siempre la salida real de estos
comandos. Un código de salida sin stdout visible no cuenta como verificación. Si el entorno no
permite ejecutarlos, pedir al usuario el comando exacto y esperar su respuesta.

---

## 4. Datos: seeding, importadores y recarga

### 4.1 Seeding automático

`seed_if_empty()` corre en cada arranque (`01-arquitectura.md` §5) y actúa **solo si la
colección está vacía**. Lee `backend/establishments.json` y lo descompone en tres colecciones
(`02-modelo-datos.md` §8).

**El seeding no es una migración.** No hay forma soportada de cargar datos nuevos sobre una base
ya poblada. Recargar desde cero, en desarrollo:

```bash
docker compose exec mongodb mongosh slep_llanquihue --eval \
  'db.establishments.deleteMany({}); db.counterparts.deleteMany({}); db.metrics.deleteMany({})'
docker compose restart backend
```

**Esto destruye toda edición hecha desde la aplicación.** No ejecutarlo en producción sin backup
previo (§6.2). Nótese que `users` se deja intacta a propósito: borrarla re-sembraría el admin
con `ADMIN_PASSWORD`.

> ✅ El seeding ya incluye `location` en `est_doc` (`02` §8, D1 resuelto), así que una recarga
> conserva las coordenadas de los 74/78 registros que las traen en `establishments.json`. El
> importador KMZ (§4.2) solo hace falta para *incorporar* coordenadas nuevas o corregidas.

### 4.2 Importador de coordenadas (KMZ)

```bash
cd backend
python scripts/import_kmz_locations.py
```

Lee `backend/data/SLEP_EE.kmz`, empareja cada Placemark contra `establishments.json` por comuna
+ similitud de nombre (umbral `0.80`, `difflib` sobre nombres normalizados sin acentos ni
stopwords del rubro), y para cada coincidencia de alta confianza hace **dos escrituras**:
`backend/establishments.json` y el documento en MongoDB. Los no emparejados se listan al final
para carga manual desde la ficha (Editar → Latitud/Longitud).

Requiere que `MONGODB_URL` apunte a la base correcta y que la base esté poblada.

> ⚠️ **NO VERIFICADO:** que el script se ejecute sin error contra el KMZ actual y que los 74
> establecimientos con `location` en el JSON provengan de esta corrida. Para confirmarlo, correr
> el script y contrastar su resumen final con
> `db.establishments.countDocuments({location: {$exists: true}})`.

### 4.3 Planilla origen

`Documentacion/2026 - Directorio SLEP Llanquihue.xlsx` y `excel_details.txt` describen la
fuente. **No existe script versionado que convierta la planilla a `establishments.json`**
(`01` §1). Es un procedimiento manual no reproducible.

---

## 5. Build y despliegue

### 5.1 Build de producción

Backend (`backend/Dockerfile.prod`): `python:3.11-slim`, instala `requirements.txt` + `gunicorn`,
copia el código (sin volumen), y arranca `gunicorn app.main:app` con 2 `UvicornWorker`,
`--timeout 120` y logs a stdout. Sin `--reload`. Healthcheck contra `GET /`.

Frontend (`frontend/Dockerfile.prod`): build multi-etapa — `node:22-alpine` corre `npm install`
y `npm run build`, luego `nginx:1.27-alpine` sirve `/app/dist` con `nginx.conf`. Healthcheck
contra `/health`.

### 5.2 Despliegue

```bash
bash scripts/deploy.sh
```

Seis pasos, con `set -euo pipefail`:

1. **Validación** — `.env` presente, Docker corriendo, y las cinco variables críticas
   (`MONGO_ROOT_USERNAME`, `MONGO_ROOT_PASSWORD`, `JWT_SECRET`, `ADMIN_PASSWORD`, `DATABASE_NAME`)
   definidas y no vacías. Aborta si falta alguna.
2. **Backup preventivo** — ejecuta `backup-mongo.sh` dentro del contenedor `backup`, si está
   corriendo. No aborta si falla (contempla el primer deploy).
3. `git pull --ff-only`.
4. `docker compose -f docker-compose.prod.yml build --no-cache`.
5. `docker compose -f docker-compose.prod.yml up -d --remove-orphans`.
6. **Verificación** — espera 10 s e inspecciona el `Health.Status` de los cuatro contenedores.
   Sale con código 1 si alguno no está `healthy`.

El script es la mitigación práctica de la brecha de secretos: valida en el servidor lo que
`config.py` no valida en el código (`04` §6). Desplegar sin él reintroduce el riesgo completo.

> 🔸 **BRECHA:** `deploy.sh` no ofrece rollback. Si el paso 6 falla, los contenedores nuevos ya
> están corriendo. La reversión es manual: `git checkout <commit-anterior>` y volver a
> desplegar, más restaurar el backup del paso 2 si hubo cambio de esquema. La regla 3 de
> `GEMINI.md` (plan de rollback para componentes críticos) no está automatizada aquí.
>
> ⚠️ **NO VERIFICADO:** el mensaje final del script dice "corriendo en http://localhost", pero
> el compose publica el frontend en `127.0.0.1:8080`. Qué expone el puerto 80/443 del servidor
> queda fuera del repositorio (`01` §2).

### 5.3 Puertos y exposición

| Servicio | Desarrollo | Producción |
|---|---|---|
| MongoDB | `27017` publicado | `expose` interno, sin publicar |
| Backend | `8000` publicado | `expose` interno, sin publicar |
| Frontend | `5173` publicado | `127.0.0.1:8080` → contenedor `:80` |

En producción solo el frontend es alcanzable, y solo desde el propio host.

---

## 6. Backups

### 6.1 Automático

Servicio `backup` en `docker-compose.prod.yml`: contenedor `mongo:7.0` con un bucle que revisa
la hora cada 30 s y ejecuta `scripts/backup-mongo.sh` cuando marca las **02:00** del servidor.
El script hace `mongodump --gzip --archive` a `/backups/slep_backup_<TIMESTAMP>.gz` en el
volumen `mongo_backups`, y aplica la retención de `BACKUP_RETENTION_DAYS` (default 7).

> 🔸 **BRECHA:** el volumen `mongo_backups` es **local al host**. Un fallo del disco o la
> pérdida del servidor se lleva la base y todos sus backups. No hay copia fuera del host.
>
> 🔸 **BRECHA:** el planificador es un bucle `sleep 30` comparando `date '+%H:%M'`. Si el
> contenedor está reiniciando durante esa ventana, el backup del día se salta sin alerta. No
> hay notificación de fallo.

### 6.2 Restauración

```bash
bash scripts/restore-mongo.sh
```

Lista los backups disponibles del volumen `gestion-de-establecimientos_mongo_backups`, numerados
y ordenados del más reciente al más antiguo, para elegir cuál restaurar. Requiere el stack de
producción corriendo.

> ⚠️ **NO VERIFICADO:** el nombre del volumen está hardcodeado como
> `gestion-de-establecimientos_mongo_backups`, que Docker Compose deriva del nombre del
> directorio del proyecto. Si el repositorio se clona con otro nombre de carpeta, el volumen se
> llama distinto y el script no encuentra nada. Confirmar con `docker volume ls` en el servidor.
>
> ⚠️ **NO VERIFICADO:** no consta que la restauración se haya probado nunca. Un backup no
> verificado no es un backup. Ensayar la restauración en un entorno de prueba antes de
> necesitarla.

---

## 7. Checklist de impacto en el despliegue

Regla 2 de `GEMINI.md`: este análisis se hace **al planificar el cambio**, no cuando el usuario
lo evidencia.

| Si el cambio… | Entonces hay que… |
|---|---|
| Agrega una dependencia Python | Actualizar `requirements.txt` **y** rebuild de la imagen del backend (`--build`). El volumen de desarrollo no instala nada. |
| Agrega una dependencia npm | `package.json` + `package-lock.json`, rebuild del frontend. |
| Agrega una variable de entorno | Los **cuatro** archivos: `config.py`, `docker-compose.yml`, `docker-compose.prod.yml`, `.env.production.template`. Y evaluar si `deploy.sh` debe validarla en su paso 1. |
| Cambia un puerto | `docker-compose*.yml`, `vite.config.js` (proxy), `nginx.conf` (`proxy_pass`), healthchecks. |
| Cambia un alias de importación | `vite.config.js` (`resolve.alias`) y `jsconfig.json`. |
| Agrega o modifica un índice | `ensure_indexes()`. Se materializa al reiniciar. Cambiar la **definición** de un índice existente hace fallar el arranque: hay que borrarlo a mano primero (`01` §5). |
| Cambia el esquema de un documento | Definir qué pasa con los documentos existentes. El seeding **no** migra. Si hace falta `updateMany`, documentarlo y correrlo con backup previo. |
| Agrega un archivo estático o una ruta del frontend | El `try_files $uri $uri/ /index.html` de `nginx.conf` ya cubre el fallback de React Router. Sin cambios. |
| Cambia el endpoint de healthcheck | `Dockerfile.prod` (backend), `docker-compose.prod.yml` (los tres healthchecks), `nginx.conf` (`/health`). |
| Toca `auth/`, `ProtectedRoute` o `database_service` | Punto único de falla: rama aislada, punto de restauración, y tests de autenticación pasando antes y después (regla 3 de `GEMINI.md`). |
| 🧭 Agrega un componente de shadcn | `npx shadcn@latest add …` (nunca descargar a mano ni usar `--overwrite` sin aprobación); revisar con `--dry-run` las dependencias `@radix-ui/*` que trae, porque obligan a reconstruir la imagen del frontend. Requiere corregir antes `components.json` (D18). |
| 🧭 Envía correo desde el backend | `GMAIL_*` y `GOOGLE_*` en los cuatro archivos; el consentimiento inicial de la casilla es una tarea manual (§9). |
| 🧭 Agrega un contador o una colección con TTL | `ensure_indexes()` con `expireAfterSeconds`; comprobar que sigue siendo idempotente. |

---

## 9. 🧭 DISEÑO F2: casilla remitente de Gmail (checklist manual)

> **Estado: sin implementar.** Son tareas de la consola de Google Cloud y de Google Workspace
> que **ni el código ni un agente pueden hacer**: las ejecuta una persona con permisos de
> administrador. Decisión y riesgos: ADR-012.

1. [ ] **Elegir o pedir a TI la casilla remitente**: `@slepllanquihue.cl`, dedicada
   (notificaciones o no-reply), no personal. Si fuera personal, al irse su dueño o cambiar su
   contraseña se corta el envío para todos.
2. [ ] En el proyecto de Google Cloud del cliente OAuth existente, abrir la **pantalla de
   consentimiento** y confirmar que es de tipo **Internal**. Si fuera *External* en estado
   *Testing*, Google caduca el refresh token a los **7 días**.
3. [ ] Agregar el scope `https://www.googleapis.com/auth/gmail.send` (y ningún otro) al cliente.
4. [ ] Con la casilla remitente, ejecutar **una sola vez** el script
   `backend/scripts/gmail_consent.py` (instala `google-auth-oauthlib` solo donde se ejecute; no
   va en la imagen). Imprime el **refresh token** por pantalla; no lo escribe en ningún archivo.
5. [ ] Guardar el token como secreto en el `.env` del servidor (`GMAIL_REFRESH_TOKEN`) junto con
   `GMAIL_SENDER_ADDRESS`. **Nunca** en el repositorio ni en un chat.
6. [ ] Agregar `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` al `.env` del servidor y a los dos
   compose (hoy no llegan al contenedor).
7. [ ] **Si cambia la contraseña de la casilla remitente**, Google revoca los tokens con scopes de
   Gmail: repetir los pasos 4 y 5. Mientras tanto los usuarios quedan `invited` y el error se ve
   en `users.invitation.last_error`; al restablecer el envío, el admin reenvía las invitaciones.
8. [ ] Confirmar con TI que el filtro de salida o de spam del dominio no bloquea los correos de la
   casilla remitente antes de la primera alta masiva.

---

## 8. Diagnóstico rápido

| Síntoma | Causa probable | Verificación |
|---|---|---|
| La base queda vacía al arrancar | Falta `backend/establishments.json` (git-ignored) | `docker compose logs backend \| grep "Seeding source file not found"` |
| El login falla con `admin` / `admin123` | `users` ya existía, así que `ADMIN_PASSWORD` se ignoró | `db.users.findOne({username:"admin"})` |
| Todas las llamadas a `/api` fallan en dev | Frontend fuera de Docker con el proxy apuntando a `backend:8000` | §1.2 |
| El mapa de la ficha dice "Ubicación no disponible" | La base se re-sembró y se perdió `location` | `db.establishments.countDocuments({location:{$exists:true}})` · §4.1 |
| El dashboard muestra ceros | No hay métricas del año 2026, que está hardcodeado | `db.metrics.countDocuments({year:2026})` · `03` §5.16 |
| Sesión que se cierra sola | Token expirado (180 min) o un `401` que disparó el interceptor | `04` §1 |
| El backend pasa el healthcheck pero la app no funciona | `GET /` no consulta MongoDB | `03` §5.1 |
| El arranque falla al crear un índice | Se cambió la definición de un índice existente | `docker compose logs backend` · §7 |
