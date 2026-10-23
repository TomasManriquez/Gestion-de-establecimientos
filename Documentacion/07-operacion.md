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
`Seeding source file not found at ...` (`seed_service.py`) y los establecimientos quedan vacíos;
las unidades, las plataformas y el admin sí se crean (los siembran sus módulos). Hay que pedirlo a quien mantiene el proyecto.

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
> del lado del bundling de Vite. **Correcto:** `docker compose up -d --build --renew-anon-volumes frontend`.
> Recrear el contenedor **no basta**: `docker compose` conserva los volúmenes anónimos de la
> versión anterior, y `--renew-anon-volumes` (`-V`) es lo que los descarta y los repuebla desde la
> imagen nueva. Verificado en F5: tras `up -d --build frontend` (sin `-V`) Vite fallaba con
> `Failed to resolve import "@radix-ui/react-tooltip"`; con `-V` resolvió. Nunca `restart` después
> de tocar dependencias del frontend.
>
> 🧭 **F5 trae dependencias nuevas** (`@radix-ui/react-{alert-dialog,avatar,checkbox,dialog,dropdown-menu,popover,select,separator,switch,tooltip}`,
> `cmdk`, `next-themes`, `sonner`): tras actualizar el código hay que correr `docker compose up -d --build --renew-anon-volumes frontend` (sin `-V` el `node_modules` viejo sigue montado).
> Para producción, `docker compose -f docker-compose.prod.yml build frontend` ya las incluye (el build copia `package-lock.json`).

### 1.2 Sin Docker

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# MongoDB debe estar corriendo en localhost:27017 (default de config.py)
# La app NO arranca sin las variables obligatorias de §2 (JWT_SECRET, ADMIN_PASSWORD,
# BOOTSTRAP_ADMIN_EMAIL, ALLOWED_EMAIL_DOMAINS). Exportarlas antes, por ejemplo:
export JWT_SECRET=... ADMIN_PASSWORD=... BOOTSTRAP_ADMIN_EMAIL=admin@slepllanquihue.cl ALLOWED_EMAIL_DOMAINS=slepllanquihue.cl
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

### 1.3 Credenciales iniciales y migración del admin

Al arrancar, el `lifespan` ejecuta `run_bootstrap()` (`main.py`): primero las unidades, luego las
plataformas y por último el admin global. Todo es idempotente y tolera que dos workers de Gunicorn
corran a la vez.

| Situación de la base | Qué ocurre con el admin |
|---|---|
| **Vacía** | Se crea `BOOTSTRAP_ADMIN_EMAIL` con la contraseña `ADMIN_PASSWORD`, `must_change_password: true`, en la unidad `AF-TI`, con `iam/admin` y `datos/admin`. |
| **Con el admin de la versión anterior** (`username: "admin"`, sin correo) | Se **migra en el mismo `_id`**: recibe el correo, la unidad y los accesos; conserva su hash, así que la contraseña de siempre sigue funcionando. Entra con el correo o con `admin`. Los campos `username`, `hashed_password`, `role` y `full_name` se conservan (rollback). |
| **Ya migrada** | No hace nada. |

`ADMIN_PASSWORD` solo se usa si hay que **crear** el admin. Cambiarla después **no** cambia su
contraseña (cambiarla desde el perfil: `POST /api/auth/password`).

**Primer arranque tras actualizar un entorno existente (F3):**

1. Agregar las variables nuevas a tu entorno (§2). En desarrollo ya están en `docker-compose.yml`.
2. **Recrear el contenedor**, no solo reiniciarlo: `docker compose up -d --build backend`. Con el
   código montado y `--reload`, el contenedor *ya creado* recarga el código nuevo pero conserva el
   entorno viejo y falla con `Variable de entorno obligatoria sin definir: ADMIN_PASSWORD`. Es el
   comportamiento buscado (T9), no un fallo. `--build` instala `email-validator`.
3. Antes de desplegar en producción: backup (`scripts/backup-mongo.sh`) y verificar que `.env` tiene
   `BOOTSTRAP_ADMIN_EMAIL` y `ALLOWED_EMAIL_DOMAINS` (`deploy.sh` lo valida).

**Rollback:** volver al commit `pre-usuarios-f3` y redesplegar. El documento del admin conserva los
campos legados, y el código anterior ignora los campos nuevos. Los usuarios creados con el
código nuevo no existen para el código viejo (solo autentica al admin). Si hay que deshacer
también los datos: borrar las colecciones `units` y `platforms`, quitar de `users` los documentos
con `email`, y los campos nuevos del admin.

---

## 2. Variables de entorno

Todas se leen en `backend/app/config.py` (`Settings`) al arrancar. **Las de identidad y secreto no
tienen default: si falta una, la app no arranca** y el mensaje nombra la variable (T9; `04` §6).

