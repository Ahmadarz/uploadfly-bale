#!/bin/sh
# پشتیبان روزانه‌ی PostgreSQL؛ نسخه‌های قدیمی‌تر از ۱۴ روز پاک می‌شوند
set -u
while true; do
  file="/backups/uploadfly-$(date +%Y%m%d-%H%M).sql.gz"
  if pg_dump -h db -U uploadfly uploadfly | gzip > "$file.tmp"; then
    mv "$file.tmp" "$file"
    echo "backup ok: $file"
  else
    rm -f "$file.tmp"
    echo "backup FAILED" >&2
  fi
  find /backups -name 'uploadfly-*.sql.gz' -mtime +14 -delete
  sleep 86400
done
