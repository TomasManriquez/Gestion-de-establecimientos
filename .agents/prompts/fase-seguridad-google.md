# Prompt · F6: línea base de seguridad y login con Google

> **Uso:** mensaje inicial de una sesión nueva de agente, abierta en la raíz del repositorio.
> **Es implementación, no planificación.** Estado verificado el 2026-10-19 contra el repo (rama
> `feature/usuarios-f4`, F5 ya mergeada en `master`) y contra `Documentacion/`.
> Complementa a `feature-usuarios-iam.md`, que es el diseño de la feature completa y ya está
> implementado en F3 a F5. Léelo solo por §3 (modelo) y §8 (interconexión) si lo necesitas.

---

## 0. Cómo trabajas

1. Lee `CLAUDE.md`. Sus reglas son vinculantes.
2. Lee `Documentacion/00-README.md`, `04-seguridad-y-acceso.md` completo (en especial §9),
   `03-api-contract.md` §8 y `06-decisiones-adr.md` ADR-006, 009, 012, 013 y 014.
3. **Alcance: solo la parte técnica.** Backend, `nginx.conf` y el botón del login. No toques la
   interfaz de administración ni el segmento de creación de usuarios (F4): su cierre queda para
   después (decisión N17).
4. **Regla anti-sobreingeniería (explícita del usuario).** La meta es una plataforma robusta que
   evite lo básico: secuestro de sesión, inyección de código y bypass del token. Cada cambio de
   este prompt cierra una brecha concreta de §3 o implementa C24. Si propones algo que no cierre
   una brecha nombrada, no lo hagas. §6 lista lo que queda fuera.
5. **Orden y rollback (regla 4: `auth` es punto único de falla).** **Parte de `feature/usuarios-f4`**
   (o de `master` actualizado, si el usuario ya mergeó F4), nunca del `master` local desactualizado:
   esa rama trae el rate limiting (`rate_guard`, `rate_hit`) que S2 reutiliza y el `leeway` de D28
   (commit `95b6d1b`). **Mientras dure F6 eres el único agente que escribe en este repositorio:** el
   agente de la feature principal está en pausa por decisión del usuario. Antes de empezar,
   `git status` no debe mostrar cambios sin commitear en `backend/` ni en `frontend/`; si los ves,
   detente y pregunta. Crea el tag `pre-usuarios-f6` (convención de `pre-usuarios-f3` y
   `pre-usuarios-f4`) y la rama `feature/usuarios-f6`. Trabaja en tres pasos, cada uno con su
   commit y su evidencia:
   - **S1** · Endurecimiento sin cambio de comportamiento (§3).
   - **S2** · Login con Google y alta automática (§4).
   - **S3** · Cookie `HttpOnly`, **solo si el usuario la aprueba** (§5, D-C).
6. **Evidencia (regla 2).** Muestra la salida real de los tests antes y después de cada paso.
   Tienen que estar en verde: BE03, BE05, BE11, BE12, BE13, BE14, BE47, INT02, INT03 e INT04.
   **Línea base verificada por el usuario el 2026-10-19: `596 passed`** (`cd backend && python -m
   pytest -v`, desde WSL con el `.venv` del repo, que es de tipo Linux). Si no puedes ejecutar los
   tests desde tu entorno, pide al usuario el comando exacto y espera su resultado. Un test que falle
   de forma intermitente (~1 de cada 30 corridas) con `ImmatureSignatureError` es el reloj de WSL2,
   que salta hacia atrás (D28), no tu cambio: reintenta. El `leeway=10` ya commiteado (`95b6d1b`)
   debería eliminarlo; si reaparece, repórtalo.
7. IDs de tests: usa el siguiente libre y compruébalo con `ls backend/tests`. Al escribir este
   prompt, el último `BE` es BE50 y el último `INT` es INT09.