| Variable | Default | Significado | Dónde se define en prod |
|---|---|---|---|
| `MONGODB_URL` | `mongodb://localhost:27017` | Cadena de conexión completa. En producción incluye usuario, contraseña y `?authSource=admin` | `docker-compose.prod.yml`, compuesta |
| `DATABASE_NAME` | `slep_llanquihue` | Nombre de la base | `.env` |
| `JWT_SECRET` | **ninguno** | **Clave de firma HS256.** Obligatoria. Debe ser única y secreta por despliegue. Mínimo 32 caracteres; se rechazan los valores públicos del repositorio y los marcadores `CAMBIA_ESTO…` (SEC-1). Generar con `python -c "import secrets; print(secrets.token_hex(64))"` | `.env` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `180` | Vigencia del token en minutos. No hay refresh: al expirar hay que reautenticarse | `.env` (default `180` en el compose) |
| `ADMIN_PASSWORD` | **ninguno** | Contraseña del admin **solo si hay que crearlo** (§1.3). Obligatoria | `.env` |
| `BOOTSTRAP_ADMIN_EMAIL` | **ninguno** | Correo del admin global sembrado o migrado. Debe pertenecer a `ALLOWED_EMAIL_DOMAINS` | `.env` |
| `ALLOWED_EMAIL_DOMAINS` | **ninguno** | Dominios de correo permitidos, separados por comas (`slepllanquihue.cl`) | `.env` |
| `PASSWORD_MIN_LENGTH` | `15` | Largo mínimo (NIST SP 800-63B-4: 15 como único factor). ≥ 8 | `.env` (default `15` en el compose) |
| `PASSWORD_MAX_LENGTH` | `64` | Largo máximo permitido (≥ 64). Además se rechaza lo que pase de 72 bytes (límite de bcrypt) | `.env` (default `64`) |
| `PASSWORD_REQUIRE_CHAR_CLASSES` | `0` | Tipos de caracteres exigidos, 0 a 4. NIST recomienda 0 | `.env` (default `0`) |
| `MONGO_ROOT_USERNAME` | — | Usuario root de MongoDB. **Solo producción**, no lo lee `config.py` | `.env` |
| `MONGO_ROOT_PASSWORD` | — | Contraseña root. **Solo producción** | `.env` |
| `BACKUP_RETENTION_DAYS` | `7` | Días de retención de los dumps. **Solo producción**, lo lee `backup-mongo.sh` | `.env` |

El frontend **no tiene variables de entorno** (ADR-008).

### 2.1 Variables de la feature de usuarios: estado por fase

**Ya implementadas** (tabla de abajo): en F3 `JWT_SECRET`, `ADMIN_PASSWORD`, `BOOTSTRAP_ADMIN_EMAIL`, `ALLOWED_EMAIL_DOMAINS` y la política de contraseñas; en F4 `MAIL_MODE`, `PUBLIC_BASE_URL`, `GMAIL_SENDER_ADDRESS`, `GMAIL_REFRESH_TOKEN`, `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` (✅). **🧭 De F6:** el uso de `GOOGLE_CLIENT_ID` para verificar el `id_token`. Cada una debe declararse en **los cuatro archivos** (`config.py`, `docker-compose.yml`,
`docker-compose.prod.yml`, `.env.production.template`; un test lo verifica) y evaluarse para el
paso 1 de `scripts/deploy.sh`. **Las de identidad y secreto no tienen default: si falta una, la app
no arranca.**

| Variable | Default | Significado |
|---|---|---|
| `ALLOWED_EMAIL_DOMAINS` | **ninguno** | Lista separada por comas (`slepllanquihue.cl`). Valida las altas y el claim `hd` de Google |
| `BOOTSTRAP_ADMIN_EMAIL` | **ninguno** | Correo del admin sembrado o migrado |
| `PUBLIC_BASE_URL` | **ninguno** | Origen público **sin ruta ni barra final**; forma el enlace de los correos. Con `MAIL_MODE=smtp` o `gmail` debe ser `https` (salvo `localhost`) |
| `MAIL_MODE` | **ninguno** | `smtp` (✅ envío real por SMTP, ADR-017), `gmail` (✅ envío real por Gmail API, alternativa) o `console` (escribe el mensaje en el log; solo desarrollo, el arranque lo rechaza si `PUBLIC_BASE_URL` no es `localhost` o `127.0.0.1`). Con `console` no hace falta ninguna credencial de correo |
| `SMTP_HOST` | **ninguno** | Servidor SMTP (`smtp.gmail.com`). Obligatoria con `MAIL_MODE=smtp` |
| `SMTP_PORT` | **ninguno** | `587` (STARTTLS) o `465` (TLS implícito); otro valor impide el arranque. Obligatoria con `smtp` |
| `SMTP_USERNAME` | **ninguno** | Cuenta que inicia sesión (la casilla remitente). Obligatoria con `smtp` |
| `SMTP_PASSWORD` | **ninguno** | **Secreto.** Contraseña de aplicación de la casilla (§9). Trátese como `JWT_SECRET`; da acceso SMTP **e IMAP** |
| `SMTP_SENDER_ADDRESS` | **ninguno** | Dirección del encabezado `From`. Obligatoria con `smtp`; debe ser un correo válido |
| `GMAIL_SENDER_ADDRESS` | **ninguno** | Solo `MAIL_MODE=gmail`. Casilla remitente dedicada, no personal |
| `GMAIL_REFRESH_TOKEN` | **ninguno** | Solo `MAIL_MODE=gmail`. **Secreto.** Token de la casilla remitente, obtenido una vez (§9.1). Trátese como `JWT_SECRET` |
| `GOOGLE_CLIENT_ID` | **ninguno** | Cliente OAuth. Desde F4 los dos compose la pasan al contenedor (`${GOOGLE_CLIENT_ID:-}`); obligatoria con `MAIL_MODE=gmail` y para el login con Google (F6) |
| `GOOGLE_CLIENT_SECRET` | **ninguno** | **Secreto.** Solo `MAIL_MODE=gmail`: lo usa el refresco del token de Gmail |
| `GOOGLE_AUTO_PROVISION` | **ninguno** (obligatoria) | `true` o `false`, nada más. Con `true`, quien entra con una cuenta del dominio y no existe obtiene una cuenta de **lector** en `datos`, sin asignar (ADR-015). **En producción la activa el responsable** tras las condiciones de `04` §9.6; la plantilla trae `false`. Ambos compose la exigen (`${GOOGLE_AUTO_PROVISION:?…}`) |
| `PASSWORD_MIN_LENGTH` | `15` | Mínimo ≥ 8 (NIST SP 800-63B-4: 15 sin MFA) |
| `PASSWORD_MAX_LENGTH` | `64` | Mínimo permitido 64; la política también rechaza lo que pase de 72 bytes (límite de bcrypt) |
| `PASSWORD_REQUIRE_CHAR_CLASSES` | `0` | De 0 a 4. NIST recomienda 0 |
| `JWT_SECRET`, `ADMIN_PASSWORD` | **ninguno** (hoy tienen default, D2) | Pasan a ser obligatorias; `docker-compose.yml` (desarrollo) debe definir `ADMIN_PASSWORD` |

