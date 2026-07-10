#!/bin/bash
# =============================================================================
# backup-mongo.sh — Backup diario de MongoDB con retención automática
# Ejecutado por el servicio "backup" dentro de Docker.
# =============================================================================

set -euo pipefail

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/backups"
BACKUP_FILE="${BACKUP_DIR}/slep_backup_${TIMESTAMP}.gz"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
DB="${DATABASE_NAME:-slep_llanquihue}"
MONGO_URI="mongodb://${MONGO_ROOT_USERNAME}:${MONGO_ROOT_PASSWORD}@mongodb:27017/${DB}?authSource=admin"

echo "========================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando backup de MongoDB"
echo "  Base de datos : ${DB}"
echo "  Archivo       : ${BACKUP_FILE}"
echo "  Retención     : ${RETENTION_DAYS} días"
echo "========================================"

# Crear directorio de backups si no existe
mkdir -p "${BACKUP_DIR}"

# Ejecutar mongodump y comprimir con gzip
if mongodump \
    --uri="${MONGO_URI}" \
    --db="${DB}" \
    --gzip \
    --archive="${BACKUP_FILE}"; then

    SIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Backup completado exitosamente"
    echo "  Tamaño del archivo: ${SIZE}"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ ERROR: El backup falló"
    exit 1
fi

# Eliminar backups más antiguos que RETENTION_DAYS
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Limpiando backups con más de ${RETENTION_DAYS} días..."
DELETED=$(find "${BACKUP_DIR}" -name "slep_backup_*.gz" -mtime "+${RETENTION_DAYS}" -print)
if [ -n "${DELETED}" ]; then
    find "${BACKUP_DIR}" -name "slep_backup_*.gz" -mtime "+${RETENTION_DAYS}" -delete
    echo "  Eliminados:"
    echo "${DELETED}" | sed 's/^/    - /'
else
    echo "  No hay backups antiguos para eliminar."
fi

# Listar backups disponibles
echo ""
echo "Backups disponibles actualmente:"
ls -lh "${BACKUP_DIR}"/slep_backup_*.gz 2>/dev/null || echo "  (ninguno)"
echo "========================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Proceso de backup finalizado."