8. **Precondiciones del entorno (verificadas el 2026-10-20).** Tests: `596 passed` en `9976d57`.
   El `.env` del usuario define `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y
   `GOOGLE_AUTO_PROVISION=true` (solo desarrollo), y el usuario configuró los orígenes de
   JavaScript en la consola de Google. **Antes de S1, comprueba sin imprimir valores (solo
   longitudes y booleanos) que el `JWT_SECRET` del `.env` no sea el valor legado del repositorio
   ni un placeholder:** SEC-1 los rechaza y la aplicación no arrancaría. Si lo es, detente y pide
   al usuario que lo regenere (`python -c "import secrets; print(secrets.token_hex(64))"`). Hoy el
   compose de desarrollo usa un literal y no lee `JWT_SECRET` del `.env`; eso cambia con SEC-1.
   `GOOGLE_AUTO_PROVISION` está en el `.env`, pero ningún compose lo pasa todavía: agrégalo en S2.

---

## 1. Lo que ya está hecho (no lo rehagas)

| Protección | Dónde | Test |
|---|---|---|
| Secretos sin default y fail-fast al arrancar | `config.py` (`_required`) | BE14 |
| HS256 fijado, `sub = str(_id)`, 401 uniforme, usuario releído en cada request, rol tomado del documento y no del token | `auth_service.get_current_user` | BE11 |
| Sesión cortada por desactivación y por cambio de contraseña | `auth_service.py:319-326` | BE11 |
| Rate limiting de login, canje y reenvío, con contadores en Mongo | `auth_service.rate_*`, `auth_controller._limited_login` | BE47 |
| Enlaces de un solo uso con hash sha256 y token en el fragmento (`#`) | `auth_service.issue_link_token` | BE46 |
| `require_access` en toda ruta, con lista de excepciones verificada | `auth_service.require_access` | BE12, INT03 |
| El `PUT` no devuelve credenciales; `[REDACTED]` no sobrescribe el valor real | `establishments_*` | BE13, INT04 |
| Inyección de operadores en el login y en las escrituras | `LoginRequest`, modelos con `extra="forbid"` | BE11, INT08 |
| Búsqueda de usuarios con `re.escape` | `users_service.py:148` | INT08 |
| El popup del mapa escapa el HTML; no hay `dangerouslySetInnerHTML` | `EstablishmentMap.jsx:69-70` | — |
| En producción solo `/api/` se enruta al backend, y el backend no se publica: `/docs` y `/openapi.json` **no son alcanzables**, así que no hace falta deshabilitarlos | `nginx.conf`, compose de producción | BE47 |

---

## 2. Decisiones cerradas de esta fase

| # | Decisión |
|---|---|
| G1 | **Alta automática como lector (C24).** Quien entra con una cuenta del dominio permitido y no existe obtiene una cuenta con `status: "active"`, `access: [{platform_id: "datos", role: "viewer"}]` y pertenencia **sin asignar**. El rol sale del servidor, nunca del token de Google. Se controla con `GOOGLE_AUTO_PROVISION` (variable obligatoria, sin default). |
| G2 | **N14 = no.** No se asigna nada automáticamente: ni establecimiento, ni cargo, ni siquiera a los directores. Todas las cuentas nuevas quedan sin asignar hasta que un admin global las asigne. |
| G3 | **N15: `licenses` se dará de baja.** No construyas nada nuevo sobre `licenses`. Mientras el campo exista, la redacción actual se mantiene y sus tests (BE05, BE13, INT02, INT04) siguen en verde. El retiro es una tarea aparte. |
| G4 | **N16 y N18: el dominio incluye estudiantes y cuentas de servicio, y el usuario lo acepta de forma consciente** porque el contenido de `datos` es público dentro de la organización. Consecuencia que no se debe olvidar: **pertenecer al dominio no significa ser funcionario.** Por eso todo recurso que no sea público (por ejemplo, el futuro `/personas`) se protege con un acceso explícito por plataforma lógica, nunca con el dominio del correo ni con `is_slep_staff` (ver `feature-usuarios-iam.md` §12). |
| G5 | **N17: esta fase tiene prioridad.** El cierre del segmento de creación de usuarios (F4) queda para después. |
| G6 | **El rol `viewer` no escribe y no ve credenciales.** Ya lo garantizan BE12 y BE13. No debilites esa matriz. |

---

## 3. S1 · Línea base de seguridad (sin cambio de comportamiento)

Cada fila es una brecha verificada en el código, con su cambio mínimo y su test.