**Cada variable pasa a ser obligatoria en la fase que la usa**, no antes: F3 exige
`BOOTSTRAP_ADMIN_EMAIL`, `ALLOWED_EMAIL_DOMAINS`, `JWT_SECRET`, `ADMIN_PASSWORD` y la política de
contraseñas; F4 agrega `MAIL_MODE` y `PUBLIC_BASE_URL` (y las de Gmail/Google si `MAIL_MODE=gmail`; las `SMTP_*` si `MAIL_MODE=smtp`, ADR-017 ✅);
F6 agrega el uso de `GOOGLE_CLIENT_ID` para el login y la variable obligatoria `GOOGLE_AUTO_PROVISION`. Mientras la cuenta remitente no exista se trabaja con
`MAIL_MODE=console`: el mensaje, **con el enlace completo**, sale por el log del backend
(`docker compose logs backend | grep "MAIL console"`), que es como se prueba el alta en desarrollo.
En desarrollo `docker-compose.yml` usa `MAIL_MODE=${MAIL_MODE:-console}` y
`PUBLIC_BASE_URL=${PUBLIC_BASE_URL:-http://localhost:5173}`; en producción ambas son obligatorias
(`deploy.sh` las exige) y el arranque rechaza `console` fuera de `localhost`.

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
python -m pytest tests/test_BE05_sensitive_access_control.py -v   # un archivo
python -m pytest -k "INT02" -v                         # por patrón
```

`pytest.ini` ya incluye `-v --tb=short` en `addopts`. Nomenclatura:
`test_BE<NN>` = backend unitario, `test_INT<NN>` = integración con `TestClient` (BE09 a BE50 e INT03 a INT08 son de la feature de usuarios; F4 aporta BE42 a BE50), `test_FM01` = el doble de MongoDB.
`conftest.py` reemplaza `mail_service.send` en **todos** los tests por un buzón falso (`mailbox`), así que
ninguna prueba envía correo; `mailbox.fail_with` simula un fallo y `mailbox.last_token()` extrae el token del
último enlace.

> 🔸 **BRECHA (tests de sesión intermitentes en WSL2):** se observó que ~1 de cada 30 corridas de la suite
> falla un test de sesión (`BE12`, `BE32` o un test de `BE46` que usa un token recién emitido). Se
> instrumentó `get_current_user` y se capturó un `ImmatureSignatureError` («token aún no válido, `iat`»):
> **el reloj de pared del entorno salta hacia atrás** entre dos instantes del mismo test, y el token queda con
> `iat` en el futuro. No es un defecto de F4 ni de F3. **Mitigado** el 2026-10-19 con `leeway=10` en
> `jwt.decode` (commit `95b6d1b`, `test_BE52_*`); un fallo aislado de `BE32` sigue siendo posible (depende
> de que el cambio caiga en un segundo posterior al del login). Ver `05` §5.3c (D28).

**Dependencias de test:** `pip install -r backend/requirements-dev.txt` (`pytest`,
`pytest-asyncio`, `httpx`). Con el venv del proyecto sin `pip`, `uv pip install -r requirements-dev.txt`.

**Estrategia (`tests/conftest.py`):**
- **Ningún test toca una base real.** Un fixture automático reemplaza `app.main.db_service` y
  `run_bootstrap`, de modo que `TestClient(app)` no ejecuta el `lifespan` contra la MongoDB de
  desarrollo (D25).
- Las variables obligatorias de §2 se fijan al inicio de `conftest.py` con valores de prueba.
- Los tests de reglas de negocio de la feature usan `tests/fake_mongo.py`: una MongoDB en memoria
  con índices únicos (incluidos los parciales) que lanza el `DuplicateKeyError` real. Se verifica
  a sí misma en `test_FM01_*`. Fixtures: `fake_db`, `seed_users`, `bearer_for`, `prepare_org`.
- Los usuarios de prueba (`ADMIN_USER`, `DATOS_ADMIN_USER`, `EDITOR_USER`, `VIEWER_USER`,
  `NO_DATOS_USER`) tienen el modelo nuevo. `authenticated_as(user)` emite un JWT real.
- bcrypt corre con costo 4 en los tests (`_fast_bcrypt`).
- El doble no es MongoDB: lo que no simula lanza `NotImplementedError`. Para cambios de
  índices o consultas nuevas, verificar además contra un MongoDB real desechable
  (`docker run --rm -p 127.0.0.1:27018:27017 mongo:latest`).

**Frontend** — vitest + Testing Library con jsdom:

```bash
cd frontend
npm test                # vitest run
```

Suites `test_FE00` a `test_FE05`, `test_FE06` a `test_FE10`, `test_FE12`, `test_FE16`, `test_INT01` e `test_INT09`, en `frontend/src/tests/`.
`src/tests/setup.js` agrega a jsdom las APIs que Radix usa y jsdom no implementa (`hasPointerCapture`,
`scrollIntoView`, `matchMedia`); `usersFixtures.js` (no es un test) trae los datos y el enrutador de
`axios.get` de las pruebas de la vista de usuarios. `npm run lint` **no se puede ejecutar** (D20).

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
previo (§6.2). Nótese que `users`, `units` y `platforms` se dejan intactas a propósito: son datos de la
feature de usuarios y no vienen de `establishments.json`.

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

1. **Validación** — `.env` presente, Docker corriendo, y las siete variables críticas
   (`MONGO_ROOT_USERNAME`, `MONGO_ROOT_PASSWORD`, `JWT_SECRET`, `ADMIN_PASSWORD`, `DATABASE_NAME`,
   `BOOTSTRAP_ADMIN_EMAIL`, `ALLOWED_EMAIL_DOMAINS`) definidas y no vacías. Aborta si falta alguna.
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

**Desarrollo (SEC-1):** `docker-compose.yml` ya no trae `JWT_SECRET` ni `ADMIN_PASSWORD` literales; los
lee del `.env` de la raíz y `docker compose` se niega a levantar si faltan. Quien levante el entorno
debe tenerlos en su `.env` (el `JWT_SECRET` con ≥ 32 caracteres).

**HSTS (SEC-6):** `frontend/nginx.conf` escucha en `:80` y no puede emitir `Strict-Transport-Security`
(el TLS termina en un componente externo). Quien administre ese terminador debe agregarlo. El mismo
`nginx.conf` envía hoy una CSP en modo `Content-Security-Policy-Report-Only`: tras desplegar, abrir
Login, Directorio, una Ficha con mapa y el Dashboard con la consola abierta; si no hay violaciones,
renombrar el encabezado a `Content-Security-Policy` y reconstruir la imagen del frontend.

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
| Envía correo desde el backend (✅ F4) | `MAIL_MODE`, `PUBLIC_BASE_URL`, `GMAIL_*` y `GOOGLE_*` en los cuatro archivos y en `deploy.sh`; el consentimiento inicial de la casilla es una tarea manual (§9.1). **La imagen del backend se reconstruye** (`httpx` entra en `requirements.txt`). |
| Pasa el correo a SMTP (✅ ADR-017) | Código nuevo en `mail_service.py` y `config.py`: la imagen del backend se reconstruye, **sin dependencias nuevas** (`smtplib`). `SMTP_*` en los cuatro archivos y en `deploy.sh` (que las exige con `MAIL_MODE=smtp`); `.env.production.template` trae `MAIL_MODE=smtp`. Un entorno ya desplegado con `MAIL_MODE=gmail` sigue funcionando sin cambios. En el servidor: `SMTP_PASSWORD` solo en el `.env`, y **antes del primer despliegue probar la salida por el puerto 587** (§9). |
| Agrega un contador o una colección con TTL (✅ F4) | `ensure_indexes()` con `expireAfterSeconds`; comprobar que sigue siendo idempotente. Los índices nuevos de F4 (`auth_tokens`, `rate_limits`, `audit_log`, `subrogations`) se crean al arrancar. |
| Depende de la IP del cliente (rate limiting) | `--forwarded-allow-ips` en `Dockerfile.prod` y `X-Forwarded-For` en `nginx.conf`. **Verificar en el primer despliegue** que el proxy del host (delante de `127.0.0.1:8080`) reenvía `X-Forwarded-For`: de lo contrario el límite por IP se comparte entre todos. Prueba: dos fallos de login desde equipos distintos no deben sumarse en `db.rate_limits`. |
| Actualiza un entorno existente a F4 | Backup (`scripts/backup-mongo.sh`); `.env` con `MAIL_MODE` y `PUBLIC_BASE_URL`; `docker compose up -d --build backend` (dependencia nueva). Los usuarios `invited` creados antes de F4 tienen `invitation.last_error: "mail_not_configured"`: reenviarles la invitación. Rollback: tag `pre-usuarios-f4`; las colecciones nuevas las ignora el código anterior. |

---

## 8. Diagnóstico rápido

| Síntoma | Causa probable | Verificación |
|---|---|---|
| La base queda vacía al arrancar | Falta `backend/establishments.json` (git-ignored) | `docker compose logs backend \| grep "Seeding source file not found"` |
| El backend no arranca: `Variable de entorno obligatoria sin definir: …` | Falta una variable de §2 (contenedor creado con el compose anterior) | `docker compose up -d --build backend`; §1.3 |
| El login del admin falla | El admin ya existía: `ADMIN_PASSWORD` solo se usa para crearlo. Entrar con el correo o con `admin` y la contraseña vigente | `db.users.findOne({email:"<BOOTSTRAP_ADMIN_EMAIL>"})` · §1.3 |
| Un usuario recién creado no puede entrar | Queda `invited` hasta definir su contraseña con el enlace del correo | `invitation` en `GET /api/users/{id}`: `last_error` indica por qué no salió el correo (`mail_auth_failed`, `mail_send_failed`, `mail_timeout`); reenviar con `POST /api/users/{id}/invitation` |
| `429` al iniciar sesión | Rate limiting (5 fallos por cuenta+IP o 30 por IP en 15 min) | Cabecera `Retry-After`. Si **todos** los usuarios chocan a la vez, la IP no llega al backend: ver §7 |
| `MAIL_MODE=console solo se permite con PUBLIC_BASE_URL en localhost` | Se dejó `console` en un entorno con URL pública | Usar `MAIL_MODE=smtp` o `gmail` y completar las variables de §2.1 |
| Todas las llamadas a `/api` fallan en dev | Frontend fuera de Docker con el proxy apuntando a `backend:8000` | §1.2 |
| El mapa de la ficha dice "Ubicación no disponible" | La base se re-sembró y se perdió `location` | `db.establishments.countDocuments({location:{$exists:true}})` · §4.1 |
| El dashboard muestra ceros | No hay métricas del año 2026, que está hardcodeado | `db.metrics.countDocuments({year:2026})` · `03` §5.16 |
| Sesión que se cierra sola | Token expirado (180 min), usuario desactivado, contraseña cambiada, o un `401` que disparó el interceptor | `04` §1 |
| Todas las escrituras dan `403 untrusted_origin` tras iniciar sesión | `PUBLIC_BASE_URL` no es el origen exacto que ve el navegador (esquema, host, puerto), p. ej. se entra por `127.0.0.1` y la variable dice `localhost`, o el dominio público cambió | `.env` · ADR-016 |
| El backend pasa el healthcheck pero la app no funciona | `GET /` no consulta MongoDB | `03` §5.1 |
| El arranque falla al crear un índice | Se cambió la definición de un índice existente | `docker compose logs backend` · §7 |

---

## 9. Casilla remitente de correo (checklist manual)

> **Estado (2026-10-23): en producción el envío es por SMTP (ADR-017); el código está implementado y falta la
> parte manual.** Son tareas de la cuenta de Google y de Workspace que **ni el código ni un agente pueden
> hacer**: las ejecuta una persona. Hasta completarlas se trabaja con `MAIL_MODE=console`.
> El modo `gmail` (§9.1) sigue implementado como alternativa.

La casilla es `correos.automaticos@slepllanquihue.cl`: dedicada, no personal.

1. [ ] **Activar la verificación en dos pasos** en la cuenta de la casilla (sin ella Google no ofrece
   contraseñas de aplicación).
2. [ ] **Confirmar con TI** que el administrador de Workspace permite las contraseñas de aplicación. Si las
   desactiva, el envío falla con `mail_auth_failed`: usar el modo `gmail` (§9.1).
3. [ ] **Generar la contraseña de aplicación** (cuenta de Google → Seguridad → Contraseñas de aplicaciones).
   Se muestra una sola vez, en cuatro bloques de cuatro caracteres.
4. [ ] **Deshabilitar IMAP en la casilla** (Gmail → Configuración → Reenvío y correo POP/IMAP → *Inhabilitar
   IMAP*). Con IMAP habilitado, esa contraseña también permitiría leer la carpeta Enviados, que contiene
   enlaces de invitación vigentes (ADR-017). SMTP sigue funcionando.
5. [ ] **Guardarla como secreto** en el `.env` del servidor (`SMTP_PASSWORD`), junto con `SMTP_HOST`,
   `SMTP_PORT`, `SMTP_USERNAME` y `SMTP_SENDER_ADDRESS`. **Nunca** en el repositorio, en un log ni en un chat.
   Un script de prueba que la contenga **no se versiona**: bórralo o léela del entorno.
6. [ ] **Probar la salida por el puerto 587 desde el servidor de producción** (no desde un equipo de
   desarrollo): `nc -vz smtp.gmail.com 587` o equivalente. Si está bloqueado, pedir a TI abrirlo o usar el
   modo `gmail` (443).
7. [ ] **Si cambia la clave de la cuenta**, o un administrador revoca la contraseña de aplicación, generar una
   nueva (paso 3) y actualizar `SMTP_PASSWORD`. Mientras tanto los usuarios quedan `invited` y el error se
   ve en `users.invitation.last_error`; al restablecer el envío, el admin reenvía las invitaciones.
8. [ ] Confirmar con TI que el filtro de salida o de spam del dominio no bloquea los correos de la casilla
   antes de la primera alta masiva.

### 9.1 Alternativa: Gmail API (modo `gmail`, ✅ implementado en F4)

Solo si las contraseñas de aplicación dejan de estar permitidas. Ya no es el camino de producción.

1. [ ] **Elegir o pedir a TI la casilla remitente**: `@slepllanquihue.cl`, dedicada
   (notificaciones o no-reply), no personal. Si fuera personal, al irse su dueño o cambiar su
   contraseña se corta el envío para todos.
2. [ ] En el proyecto de Google Cloud del cliente OAuth existente, abrir la **pantalla de
   consentimiento** y confirmar que es de tipo **Internal**. Si fuera *External* en estado
   *Testing*, Google caduca el refresh token a los **7 días**.
3. [ ] Agregar el scope `https://www.googleapis.com/auth/gmail.send` (y ningún otro) al cliente.
4. [ ] Con la sesión de la casilla remitente abierta en el navegador, ejecutar **una sola vez**, desde
   cualquier equipo con el repositorio y Python (usa solo `httpx`, que ya está en `requirements.txt`):
   `cd backend && GOOGLE_CLIENT_ID=… GOOGLE_CLIENT_SECRET=… python scripts/gmail_consent.py`
   (con `--no-browser` imprime la URL). El cliente OAuth debe ser de tipo **«Aplicación de escritorio»**, o
   web con `http://127.0.0.1:8765/` **con la barra final**, registrada en ese mismo cliente, como URI de
   redirección autorizada (`--port` cambia el puerto; los cambios pueden tardar en propagarse). Un cliente
   web sin esa URI exacta falla con `redirect_uri_mismatch`. Pide
   solo el scope `gmail.send`, usa PKCE y verifica `state`. Imprime el **refresh token** por pantalla; no lo
   escribe en ningún archivo ni log (un test lo fija). Si Google no devuelve token (la cuenta ya consintió),
   revocar el acceso en `myaccount.google.com/permissions` y repetir.
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

