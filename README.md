# Sistema de Gestión de Establecimientos — SLEP Llanquihue

Plataforma web interna para consultar y mantener la ficha técnica de los establecimientos
educacionales del SLEP Llanquihue (78 establecimientos, 5 comunas), con sus métricas anuales,
sus contrapartes técnicas, un mapa de ubicación y la gestión de usuarios y accesos por plataforma.

| | |
|---|---|
| **Estado** | **Alfa — versión 0.2.x, segunda iteración en curso** |
| **Backend** | FastAPI + Motor / MongoDB |
| **Frontend** | React 18 + Vite + React Router + shadcn/ui (Tailwind) + MapLibre |
| **Despliegue** | Docker Compose (`docker-compose.yml` desarrollo, `docker-compose.prod.yml` producción) |

## Inicio rápido

```bash
docker compose up --build
```

| Servicio | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API y documentación interactiva | http://localhost:8000/docs |

Antes de la primera vez hace falta `backend/establishments.json` (datos reales del servicio, está
en `.gitignore`; se pide a quien mantiene el proyecto). Las credenciales iniciales, las variables de
entorno obligatorias y el rebuild del frontend cuando cambian sus dependencias están en
[`Documentacion/07-operacion.md`](Documentacion/07-operacion.md) §1.

## Verificación

```bash
cd backend  && python -m pytest -v
cd frontend && npm test
cd frontend && npm run build
```

`npm run lint` **no se puede ejecutar todavía** (ESLint no está declarado; brecha D20).

## Documentación

Empieza por [`Documentacion/00-README.md`](Documentacion/00-README.md): glosario y una tabla
«quiero hacer X → lee Y». Las reglas de ingeniería del repositorio están en [`CLAUDE.md`](CLAUDE.md).

## Madurez: de alfa a beta

Hoy es **alfa** porque el alta de punta a punta todavía no se ha probado en producción: el backend ya la
resuelve (F6: login con Google y alta automática como lector; F4: invitación y restablecimiento por enlace como
vía alternativa), pero la alta automática está **desactivada fuera de desarrollo** hasta que el usuario decida
activarla. Se considera **beta**, y la versión pasa a `0.3.0`, cuando se cumplan **todos** estos criterios:

1. **Alta de punta a punta = entrar con Google.** Quien tiene una cuenta del dominio permitido entra con Google y
   obtiene su cuenta de lector sin que nadie la cree (alta automática, `GOOGLE_AUTO_PROVISION=true`), y un admin
   global le asigna después su pertenencia y sus accesos. *Backend ✅ (F6, ADR-015, verificado con tests).
   Falta: que el usuario active `GOOGLE_AUTO_PROVISION` en producción (sus requisitos SEC-1…6 y el retiro de
   `licenses` ya están cumplidos), la consola de Google (`07` §10) y la interfaz para asignar cuentas «sin
   asignar» (D33). La invitación por correo (F4) queda como vía para cuentas fuera de Google y necesita la
   casilla remitente (`07` §9) y la pantalla `/definir-contrasena`, que ya no bloquean la beta.*
2. **Protección del acceso:** rate limiting en el login, el restablecimiento y el canje de enlaces, y auditoría
   de los cambios de usuarios y accesos. *✅ F4; falta comprobar en producción que el proxy del host reenvía
   `X-Forwarded-For` (`07` §7).*
3. **Brechas abiertas de seguridad y datos resueltas:** ~~D5~~ (✅ F6, SEC-4) y D6 (el año 2026 fijo en los
   pipelines del dashboard; si no se corrige, desde enero de 2027 el dashboard muestra datos viejos sin
   avisar). Además, D35 (el límite por IP puede evadirse si el proxy del host *agrega* a `X-Forwarded-For`).
   Tabla en
   [`05-guia-de-extension.md`](Documentacion/05-guia-de-extension.md) §5.
4. **Producción ensayada:** un despliegue con `docker-compose.prod.yml` y un backup con su
   restauración probados al menos una vez (`07` §5 y §6).
5. **Primeros usuarios reales** distintos del administrador, en el entorno de producción.

Se llegará a **1.0** con la API versionada (D10) y una iteración completa sin cambios que rompan
el contrato.

## Changelog

Más reciente arriba. **Despliegue** indica lo que hay que hacer al actualizar un entorno existente;
**Brechas** remite a la tabla de deuda de `05` §5 (✅ resuelta, 🔸 sigue abierta).
La numeración 0.x es una etiqueta de este documento: el repositorio aún no tiene tags de versión
(`pre-usuarios-f3`, `pre-usuarios-f4`, `pre-usuarios-f6` y `pre-usuarios-f6-s3`, los puntos de rollback de cada fase). F4 y F6 siguen
**sin mergear a `master`**: viven encadenadas en `feature/usuarios-f4` → `feature/usuarios-f6` → `feature/usuarios-f6-s3`.