| ID | Amenaza | Brecha verificada | Cambio mínimo | Test |
|---|---|---|---|---|
| SEC-1 | Bypass del token | `JWT_SECRET` solo se valida como "no vacío" (`config.py`); cualquier placeholder pasa. El compose de desarrollo trae un secreto literal versionado en git (`docker-compose.yml:24`; `ADMIN_PASSWORD` también, línea 28). | Exigir al menos 32 caracteres y rechazar los placeholders conocidos (los de `.env.production.template` y el valor legado del repo). El compose de desarrollo lee `${JWT_SECRET}` y `${ADMIN_PASSWORD}` del `.env` de la raíz. `test_BE14_every_env_var_declared…` debe seguir en verde. **Los fixtures de test usan hoy una clave de 12 bytes** (la salida de BE11 ya emite `InsecureKeyLengthWarning`): súbela a 32 o más al introducir el mínimo. | BE51 |
| SEC-2 | Bypass del token | `jwt.decode` no exige claims (`auth_service.py:308`): un token firmado sin `exp`, sin `iat` o sin `sub` no se rechaza por eso. | `options={"require": ["exp", "iat", "sub"]}`. Probar también `alg: none` y un token HS512. **El `leeway=10` de D28 ya está commiteado en esa misma llamada** (`95b6d1b`): agrega `options` sin quitarlo. | BE52 |
| SEC-3 | Secuestro de sesión | `POST /logout` no hace nada (`auth_controller.py:73-77`). La revocación solo existe para cuentas con contraseña local (`auth_service.py:319-326`): **una cuenta de Google no tiene `password_changed_at`**, así que su token robado no se puede cortar sin desactivar a la persona. Además, reactivar a un usuario desactivado revive sus tokens todavía vigentes. | Campo `sessions_revoked_at` en `users`. `get_current_user` rechaza los tokens con `iat` anterior a `max(password_changed_at, sessions_revoked_at)`. Lo fijan `POST /logout` (ahora autenticado; devuelve 204 aunque el token ya no sirva), la desactivación y el restablecimiento. El logout corta **todas** las sesiones de esa persona: es la forma sin estado, y el efecto debe quedar documentado. | BE53 |
| SEC-4 | Inyección | D5 sigue abierta en `establishments_service.py:39-60`: seis `$regex` con texto del usuario sin `re.escape` (`search`, `comuna`, `area_type`, `coverage`, `adp`). Con C24 los alcanza cualquier cuenta del dominio. | `re.escape` en los seis, con el mismo patrón de `users_service.py:148`. | INT10 (tabla de INT08: `(a+)+$`, `.*`, `comuna[$ne]=x`). Cierra D5 (criterio 3 de beta del README; D6 sigue abierta y no es de esta fase) |
| SEC-5 | Secuestro / CSRF | `main.py:56-63` permite cualquier origen con credenciales. Hoy es inofensivo porque el token va en una cabecera, pero es la configuración que se vuelve explotable si algún día hay cookies. El frontend es de mismo origen (ADR-008) y no necesita CORS. | Eliminar `CORSMiddleware`. Verificar que ningún test dependa de él (BE47 comprueba `Retry-After` y debe seguir en verde: es legible desde el mismo origen). | BE54: una petición con `Origin` ajeno no recibe `Access-Control-Allow-Origin` |
| SEC-6 | XSS → robo del token | `frontend/nginx.conf` no define ninguna cabecera de seguridad. Si algún día entrara un XSS, nada limita lo que el script inyectado puede cargar o enviar. | Agregar `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, una `Permissions-Policy` mínima y una **CSP en modo `Content-Security-Policy-Report-Only`** primero (ver abajo). | BE55 (parsea `nginx.conf`) |

**CSP.** Parte de `default-src 'self'`. Agrega lo que ya usa la app y lo que pide Google
Identity Services (según su guía de CSP, que debes verificar contra la versión vigente):
`script-src 'self' https://accounts.google.com/gsi/client`,
`frame-src https://accounts.google.com/gsi/`, `connect-src 'self' https://accounts.google.com/gsi/`,
`style-src 'self' 'unsafe-inline' https://accounts.google.com/gsi/style`,
`img-src 'self' data: blob:` más los hosts de teselas, `worker-src blob:` (MapLibre) y
`frame-ancestors 'none'`. Los hosts de teselas y del estilo del mapa salen de `OSM_STYLE` en
`EstablishmentMap.jsx`: léelo, no los supongas. Despliega en `Report-Only`, abre Login, Directorio,
una Ficha con mapa y el Dashboard en el navegador, y revisa que la consola no reporte violaciones.
Solo entonces cambia el encabezado a `Content-Security-Policy`. No agregues
`Cross-Origin-Opener-Policy` salvo `same-origin-allow-popups`: otro valor rompe el popup de Google.
**HSTS no va en este nginx**: escucha en `:80` y el TLS termina afuera. Anótalo en `07-operacion.md`
para quien administre el terminador TLS.

**Se mantiene como está (decidido, no lo cambies):** TTL de 180 minutos, sin refresh tokens, sin
MFA, sin captcha. Ninguno cierra una brecha de esta tabla y todos suman piezas que mantener.

---

## 4. S2 · Login con Google y alta automática

