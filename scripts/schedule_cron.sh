#!/bin/bash
set -euo pipefail

# Adds cron jobs for database backup and log rotation
CRON_FILE=$(mktemp)
crontab -l > "$CRON_FILE" 2>/dev/null || true

grep -q backup_db.sh "$CRON_FILE" || echo "0 2 * * * /app/scripts/backup_db.sh >> /var/log/cierre_farmacias/backup.log 2>&1" >> "$CRON_FILE"
grep -q logrotate "$CRON_FILE" || echo "0 3 * * * /usr/sbin/logrotate /app/scripts/logrotate.conf" >> "$CRON_FILE"

crontab "$CRON_FILE"
rm "$CRON_FILE"

echo "Cron jobs installed" 