## 10. Login con Google: checklist de la consola de Google Cloud (tarea manual)

> **El código está implementado (F6, ADR-015); estos pasos los hace una persona con acceso a la consola.**
> Sin ellos el botón de Google no aparece o Google rechaza el inicio de sesión.

1. [ ] **Orígenes de JavaScript autorizados** del cliente OAuth: `http://localhost:5173` y
   `https://datos.slepllanquihue.gob.cl`. **No hacen falta URIs de redirección**: la callback de Google
   Identity Services es de JavaScript.
2. [ ] Para pruebas locales la guía de Google Identity Services pide registrar además `http://localhost`
   (sin puerto); verificarlo contra la guía vigente si el botón no aparece.
3. [ ] **Navegar siempre por `localhost`, no por `127.0.0.1`**: son orígenes distintos para Google.
4. [ ] La pantalla de consentimiento debe ser de tipo **Internal** (§9, paso 2).
5. [ ] `GOOGLE_CLIENT_ID` definido en el `.env` del entorno (el frontend lo obtiene de `GET /api/auth/config`).
6. [ ] **`GOOGLE_AUTO_PROVISION`:** en desarrollo, `true` en el `.env`; en producción, `false` hasta que el
   responsable decida activarla (condiciones en `04` §9.6 y ADR-015). Cambiarla exige reiniciar el backend.
