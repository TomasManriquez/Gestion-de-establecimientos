# CLAUDE.md — Sistema de Gestión de Establecimientos (SLEP Llanquihue)

Reglas de ingeniería vinculantes para este repositorio. Léelas antes de tocar código.

## 1. Documentación primero

Antes de planificar cualquier feature o fix, lee `Documentacion/00-README.md` (glosario e
índice) y sigue la tabla "quiero hacer X → lee Y" hasta el documento relevante:

| Documento | Cuándo leerlo |
|---|---|
| `01-arquitectura.md` | Siempre que el cambio toque más de un archivo |
| `02-modelo-datos.md` | Cambios de esquema, colecciones, campos sensibles |
| `03-api-contract.md` | Nuevo endpoint o cambio de contrato |
| `04-seguridad-y-acceso.md` | Auth, roles, redacción de campos |
| `05-guia-de-extension.md` | Agregar módulo/campo nuevo — recetas y **Definition of Done** (§6) |
| `06-decisiones-adr.md` | Antes de proponer una alternativa arquitectónica ya evaluada |
| `07-operacion.md` | Levantar entorno, seed, tests, despliegue |

Estos documentos están verificados línea por línea contra el código (`archivo:línea`). Si el
código y el documento discrepan, el código gana pero la discrepancia se reporta como
`🔸 BRECHA` nueva — no se asume silenciosamente.

El formato y la estructura de esta documentación son el estándar del proyecto — ver
`.agents/skills/project-documentation-standard.md`. Cualquier feature que agregue una
colección, un endpoint o una decisión de arquitectura debe actualizar el `.md` correspondiente
en el mismo cambio, no como tarea separada.

## 2. Verificación basada en evidencia observable

No declares una tarea o fase "completada" sin:

- Presentar el output real del comando ejecutado (tests, build, lint) — no un resumen.
- Un código de salida 0 sin stdout visible **no** es evidencia de que funcionó.
- Si no puedes ejecutar la prueba en tu entorno, pide explícitamente al usuario el comando
  exacto a correr y espera su resultado antes de dar el paso por cerrado.

Comandos de verificación de este repo:

```bash
cd backend && python -m pytest -v
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build
```

## 3. Impacto en el entorno de despliegue

Este repo tiene `Dockerfile`, `Dockerfile.prod`, `docker-compose.yml` y `docker-compose.prod.yml`.
Al planificar cualquier cambio, evalúa explícitamente — no esperes a que el usuario lo note:

- ¿Nueva dependencia en `requirements.txt` o `package.json`? → rebuild de imagen.
- ¿Nueva variable de entorno? → actualizar `.env.production.template` y los `docker-compose*.yml`.
- ¿Cambio de puerto o volumen? → sincronizar ambos compose files.

## 4. Rollback en componentes críticos

Antes de refactorizar un punto único de falla (`backend/app` auth/middlewares, `ProtectedRoute`
del frontend, `database_service.py`):

- Define el punto de restauración de git y trabaja en rama aislada.
- Verifica que los tests del flujo de autenticación (BE03/BE05/INT02) pasen **antes y después**
  del cambio.

## 5. Brechas conocidas — no las repliques

Ver `Documentacion/05-guia-de-extension.md` §5 para la lista completa y su estado actual.

**Resueltas — son el patrón a seguir, no lo reviertas:**

- **D1**: el seeding ya persiste `location` (`seed_service.py`).
- **D2**: `JWT_SECRET`/`ADMIN_PASSWORD` no tienen default y la app no arranca sin ellos
  (`config._required`). Todo secreto nuevo se declara igual: obligatorio, sin default silencioso.
- **D3/D4**: `viewer` solo lee y el `PUT` de establecimiento respeta `include_sensitive`. Todo
  endpoint declara `require_access`; un test recorre las rutas. No lo omitas en endpoints nuevos
  ni devuelvas secretos sin redactar.
- **D5**: los filtros de texto escapan con `re.escape`. Todo filtro nuevo por texto hace lo mismo.
- **D6**: el año fijo se retiró (ADR-019). No agregues pipelines con el año hardcodeado.

**Abiertas — cuidado al tocar código cercano:**

- **D10**: no hay versionado de API (`/api/`, sin `/v1`). Cualquier cambio de contrato es
  potencialmente breaking — coordinar con frontend. Los routers nuevos de ADR-021 van bajo `/api/v1/`.
- **D36**: los cambios a ficha, contrapartes y métricas no se auditan. No asumas que hay rastro.
- **D37/D20**: `npm run lint` no corre (falta `eslint`). Nunca declares que el lint pasó.

**Acceso por recurso (ADR-021; fases 1 (concesiones) y 2 (bóveda, backend) ✅; portal y pestaña de la ficha 🧭):** cada recurso del portal es `org` (toda cuenta de `datos`)
o `restricted` (nivel 2 del catastro y la bóveda). El rol de plataforma no abre recursos `restricted`;
solo una concesión explícita, por persona (la de unidad llega después). Quien registra un recurso
`restricted` recibe `ver` en el acto. `vault.reveal` se audita antes de entregar la clave y, si el
registro falla, no se entrega. Toda cuenta del dominio entra como `datos/viewer` sin unidad
(ADR-015), así que ni el rol, ni el dominio, ni `is_slep_staff` justifican dar acceso a un dato
restringido. Las contraseñas de la bóveda nunca van en respuestas de lista, `PUT`, `audit_log`
ni en el snapshot de la PWA.

## 6. Definition of Done

Antes de cerrar una feature, repasa `Documentacion/05-guia-de-extension.md` §6 completo. Resumen:

- [ ] Tests unitarios + integración corridos con salida real mostrada (regla 2).
- [ ] Impacto de despliegue evaluado (regla 3).
- [ ] Si se tocó un punto único de falla, rollback definido y tests de auth verdes antes/después.
- [ ] Ninguna brecha de la sección 5 replicada.
- [ ] Documentación (`Documentacion/*.md`) actualizada si el cambio afecta modelo de datos,
      contrato de API, seguridad o arquitectura.

## 7. Convenciones de proyecto

- Backend: FastAPI + Motor/MongoDB, capas entity/service/controller (`01-arquitectura.md`).
- Frontend: React + Vite + React Router + shadcn/ui.
- Escala actual: 78 establecimientos, 5 comunas. Decisiones que son correctas a esta escala
  (paginación simple, sin caché en agregaciones) dejan de serlo un orden de magnitud más
  arriba — no optimices prematuramente, pero no ignores el límite si el cambio lo acerca.
