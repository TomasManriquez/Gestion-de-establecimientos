#!/bin/bash
# =============================================================================
# restore-mongo.sh — Restaurar un backup de MongoDB
# Ejecutar desde el HOST con: bash scripts/restore-mongo.sh
# Requiere que el stack de producción esté corriendo.
# =============================================================================

set -euo pipefail

BACKUP_VOLUME="gestion-de-establecimientos_mongo_backups"
DB="${DATABASE_NAME:-slep_llanquihue}"

echo "========================================"
echo "  Restauración de MongoDB — SLEP"
echo "========================================"
echo ""

# Listar backups disponibles desde el volumen
echo "Backups disponibles:"
BACKUPS=$(docker run --rm \
    -v "${BACKUP_VOLUME}:/backups:ro" \
    alpine \
    ls /backups/slep_backup_*.gz 2>/dev/null | sort -r || true)

if [ -z "${BACKUPS}" ]; then
    echo "❌ No se encontraron backups en el volumen ${BACKUP_VOLUME}"
    exit 1
fi

# Numerar y mostrar los backups
i=1
declare -A BACKUP_MAP
while IFS= read -r backup; do
    basename=$(basename "${backup}")
    echo "  ${i}) ${basename}"
    BACKUP_MAP[$i]="${basename}"
    ((i++))
done <<< "${BACKUPS}"

echo ""
read -rp "Selecciona el número del backup a restaurar [1]: " SELECTION
SELECTION="${SELECTION:-1}"

SELECTED_FILE="${BACKUP_MAP[$SELECTION]:-}"
if [ -z "${SELECTED_FILE}" ]; then
    echo "❌ Selección inválida."
    exit 1
fi

echo ""
echo "⚠️  ADVERTENCIA: Esto sobreescribirá la base de datos '${DB}' actual."
read -rp "¿Estás seguro? Escribe 'SI' para continuar: " CONFIRM
if [ "${CONFIRM}" != "SI" ]; then
    echo "Operación cancelada."
    exit 0
fi

echo ""
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando restauración desde: ${SELECTED_FILE}"

# Cargar variables del .env si existe
if [ -f ".env" ]; then
    # shellcheck disable=SC1091
    set -a && source .env && set +a
fi

MONGO_URI="mongodb://${MONGO_ROOT_USERNAME}:${MONGO_ROOT_PASSWORD}@localhost:27017/${DB}?authSource=admin"

# Restaurar usando el contenedor de MongoDB
docker run --rm \
    --network "$(docker inspect slep_mongodb --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}')" \
    -v "${BACKUP_VOLUME}:/backups:ro" \
    mongo:7.0 \
    mongorestore \
        --uri="mongodb://${MONGO_ROOT_USERNAME}:${MONGO_ROOT_PASSWORD}@slep_mongodb:27017/?authSource=admin" \
        --db="${DB}" \
        --gzip \
        --archive="/backups/${SELECTED_FILE}" \
        --drop

echo ""
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Restauración completada exitosamente."
echo "  Base de datos '${DB}' restaurada desde '${SELECTED_FILE}'"
