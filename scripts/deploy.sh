#!/bin/bash
# =============================================================================
# deploy.sh — Script de despliegue para producción
# Ejecutar desde el servidor Ubuntu con:
#   bash scripts/deploy.sh
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.prod.yml"
ENV_FILE="${PROJECT_DIR}/.env"

echo "========================================"
echo "  SLEP Llanquihue — Deploy a Producción"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

# ─── Validaciones previas ────────────────────────────────────────────────────
echo "[1/6] Verificando requisitos..."

if [ ! -f "${ENV_FILE}" ]; then
    echo "❌ ERROR: No se encontró el archivo .env en ${PROJECT_DIR}"
    echo "   Copia .env.production.template a .env y rellena los valores."
    exit 1
fi

if ! docker info &>/dev/null; then
    echo "❌ ERROR: Docker no está corriendo."
    exit 1
fi

# Verificar que las variables críticas están definidas
# shellcheck disable=SC1091
set -a && source "${ENV_FILE}" && set +a

for VAR in MONGO_ROOT_USERNAME MONGO_ROOT_PASSWORD JWT_SECRET ADMIN_PASSWORD DATABASE_NAME; do
    if [ -z "${!VAR:-}" ]; then
        echo "❌ ERROR: Variable ${VAR} no está definida en .env"
        exit 1
    fi
done

echo "  ✅ Requisitos verificados."

# ─── Backup preventivo antes de actualizar ───────────────────────────────────
echo ""
echo "[2/6] Ejecutando backup preventivo antes del deploy..."
if docker compose -f "${COMPOSE_FILE}" ps backup 2>/dev/null | grep -q "running"; then
    docker compose -f "${COMPOSE_FILE}" exec backup sh /backup-mongo.sh || echo "  ⚠️  Backup preventivo falló (puede ser el primer deploy)."
else
    echo "  ℹ️  Servicio de backup no está corriendo (posiblemente primer deploy). Omitiendo."
fi

# ─── Pull + Build ─────────────────────────────────────────────────────────────
echo ""
echo "[3/6] Actualizando código desde el repositorio..."
cd "${PROJECT_DIR}"
git pull --ff-only

echo ""
echo "[4/6] Construyendo imágenes de producción..."
docker compose -f "${COMPOSE_FILE}" build --no-cache

# ─── Despliegue con reinicio ordenado ────────────────────────────────────────
echo ""
echo "[5/6] Desplegando servicios..."
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans

# ─── Verificación post-deploy ─────────────────────────────────────────────────
echo ""
echo "[6/6] Verificando estado de los servicios..."
sleep 10

FAILED=0

check_service() {
    local name=$1
    local container=$2
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' "${container}" 2>/dev/null || echo "no-healthcheck")
    if [ "${STATUS}" = "healthy" ] || [ "${STATUS}" = "no-healthcheck" ]; then
        echo "  ✅ ${name} — ${STATUS}"
    else
        echo "  ❌ ${name} — ${STATUS}"
        FAILED=1
    fi
}

check_service "MongoDB"  "slep_mongodb"
check_service "Backend"  "slep_backend"
check_service "Frontend" "slep_frontend"
check_service "Backup"   "slep_backup"

echo ""
if [ "${FAILED}" -eq 0 ]; then
    echo "========================================"
    echo "  ✅ Deploy completado exitosamente"
    echo "  La aplicación está corriendo en http://localhost"
    echo "========================================"
else
    echo "========================================"
    echo "  ⚠️  Deploy completado con advertencias."
    echo "  Revisa los logs: docker compose -f docker-compose.prod.yml logs"
    echo "========================================"
    exit 1
fi