7. [ ] Primer despliegue: comprobar que el proxy del host reenvía `X-Forwarded-For` (§7). Si no, el límite
   por IP de `/api/auth/google` se comparte entre todos los usuarios.
8. [ ] Tras desplegar, **rebuild** de las imágenes del backend (dependencias `google-auth` y `requests`) y
   del frontend (`nginx.conf`).
9. [ ] **Retiro de `licenses` (N15):** tras desplegar, `python scripts/retire_licenses.py` (cuenta, no modifica) y,
   con respaldo previo (`scripts/backup-mongo.sh`), `--apply`. Si el conteo de documentos «con al menos una
   credencial» no es 0, **rotar esas credenciales** en cada plataforma externa: borrarlas de Mongo no las
   invalida y siguen en los respaldos anteriores. La aplicación ya no lee ni sirve el campo aunque exista.
10. [ ] **Conectividad en tres bloques:** con respaldo previo (`scripts/backup-mongo.sh`), desde `backend/`:
   `python scripts/migrate_connectivity.py --excel <DASHBOARD_final.xlsx> --report vista_previa.csv` muestra,
   sin modificar nada, cómo queda cada establecimiento y las notas para revisar; con `--apply` escribe. Es
   idempotente. Sin `--excel` el bloque «otro tipo» queda sin tipo, vencimiento ni OC. Hasta migrar, la
   ficha y el gráfico convierten al vuelo; guardar una ficha la deja migrada (sin los datos de la planilla).
   Para una instalación nueva: `--from-json establishments.json --excel … --write-json <salida>` deja el JSON
   de siembra ya convertido (el seeding igual convierte el JSON antiguo, sin la planilla).