### Iteración 2 — 0.2.x (en curso, desde 2026-09-15)

| Fecha | Tipo | Cambio | Despliegue | Brechas | Commit |
|---|---|---|---|---|---|
| 2026-10-23 | feat | **Correo por SMTP con contraseña de aplicación** (ADR-017, C25): `MAIL_MODE` admite `smtp`, `gmail` y `console`; TLS verificado en los puertos 587 y 465, sin dependencias nuevas. El modo `gmail` y `gmail_consent.py` se conservan como alternativa | Variables nuevas **`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SENDER_ADDRESS`** (obligatorias con `MAIL_MODE=smtp`; `deploy.sh` las exige). Antes del primer envío: tareas manuales de `07` §9 (verificación en dos pasos, contraseña de aplicación, IMAP deshabilitado, salida por el puerto 587). Rebuild del backend por el cambio de código. Rollback: tag `pre-ficha-smtp` | — | `5ac31aa` |
| 2026-10-22 | feat | **Ficha: edición de estadísticas por año y capacidades por rol; conectividad en tres bloques** (2030, BAM y otro tipo) con migración idempotente | `scripts/migrate_connectivity.py` (vista previa sin `--apply`; **respaldo antes de aplicar**). Hasta migrar, la ficha convierte al vuelo. Rollback: tag `pre-ficha-smtp` y restaurar el respaldo si se aplicó la migración | — | `2950d47` `b235e79` |
| 2026-10-20 | feat | **F6 S3 — Sesión en cookie `HttpOnly`** (`SameSite=Strict`, `Path=/api`) en lugar de `localStorage` (ADR-016) y diseño zero trust para recibir cuentas autoaprovisionadas; guía de revisión del proxy | `PUBLIC_BASE_URL` debe ser el **origen exacto del navegador** o toda escritura da `403 untrusted_origin` (en desarrollo, entrar por `localhost`, no `127.0.0.1`). Rollback: tag `pre-usuarios-f6-s3` | D35 🔸 | `864abd7` `40c89db` |
| 2026-10-20 | feat | **F6 S2 — Login con Google y alta automática como lector** (ADR-015, C24): `POST /api/auth/google`, `GET /api/auth/config`, cuentas «sin asignar» (`is_slep_staff` nulo), filtro `assignment=unassigned`; **se retira el campo `licenses`** (N15) | Variable nueva **`GOOGLE_AUTO_PROVISION`** (obligatoria; en producción la activa solo el usuario); `google-auth` y `requests` (rebuild del backend); si hubo datos reales, `scripts/retire_licenses.py --apply` y rotar esas credenciales. Rollback: tag `pre-usuarios-f6` | D33 🔸 D34 🔸 | `cce0490` `f3fd20f` |
| 2026-10-20 | feat | **F6 S1 — Línea base de seguridad (SEC-1…6):** `JWT_SECRET` ≥ 32 caracteres sin placeholders, claims `exp/iat/sub` obligatorios, `logout` y desactivación cortan todas las sesiones (`sessions_revoked_at`), `re.escape` en los filtros del directorio, sin CORS, cabeceras de seguridad y CSP en modo *Report-Only* | `JWT_SECRET` y `ADMIN_PASSWORD` se leen del `.env` también en desarrollo; `frontend/nginx.conf` cambia (rebuild del frontend) | D5 ✅ | `060f10b` |
| 2026-10-19 | fix | `leeway=10` en la validación del JWT (reloj de WSL2) | Ninguno | D28 ✅ | `95b6d1b` |
| 2026-10-09 | feat | **F4 — Primer acceso y operaciones masivas (backend):** correo con `MAIL_MODE=console\|gmail`, invitación, reenvío, restablecimiento y canje de enlaces de un solo uso; CSV con vista previa, alta masiva parcial y operaciones masivas; subrogancias y vínculo opcional contraparte↔usuario; auditoría de solo agregado y rate limiting de login (US-14…16, 19…22, 30…36, 45…47) | **`.env` con `MAIL_MODE` y `PUBLIC_BASE_URL`** (obligatorias); `docker compose up -d --build backend` (`httpx` nuevo; `Dockerfile.prod` cambia); índices nuevos al arrancar; backup previo; verificar la IP real tras el proxy del host. Rollback: tag `pre-usuarios-f4` | límites nuevos D26…D32 (`05` §5.3c) | `e98cdc8`…`a8d57b7` |
| 2026-10-07 | fix | Menú lateral colapsable fluido: los íconos no se mueven al animar y el botón pasa a ser un tirador discreto sobre el borde | Ninguno (Vite recarga solo) | — | `e302957` |
| 2026-10-07 | feat | **F5 — Vista de gestión de usuarios** en *Configuración › Usuarios*: lista con filtros en la URL, crear y editar, accesos por plataforma, desactivar y reactivar, acciones masivas (US-39, US-40) | Dependencias nuevas del frontend: `docker compose up -d --build --renew-anon-volumes frontend` (sin `-V` queda el `node_modules` viejo) | D18 ✅ D19 ✅ | `9a428a9` `7e252d1` |
| 2026-10-06 | doc | Decisiones de F4: acceso a credenciales para editores (C20), auditoría y rate limiting | Ninguno | — | `c8cda6f` |
| 2026-10-02 | feat | **F3 — Identidad y acceso por plataforma:** usuarios con roles por plataforma, unidades en jerarquía, perfil propio, política de contraseñas NIST SP 800-63B, revocación de sesiones (US-02…26) | Variables **sin default** (`JWT_SECRET`, `ADMIN_PASSWORD`, `BOOTSTRAP_ADMIN_EMAIL`, `ALLOWED_EMAIL_DOMAINS`); nueva dependencia `email-validator` (y `requirements-dev.txt` para correr los tests); recrear el contenedor del backend; backup previo. El admin existente se migra solo. Rollback: tag `pre-usuarios-f3` | D2 ✅ D3 ✅ D4 ✅ D22 ✅ | `8c52445`…`6f0913e` |
| 2026-10-02 | test | Los tests ya no escriben en la base de desarrollo y las pruebas INT02 verifican de verdad la redacción de datos sensibles | Ninguno | D24 ✅ D25 ✅ | `edbdd0b` |
| 2026-10-02 | doc | Diseño de la feature de usuarios e IAM (F1–F2): ADR-009 a ADR-014, modelo de datos y contrato | Ninguno | — | `49ad2b9` `5f0868c` `5c17938` |
| 2026-09-29 | feat | Mapa con MapLibre que geolocaliza el establecimiento en su ficha | Ninguno | — | `435c9d3` |
| 2026-09-28 | doc / fix | Documentación técnica modular (`Documentacion/00…07`); el seeding se delega a `seed_service` y ahora conserva `location` al recrear la base | Ninguno | D1 ✅ | `3807745` `ce0050d` |
| 2026-09-15 | feat | **Rutas y mapa:** migración a React Router (rutas `/dashboard`, `/establecimientos/:rbd`…, `ProtectedRoute`, `AppLayout`), shadcn/ui en las vistas existentes, campo `location`, índices de MongoDB e importador de coordenadas desde KMZ | Dependencias nuevas del frontend (rebuild); los índices se crean al arrancar el backend; el KMZ se importa a mano (`07` §4.2) | — | `3692afd` `e3d1914` `40114d3` |
| 2026-09-15 | test | Primera suite de tests: backend (BE01–BE08, INT02) y frontend (FE00–FE06, INT01) | Ninguno | — | `f167cff` `5b0984e` |

