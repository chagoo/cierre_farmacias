#!/bin/bash
set -euo pipefail

# Creates a backup of the configured SQL Server database.
# Requires DB_SERVER, DB_NAME, DB_USER and DB_PASSWORD environment variables.

BACKUP_DIR=${BACKUP_DIR:-backups}
mkdir -p "${BACKUP_DIR}"
DATE=$(date +%F_%H-%M-%S)
FILE="${BACKUP_DIR}/db_${DATE}.bak"

sqlcmd -S "$DB_SERVER" -U "$DB_USER" -P "$DB_PASSWORD" -Q "BACKUP DATABASE [$DB_NAME] TO DISK='${FILE}' WITH INIT;"

echo "Backup stored at ${FILE}" 