11. [ ] **Datos por año (ADR-018):** con respaldo previo, desde `backend/`, `python scripts/fix_metrics_cutoffs.py`
   (vista previa) y luego `--apply`: vacía la asistencia 2025 copiada en los registros 2026, marca el corte
   `2026-03` de la matrícula 2026 y deja `status: active` en los establecimientos sin estado. Idempotente.
12. [ ] **Cookie de sesión (ADR-016):** `PUBLIC_BASE_URL` debe ser **exactamente** el origen público
   (`https://datos.slepllanquihue.gob.cl`, sin barra final): con `https`, la cookie sale `Secure`; y toda
   escritura valida `Origin` contra ese valor. El proxy del host **no debe** quitar la cabecera `Origin` ni
   `Set-Cookie`. Tras el primer despliegue, todos los usuarios vuelven a iniciar sesión una vez.

---

## 11. Revisión del proxy del host (tarea manual, guía paso a paso)

> **Por qué.** La aplicación no se publica sola: delante de `127.0.0.1:8080` (frontend, `docker-compose.prod.yml`)
> hay un proxy del **host** que termina TLS y que **no está en este repositorio** (D29, D35). Tres garantías de
> seguridad dependen de él: la IP real del cliente (rate limiting), la cookie `Secure` y el `Origin` (ADR-016), y
> HSTS. Esta guía se ejecuta una vez por despliegue y cada vez que alguien cambie ese proxy.