Pendiente de esta iteración: la interfaz de administración sobre lo que F4 y F6 dejaron en el backend (asignar
las cuentas «sin asignar», reenviar y restablecer, importación CSV, acciones masivas contra `POST /api/users/bulk`
y, solo si se usa la vía por correo, `/definir-contrasena`), la página de unidades, «Mi perfil» y la casilla
remitente de Gmail; y las decisiones del usuario sobre la recepción de cuentas autoaprovisionadas (Z1…Z3,
`04` §9.6.1). F7 (interconexión entre plataformas) sigue siendo solo diseño.

### Iteración 1 — 0.1.x (2026-07-02 a 2026-09-08)

| Fecha | Tipo | Cambio | Despliegue | Brechas | Commit |
|---|---|---|---|---|---|
| 2026-09-08 | feat / fix | Se incorporan al repositorio la skill y el MCP de shadcn (preparan el refactor del frontend); el backend agrega `EstablishmentSummary` y paginado para reducir datos transferidos (el propio commit lo marca «sin uso») | Ninguno | — | `86cfbf8` `6b679b0` |
| 2026-07-02 → 08-18 | feat / fix | Base del sistema: dashboard, directorio de establecimientos y ficha individual con el backend completo; correcciones del filtro de categoría, las leyendas de los gráficos y un bucle de cierre de sesión | — | — | `cea6bf3` … `9d01e73` |
