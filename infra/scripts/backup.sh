#!/bin/bash
# ===========================================================
# backup.sh — резервное копирование PostgreSQL и Redis
#
# Использование:
#   ./backup.sh
#
# Cron (каждый день в 03:00):
#   0 3 * * * /opt/responscrm/infra/scripts/backup.sh >> /var/log/responscrm-backup.log 2>&1
#
# Переменные окружения (опционально):
#   BACKUP_ROOT  — корневая директория для бэкапов (по умолчанию /backups)
#   RETENTION_DAYS — сколько дней хранить (по умолчанию 7)
#   POSTGRES_CONTAINER — имя контейнера postgres (по умолчанию responscrm-postgres-1)
#   REDIS_CONTAINER    — имя контейнера redis    (по умолчанию responscrm-redis-1)
# ===========================================================

set -euo pipefail

# ----- Настройки -----
BACKUP_ROOT="${BACKUP_ROOT:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-responscrm-postgres-1}"
REDIS_CONTAINER="${REDIS_CONTAINER:-responscrm-redis-1}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"

# ----- Вспомогательные функции -----
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

die() {
    log "ERROR: $*" >&2
    exit 1
}

# ----- Создание директории -----
mkdir -p "${BACKUP_DIR}" || die "Не удалось создать директорию ${BACKUP_DIR}"
log "Backup directory: ${BACKUP_DIR}"

# ----- PostgreSQL -----
log "Starting PostgreSQL dump..."

docker exec "${POSTGRES_CONTAINER}" pg_dump \
    -U responscrm \
    --format=custom \
    --compress=9 \
    responscrm \
    > "${BACKUP_DIR}/postgres.dump" \
    || die "pg_dump завершился с ошибкой"

POSTGRES_SIZE="$(du -sh "${BACKUP_DIR}/postgres.dump" | cut -f1)"
log "PostgreSQL dump complete: ${BACKUP_DIR}/postgres.dump (${POSTGRES_SIZE})"

# ----- Redis -----
log "Starting Redis backup..."

# Инициируем BGSAVE и ждём завершения
docker exec "${REDIS_CONTAINER}" redis-cli BGSAVE > /dev/null
log "Waiting for Redis BGSAVE to complete..."

for i in $(seq 1 30); do
    STATUS="$(docker exec "${REDIS_CONTAINER}" redis-cli LASTSAVE)"
    sleep 1
    NEW_STATUS="$(docker exec "${REDIS_CONTAINER}" redis-cli LASTSAVE)"
    if [ "${STATUS}" != "${NEW_STATUS}" ]; then
        break
    fi
    if [ "${i}" -eq 30 ]; then
        log "WARNING: Redis BGSAVE timed out after 30s, copying current dump anyway"
    fi
done

docker cp "${REDIS_CONTAINER}:/data/dump.rdb" "${BACKUP_DIR}/redis.rdb" \
    || die "Не удалось скопировать Redis dump"

REDIS_SIZE="$(du -sh "${BACKUP_DIR}/redis.rdb" | cut -f1)"
log "Redis backup complete: ${BACKUP_DIR}/redis.rdb (${REDIS_SIZE})"

# ----- Удаление старых бэкапов -----
log "Removing backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_ROOT}" -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" -exec rm -rf {} + 2>/dev/null || true
log "Cleanup complete"

# ----- Итог -----
TOTAL_SIZE="$(du -sh "${BACKUP_DIR}" | cut -f1)"
log "Backup complete: ${BACKUP_DIR} (total: ${TOTAL_SIZE})"