```
navegador ──https──▶ PROXY DEL HOST ──http──▶ 127.0.0.1:8080 (nginx del frontend) ──▶ backend:8000 (gunicorn)
 (IP real)            (TLS, XFF, HSTS)         (cabeceras de seguridad, /api)         (rate limit usa la IP)
```

### 11.1 Encontrar el proxy y su configuración

```bash
sudo ss -ltnp | grep -E ':(80|443)\b'          # qué proceso escucha en 80/443 (nginx, apache2, caddy, traefik, haproxy…)
sudo nginx -T 2>/dev/null | less                 # nginx: configuración EFECTIVA completa (incluye los include)
                                                  # buscar el bloque con `server_name datos.slepllanquihue.gob.cl`
# Apache: apachectl -S   ·   Caddy: caddy adapt --config /etc/caddy/Caddyfile   ·   Traefik/HAProxy: su archivo de configuración
```

### 11.2 Lista de verificación (qué mirar, cómo probarlo desde afuera y cómo se ve lo correcto)

| # | Qué comprobar | Prueba (desde tu equipo, no desde el servidor) | Correcto | Incorrecto |
|---|---|---|---|---|
| 1 | **HTTP redirige a HTTPS** | `curl -sI http://datos.slepllanquihue.gob.cl/` | `301`/`308` con `Location: https://…` | `200` sobre http |
| 2 | **Certificado vigente y completo** | `echo \| openssl s_client -connect datos.slepllanquihue.gob.cl:443 -servername datos.slepllanquihue.gob.cl 2>/dev/null \| openssl x509 -noout -issuer -dates` | `notAfter` en el futuro; emisor reconocido | vencido o autofirmado |
| 3 | **Solo el proxy es alcanzable** (ni backend ni Mongo ni el puerto 8080 desde fuera) | `nmap -Pn -p 80,443,8000,8080,27017 datos.slepllanquihue.gob.cl` | solo 80 y 443 abiertos | 8000, 8080 o 27017 abiertos |
| 4 | **Destino correcto** | en la config: `proxy_pass http://127.0.0.1:8080;` | apunta a `127.0.0.1:8080` | apunta a otro puerto o a `backend:8000` |
| 5 | **`X-Forwarded-For` se SOBRESCRIBE** (la comprobación más importante, D35) | ver 11.3 | `proxy_set_header X-Forwarded-For $remote_addr;` y el límite da `429` aunque cambies la cabecera | `$proxy_add_x_forwarded_for` (agrega): la IP la elige quien llama |
| 6 | **`X-Forwarded-Proto` y `Host`** | en la config: `proxy_set_header X-Forwarded-Proto $scheme;` y `proxy_set_header Host $host;` | presentes | ausentes |
| 7 | **La cookie de sesión sale `Secure`** (confirma https y que `Set-Cookie` no se pierde) | `curl -si -X POST https://HOST/api/auth/login -H 'Content-Type: application/json' -d '{"username":"TU_CORREO","password":"TU_CLAVE"}' \| grep -i set-cookie` | `slep_session=…; HttpOnly; Path=/api; SameSite=strict; Secure` | sin `Secure`, o sin `Set-Cookie` |
| 8 | **`Origin` llega intacto** (ADR-016) | iniciar sesión en el navegador y guardar un cambio en cualquier ficha | se guarda | `403 untrusted_origin` en toda escritura → `PUBLIC_BASE_URL` no coincide con el origen público, o el proxy altera `Origin` |
| 9 | **HSTS** | `curl -sI https://HOST/ \| grep -i strict-transport` | `Strict-Transport-Security: max-age=…` (empezar con `300`, subir a `31536000` cuando todo funcione) | ausente (se agrega en el proxy: `add_header Strict-Transport-Security "max-age=300" always;`) |
| 10 | **Las cabeceras del frontend pasan** (no las pisa ni duplica) | `curl -sI https://HOST/ \| grep -iE 'x-frame\|nosniff\|content-security\|referrer-policy\|permissions-policy'` | una vez cada una | faltan o están repetidas |
| 11 | **No cachea `/api`** | en la config: sin `proxy_cache` para `/api/`; `curl -sI -X POST …/api/auth/login` trae `Cache-Control: no-store` | sin caché | respuestas de `/api` en caché |
| 12 | **Tamaño de cuerpo** (CSV de importación: 1 MiB + multipart) | en la config: `client_max_body_size 2m;` (también en el `nginx.conf` del frontend, hoy usa el default de 1 MB) | ≥ 2 MB | default `1m`: un CSV legítimo da `413` desde el proxy |
| 13 | **Host desconocido** | `curl -sI -H 'Host: otro.example' https://IP_DEL_SERVIDOR/ -k` | cerrado (`444`) o 404 | sirve la aplicación para cualquier `Host` |