**Enmienda a lo ya aprobado.** `03` §8 y `04` §9.6 describen F6 con "sin auto-provisión", y
ADR-006 repite esa decisión. C24 la cambia: actualiza esos tres lugares y registra la decisión como
**ADR-015** (enmienda ADR-006 y ADR-009).

**Contrato.**
- `POST /api/auth/google` · pública · body `{credential}` · devuelve `Token`, con el mismo
  `_issue_token` que usan `/login` y `/password`. Esa función es el único punto por donde sale una
  sesión: no abras una segunda ruta.
- `GET /api/auth/config` · pública · `{google_client_id}`. El frontend no tiene variables de
  entorno (ADR-008), así que no uses `VITE_*`.

**Verificación, en este orden.** Todo fallo responde el mismo `401` de `_credentials_exception`,
sin revelar la causa, y nunca se escribe el token en un log.
1. Límite por IP, reutilizando `rate_guard` y `rate_hit` con un scope nuevo (`google-ip`).
2. Verificar con `google-auth` (`id_token.verify_oauth2_token`) dentro de `asyncio.to_thread`,
   porque es síncrono. Comprueba firma, `aud == GOOGLE_CLIENT_ID` y `exp`, con
   `clock_skew_in_seconds=10` (mismo motivo que D28: con el reloj de WSL2 un token recién emitido
   parece del futuro).
3. Comprobar tú, de forma explícita: `iss` en (`accounts.google.com`, `https://accounts.google.com`),
   `email_verified is True`, `hd` dentro de `ALLOWED_EMAIL_DOMAINS` **y** sufijo del correo
   coincidente, `sub` no vacío, y `iat` de no más de 5 minutos (acota la reutilización de un
   `id_token` robado sin guardar estado).
4. Resolver a la persona:
   - por (`google`, `subject`); si no, por correo normalizado;
   - `invited` → pasa a `active` y se vincula el proveedor; `active` sin vínculo → se vincula;
   - vinculada con otro `subject` → `401`; `disabled` → `401`;
   - **no existe:** con `GOOGLE_AUTO_PROVISION=true`, se crea con el pipeline de `users_service`
     (`actor_id="system:google"`, sin segunda ruta de creación), con `given_name` y `family_name`
     como nombre y apellido, y se audita (`user.autoprovision`). Con `false`, el mismo `401`.
5. Emitir con `_issue_token` y actualizar `last_login_at`.

**Entidad.** `is_slep_staff` admite `null` (sin asignar). Invariante: `null` implica `unit_id`,
`rbd` y `positions` vacíos; un usuario ya asignado no vuelve a `null`; el alta manual y el CSV
siguen exigiendo asignación. Actualiza los tests de `BE24` y agrega el filtro de API
`GET /api/users?assignment=unassigned` (la interfaz de ese filtro queda fuera de esta fase).

**Frontend (solo `Login.jsx`).** Carga el script de Google Identity Services y llama a
`google.accounts.id.initialize({client_id, callback, hd: "slepllanquihue.cl"})` seguido de
`renderButton`. Aquí `hd` es solo una pista de interfaz: **no protege nada**. La callback envía
`credential` a `/api/auth/google` y reutiliza `handleLoginSuccess` de `App.jsx`. No guarda nada
nuevo. El resto de la pantalla sigue las reglas de shadcn (C15).

**Tests (`T11`).** Cada punto, uno por uno:
- Un token de otro dominio, sin `hd`, con `email_verified=false`, de otra `aud`, vencido, con `iss`
  ajeno o con `iat` antiguo devuelve `401` y **no crea ningún documento**.
- La cuenta nueva es `viewer` en `datos`, sin acceso a `iam`, y ninguna claim del token cambia el rol.
- Dos logins simultáneos del mismo correo nuevo crean **una** cuenta (índice único de `email`).
- Un usuario `disabled` no entra, y volver a iniciar sesión con Google no lo reactiva.
- Un usuario existente (por ejemplo, el admin) entra por correo y **no** cambia su rol ni su pertenencia.
- Con `GOOGLE_AUTO_PROVISION=false`, un correo sin cuenta recibe el mismo `401` y no se crea nada.
- El cuerpo de la respuesta y los logs no contienen el `credential`.
- Exceder el límite por IP devuelve `429` con `Retry-After`.

---

## 5. Pendientes del usuario (no los decidas tú)

