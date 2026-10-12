#!/bin/sh
# پشتیبان روزانه‌ی دیتابیس روی مک (تا وقتی سرور نداریم). با launchd ساعت ۴ صبح اجرا می‌شود؛
# اگر مک خواب باشد، بعد از بیدار شدن اجرا می‌شود. ۳۰ روز آخر نگه داشته می‌شود.
# نکته: توکن‌های داخل دیتابیس رمز شده‌اند؛ بدون ENCRYPTION_KEY (در .env) پشتیبان به درد نمی‌خورد،
# پس آن کلید را جدا (مثلاً در یک مدیر رمز عبور) نگه دارید. .env هرگز این‌جا کپی نمی‌شود.
set -eu
SRC="$HOME/Projects/UploadFly/bot/uploadfly.db"
DEST="$HOME/UploadFly-backups"
mkdir -p "$DEST"
chmod 700 "$DEST"
STAMP=$(date +%Y-%m-%d_%H%M%S)
OUT="$DEST/uploadfly-$STAMP.db"
# .backup نسخه‌ی سالم می‌گیرد حتی وقتی ربات در حال نوشتن است (کپی ساده‌ی فایل ممکن است نیمه‌کاره باشد)
/usr/bin/sqlite3 "$SRC" ".timeout 10000" ".backup '$OUT'"
if [ "$(/usr/bin/sqlite3 "$OUT" 'PRAGMA integrity_check;')" != "ok" ]; then
  echo "$(date '+%F %T') BACKUP BROKEN: $OUT" >&2
  rm -f "$OUT"
  exit 1
fi
gzip -9 "$OUT"
chmod 600 "$OUT.gz"
find "$DEST" -name 'uploadfly-*.db.gz' -mtime +30 -delete
echo "$(date '+%F %T') backup ok: $(basename "$OUT").gz ($(du -h "$OUT.gz" | cut -f1))"