### 11.3 La comprobación 5, en detalle (`X-Forwarded-For`)

**Qué pasa por dentro.** El backend corre con `--forwarded-allow-ips "*"`: confía en cualquiera que le hable y
toma como IP del cliente **la dirección más a la izquierda** de `X-Forwarded-For`. Lo verificamos con el código de
uvicorn de este repo:

```
cliente miente "9.9.9.9" y el proxy AGREGA la real  →  X-Forwarded-For: 9.9.9.9, 203.0.113.7, 172.18.0.1  →  backend ve 9.9.9.9   ✗
el proxy SOBRESCRIBE con $remote_addr               →  X-Forwarded-For: 203.0.113.7, 172.18.0.1          →  backend ve 203.0.113.7 ✓
```

Si el proxy agrega, un atacante cambia la cabecera en cada petición y **nunca llega al límite** de login,
canje de enlaces ni `/api/auth/google`.

**Prueba funcional** (usa un correo inexistente; no toca cuentas reales). Hace 7 intentos fallidos cambiando la
IP inventada; el límite es de 5 por (cuenta + IP):

```bash
for i in 1 2 3 4 5 6 7; do
  curl -s -o /dev/null -w "%{http_code} " -X POST https://datos.slepllanquihue.gob.cl/api/auth/login \
    -H 'Content-Type: application/json' -H "X-Forwarded-For: 10.0.0.$i" \
    -d '{"username":"prueba-proxy@slepllanquihue.cl","password":"x"}'
done; echo
```

- ✅ **`401 401 401 401 401 429 429`**: el proxy ignora lo que inventa el cliente. Correcto.
- ❌ **`401 401 401 401 401 401 401`**: la IP es falsificable. Corregir el proxy (ver abajo).
- ❌ **`429` desde otro equipo con el mismo correo**: el proxy no reenvía la IP y todos comparten un contador.

Ver la cadena que recibe el frontend (el `nginx` interno la imprime al final de cada línea del log):

```bash
curl -s -o /dev/null -H 'X-Forwarded-For: 9.9.9.9' https://datos.slepllanquihue.gob.cl/api/auth/password-policy
docker compose -f docker-compose.prod.yml logs --tail=3 frontend      # el último campo entre comillas es X-Forwarded-For
```

Correcto: el primero de la lista es **tu IP pública** (no `9.9.9.9`). Después, borrar los contadores de la prueba
(expiran solos en 15 min) o esperar.

**Corrección en el proxy del host** (nginx): en el bloque que hace `proxy_pass`,

```nginx
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $remote_addr;      # SOBRESCRIBE: nunca $proxy_add_x_forwarded_for en el borde
proxy_set_header X-Forwarded-Proto $scheme;
```

**Corrección propuesta en el repositorio** (no aplicada; defensa en profundidad, funciona aunque el proxy del host
agregue): en `frontend/nginx.conf`, confiar solo en la red de Docker y quedarse con la última dirección no
confiable, y reenviar una sola IP:

```nginx
set_real_ip_from 172.16.0.0/12;     # la red de Docker: el único que habla con este nginx es el proxy del host
real_ip_header X-Forwarded-For;
real_ip_recursive on;               # toma la dirección más a la derecha que NO sea de confianza (la que añadió el proxy del borde)
# ... y en `location /api/`:
proxy_set_header X-Forwarded-For $remote_addr;      # una sola IP, ya limpia
```

Requiere reconstruir la imagen del frontend y repetir la prueba. Se registró como D35 (`05` §5).

### 11.4 Registro de la revisión

Anotar en el cambio o ticket: fecha, quién revisó, versión de la configuración del proxy, resultado de las 13
comprobaciones y, si falló alguna, cuándo se corrigió y se repitió.

