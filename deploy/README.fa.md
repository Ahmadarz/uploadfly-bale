# راه‌اندازی UploadFly روی سرور

این راهنما برای سرور **Ubuntu 24.04** است (VPS ارزان، Oracle رایگان، یا سرور اختصاصی). همه‌چیز با Docker اجرا می‌شود:
ربات + Mini App، دیتابیس PostgreSQL، HTTPS خودکار (Caddy) و پشتیبان روزانه.

> موقع راه‌اندازی، Claude قدم‌به‌قدم کنارت است. این فایل برای مرور و مراجعه‌ی بعدی است.

## ۱. نصب Docker روی سرور
```
ssh root@IP_SERVER
curl -fsSL https://get.docker.com | sh
```

## ۲. گرفتن کد از گیت‌هاب (ریپوی خصوصی)
روی سرور یک کلید فقط‌خواندنی بساز و در گیت‌هاب به‌عنوان Deploy key اضافه کن:
```
ssh-keygen -t ed25519 -N "" -f ~/.ssh/uploadfly
cat ~/.ssh/uploadfly.pub
```
متن خروجی را در GitHub → ریپوی uploadfly → Settings → Deploy keys → Add (بدون تیک Write) بگذار. بعد:
```
GIT_SSH_COMMAND="ssh -i ~/.ssh/uploadfly" git clone git@github.com:vmirsvni/uploadfly.git
cd uploadfly
```

## ۲٫۵. دامنه (DNS)
در پنل DNS دامنه سه رکورد **A** بساز که هر سه به **IP سرور** اشاره کنند (اگر گزینه‌ی CDN یا ابر نارنجی دارد، خاموش بماند):
| نام (Host) | نوع | مقدار |
|---|---|---|
| `@` (خود دامنه، برای سایت) | A | IP سرور |
| `www` | A | IP سرور |
| `app` (برای ربات و Mini App) | A | IP سرور |

چند دقیقه تا چند ساعت طول می‌کشد تا همه‌جا اعمال شود. گواهی HTTPS خودکار و رایگان گرفته می‌شود.

## ۳. فایل تنظیمات `.env`
```
cp bot/.env.example .env
nano .env
```
- `BOT_TOKEN` و `ENCRYPTION_KEY` و `ADMIN_IDS`: **دقیقاً همان مقدارهای مک**. اگر `ENCRYPTION_KEY` فرق کند، توکن فروشگاه‌ها باز نمی‌شود.
- `POSTGRES_PASSWORD`: یک رمز طولانی؛ بساز با `openssl rand -hex 24`
- `DOMAIN`: آدرس ربات و Mini App، مثلاً `app.uploadfly.com` (بدون دامنه: IP سرور با خط تیره + `.sslip.io`، مثلاً `5-75-1-2.sslip.io`)
- `SITE_DOMAIN`: دامنه‌ی سایت معرفی، مثلاً `uploadfly.com` (همان دامنه‌ی اصلی، بدون www)
- `SUPPORT_USERNAME` و `SUPPORT_EMAIL`: حساب تلگرام و ایمیل پشتیبانی (در ربات، Mini App و پایین سایت نمایش داده می‌شوند)
- `DATABASE_URL` و `WEBAPP_URL` لازم نیست؛ Docker خودش تنظیم می‌کند.

## ۴. خاموش کردن ربات روی مک (مهم)
دو نسخه‌ی هم‌زمان پیام‌ها را از هم می‌دزدند. روی مک:
```
launchctl bootout gui/$(id -u)/com.uploadfly.bot
```

## ۵. انتقال داده‌ها از مک
روی مک (فایل دیتابیس را به سرور بفرست):
```
scp ~/Projects/UploadFly/bot/uploadfly.db root@IP_SERVER:~/uploadfly/uploadfly.db
```
روی سرور:
```
docker compose up -d db
docker compose run --rm --no-deps --user root -v "$PWD/uploadfly.db:/data/source.db" --entrypoint sh bot -c \
  'python -m scripts.migrate_sqlite_to_postgres --source sqlite+aiosqlite:////data/source.db --target "$DATABASE_URL"'
```
باید برای همه‌ی جدول‌ها ✅ ببینی. اسکریپت روی دیتابیسی که داده دارد چیزی نمی‌نویسد.

## ۶. روشن کردن همه‌چیز
```
docker compose up -d --build
docker compose logs -f bot
```
باید `UploadFly is running as @Uploadfly_Bot` را ببینی. با `Ctrl+C` از لاگ بیرون بیا (ربات روشن می‌ماند).

## ۷. بعد از راه‌اندازی
- در BotFather، **Main Mini App** را با آدرس `https://DOMAIN` ثبت کن (لینک مستقیم ویترین و دکمه‌ی Open App).
- دکمه‌ی منوی ربات خودکار روی آدرس جدید تنظیم می‌شود.
- سایت را باز کن: `https://SITE_DOMAIN` (هر بار `docker compose up -d --build` سایت با آدرس واقعی دوباره ساخته می‌شود).

## ۸. ثبت سایت در گوگل (Google Search Console)
1. به search.google.com/search-console برو، «Add property» ← نوع **URL prefix** ← `https://SITE_DOMAIN`.
2. روش تأیید **HTML tag** را انتخاب کن و فقط مقدار `content="…"` را کپی کن.
3. در `.env` بگذار: `GOOGLE_SITE_VERIFICATION=همان‌مقدار` و بزن: `docker compose up -d site`
4. در Search Console «Verify» را بزن، بعد در بخش **Sitemaps** این را ثبت کن: `sitemap.xml`
5. چند روز تا چند هفته طول می‌کشد تا صفحه‌ها در گوگل بیایند. کاربرانی که از سایت می‌آیند در `/stats` زیر «🔗 site_…» شمرده می‌شوند.

## کارهای روزمره
| کار | دستور |
|---|---|
| به‌روزرسانی بعد از تغییر کد | `git pull && docker compose up -d --build` |
| دیدن لاگ | `docker compose logs -f bot` |
| وضعیت سرویس‌ها | `docker compose ps` |
| ری‌استارت ربات | `docker compose restart bot` |
| پشتیبان‌ها | پوشه‌ی `backups/` (روزانه، ۱۴ روز آخر) |

### برگرداندن پشتیبان
```
gunzip -c backups/FILE.sql.gz | docker compose exec -T db psql -U uploadfly -d uploadfly
```
(روی دیتابیس خالی؛ قبلش با Claude هماهنگ کن.)