- **N18 · resuelta (2026-10-19): se acepta.** Cualquier cuenta del dominio obtiene `viewer` en
  `datos`. Condiciones para activar `GOOGLE_AUTO_PROVISION=true` en producción: SEC-1 a SEC-6
  aplicados y en verde, y el retiro de `licenses` (o, como mínimo, su redacción vigente con BE05,
  BE13, INT02 e INT04 en verde). La activación la hace el usuario, no el agente.
- **D-C · Cookie `HttpOnly` en lugar de `localStorage` (S3).** Es lo único que elimina el robo del
  token por XSS (`04` §1, brecha registrada). Costo: reescribir el embudo `_issue_token`, `App.jsx`,
  `Login.jsx` y los tests que tocan `localStorage` y `Authorization` (FE00, FE06, FE07, INT09,
  `setup.js`). Además exige **SameSite=Strict** (apto aquí: SPA y API de mismo origen) y que SEC-5
  ya esté aplicado. Sin ella, SEC-3 y SEC-6 acotan el daño pero no cierran la clase. **No la hagas
  sin aprobación expresa**, y si se aprueba, en su propia rama y tag (regla 4).
- **Retiro de `licenses` (N15).** ¿Cuándo? Recomendación: antes de activar C24 en producción,
  retirando el campo y **rotando esas credenciales**, porque hoy están en claro en Mongo.
- **Consola de Google Cloud (tarea del usuario, déjala como checklist en `07-operacion.md`):**
  orígenes de JavaScript autorizados `http://localhost:5173` y `https://datos.slepllanquihue.gob.cl`.
  No hacen falta URIs de redirección: la callback de Google Identity Services es de JavaScript.
  Para pruebas locales, la guía de Google Identity Services pide registrar además
  `http://localhost` (sin puerto); verifícalo contra la guía vigente si el botón no aparece.
  Navega siempre por `localhost`, no por `127.0.0.1`: son orígenes distintos.

---

## 6. Fuera de alcance (no lo agregues)

Un servicio o IdP nuevo, refresh tokens, MFA, captcha, WAF, Redis, flujo OAuth con authorization
code, nonce con estado, middleware propio de CSRF (con `Bearer` no hace falta), deshabilitar `/docs`
(no es alcanzable), cambiar el TTL, y cualquier historia de unidades, CSV, masivas, subrogancias o
interfaz de administración. La interconexión entre plataformas (F7) es solo diseño.

---

## 7. Verificación, despliegue y documentación

**Comandos (CLAUDE.md §2):** `cd backend && python -m pytest -v` y `cd frontend && npm test`.
`npm run lint` no se puede ejecutar (`eslint` no está instalado): regístralo, no lo des por pasado.

**Impacto en despliegue (regla 3):**
- `requirements.txt`: `google-auth` y el transporte HTTP que su verificación necesite. Confirma
  cuál exige tu versión y agrega solo eso. Rebuild de la imagen del backend.
- `frontend/nginx.conf` cambia: rebuild de la imagen del frontend.
- Variable nueva: `GOOGLE_AUTO_PROVISION`, en `.env.production.template` y en los dos compose
  (`test_BE14_every_env_var_declared…` lo exige). El compose de desarrollo pasa a leer
  `JWT_SECRET` y `ADMIN_PASSWORD` del `.env`, así que hay que avisar al usuario de que su `.env`
  debe tenerlos antes de levantar.
- `users` gana `sessions_revoked_at`: no necesita migración (ausente = sin corte).
- El límite por IP de `/api/auth/google` usa el mismo `client_ip` que el login: comprueba en el
  primer despliegue que el proxy del host reenvía `X-Forwarded-For` (`07` §7). Si no, el límite se
  comparte entre todos los usuarios.

**Documentación (DoD, regla 6):** `03` §8, `04` §9.6 y §1 (token y cookie), `04` §5 (CORS),
`02` (`is_slep_staff` nulo y `sessions_revoked_at`), `06` ADR-015, `07` (variable y checklist de
Google). Marca como cerradas las brechas de CORS y de D5, y registra como `🔸 D` nueva cualquier
brecha que encuentres. Si algo del código contradice lo que este prompt afirma, el código manda:
repórtalo como `🔸 BRECHA`.

---

## 8. Formato de tu respuesta

1. Resumen de lo que verificaste y de cualquier diferencia con este prompt (10 líneas como máximo).
2. S1 con la salida real de los tests antes y después. Detente y espera el visto bueno.
3. S2 con la misma evidencia, y el estado de `GOOGLE_AUTO_PROVISION` en cada entorno.
4. Lo que dejaste pendiente para el usuario (§5), sin decidirlo.
