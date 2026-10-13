# راه‌اندازی UploadFly (نسخه‌ی بله) روی سرور

این راهنما برای یک سرور مجازی **Ubuntu 24.04** است. همه‌چیز با Docker اجرا می‌شود:
بازو + Mini App، دیتابیس PostgreSQL، HTTPS خودکار (Caddy)، سایت معرفی و پشتیبان روزانه.

> موقع راه‌اندازی، Claude قدم‌به‌قدم کنارت است. این فایل برای مرور و مراجعه‌ی بعدی است.
> بخش‌هایی که با «⚠️ بررسی‌نشده» علامت خورده‌اند هنوز روی سرور واقعی امتحان نشده‌اند.

> **سروری که برنامه‌های دیگری هم رویش هست و وب‌سرور خودش را دارد** (مثل سرور فروشگاه‌ساز): به‌جای این راهنما،
> بخش آخر همین فایل («نصب روی سرور مشترک») را ببین.

## ۰. چه چیزهایی باید بخری
| چیز | پیشنهاد | چرا |
|---|---|---|
| سرور مجازی | **داخل ایران**، ۲ هسته، ۲ گیگ رم، ۳۰ گیگ دیسک | کاربرهای بله در ایران‌اند؛ Mini App باید بدون فیلترشکن و حتی وقتی اینترنت بین‌الملل کند است باز شود |
| دامنه | یک دامنه (مثلاً `.ir`) | بله Mini App را فقط با آدرس HTTPS باز می‌کند؛ سایت معرفی هم برای گوگل لازم است |

## ۱. نصب Docker روی سرور
```
ssh root@IP_SERVER
curl -fsSL https://get.docker.com | sh
```
⚠️ بررسی‌نشده: از سرور ایران، سایت Docker و Docker Hub معمولاً بسته‌اند (خطای 403). در آن صورت:
- Docker را از مخزن خود اوبونتو نصب کن: `apt update && apt install -y docker.io docker-compose-v2`
- برای دانلود ایمیج‌ها یک «آینه» (mirror) داخل ایران لازم است. آدرس آینه را از شرکت سرور بپرس (بیشترشان یکی دارند) و این‌طور تنظیم کن:
```
nano /etc/docker/daemon.json
```
```
{ "registry-mirrors": ["https://آدرس-آینه"] }
```
```
systemctl restart docker
```

## ۲. گرفتن کد از گیت‌هاب (مخزن خصوصی)
روی سرور یک کلید فقط‌خواندنی بساز و در گیت‌هاب به‌عنوان Deploy key اضافه کن:
```
ssh-keygen -t ed25519 -N "" -f ~/.ssh/uploadfly
cat ~/.ssh/uploadfly.pub
```
متن خروجی را در GitHub → مخزن `uploadfly-bale` → Settings → Deploy keys → Add (بدون تیک Write) بگذار. بعد:
```
GIT_SSH_COMMAND="ssh -i ~/.ssh/uploadfly" git clone git@github.com:Ahmadarz/uploadfly-bale.git uploadfly
cd uploadfly
git config core.sshCommand "ssh -i ~/.ssh/uploadfly"
```

## ۳. دامنه (DNS)
در پنل DNS دامنه سه رکورد **A** بساز که هر سه به **IP سرور** اشاره کنند (اگر گزینه‌ی CDN یا «ابر» دارد، خاموش بماند):
| نام (Host) | نوع | مقدار |
|---|---|---|
| `@` (خود دامنه، برای سایت) | A | IP سرور |
| `www` | A | IP سرور |
| `app` (برای بازو و Mini App) | A | IP سرور |

چند دقیقه تا چند ساعت طول می‌کشد تا همه‌جا اعمال شود. گواهی HTTPS خودکار و رایگان گرفته می‌شود.

## ۴. فایل تنظیمات `.env`
```
cp bot/.env.example .env
nano .env
```
- `BOT_TOKEN`: توکن بازوی اصلی از @botfather بله.
- `ENCRYPTION_KEY`: کلید رمزنگاری توکن فروشنده‌ها. **یک بار بساز و هرگز عوضش نکن** (اگر عوض شود، هیچ فروشگاهی روشن نمی‌شود). یک نسخه‌اش را جای امن نگه دار.
- `ADMIN_IDS`: شناسه‌ی عددی حساب بله‌ی خودت (مدیر). در بازو، Mini App ← پروفایل ← پشتیبانی شناسه‌ات را نشان می‌دهد.
- `POSTGRES_PASSWORD`: یک رمز طولانی؛ بساز با `openssl rand -hex 24`
- `DOMAIN`: آدرس بازو و Mini App، مثلاً `app.example.ir`
- `SITE_DOMAIN`: دامنه‌ی سایت معرفی، مثلاً `example.ir` (بدون www)
- `MAIN_BOT`: نام کاربری بازوی اصلی بدون @ (برای دکمه‌های سایت)
- `SUPPORT_USERNAME` و `SUPPORT_EMAIL`: حساب بله و ایمیل پشتیبانی (در بازو، Mini App و پایین سایت نمایش داده می‌شوند)
- `REFUNDS`: خالی بماند تا وقتی بازپرداخت با کیف پول واقعی آزمایش شود.
- `DATABASE_URL` و `WEBAPP_URL` لازم نیست؛ Docker خودش تنظیم می‌کند.

## ۵. خاموش کردن نسخه‌ی روی کامپیوتر خودت (مهم)
دو نسخه‌ی هم‌زمان با یک توکن، پیام‌ها را از هم می‌دزدند. قبل از روشن کردن سرور، پنجره‌ی بازو را روی کامپیوترت ببند.

داده‌های کامپیوتر خودت آزمایشی‌اند؛ سرور با دیتابیس خالی شروع می‌کند. (اگر روزی لازم شد داده‌ها منتقل شوند:
`bot/scripts/migrate_sqlite_to_postgres.py`، با همان `ENCRYPTION_KEY`.)

## ۶. روشن کردن همه‌چیز
```
docker compose up -d --build
docker compose logs -f bot
```
باید `UploadFly is running as @نام‌بازو` را ببینی. با `Ctrl+C` از لاگ بیرون بیا (بازو روشن می‌ماند).

## ۷. بعد از راه‌اندازی
- در بازو `/start` بزن: دکمه‌ی «باز کردن UploadFly (مینی‌اپ)» باید Mini App را باز کند.
- در @botfather بله برای بازوی اصلی **«مینی‌اپ اصلی»** را با آدرس `https://DOMAIN` فعال کن (طبق مستندات بله: لینک مستقیم `ble.ir/نام‌بازو?startapp`، دکمه در فهرست گفتگوها و در صفحه‌ی بازو). همان‌جا می‌توانی **دکمه‌ی منوی بازو** را هم روی همین آدرس بگذاری.
- اسم، عکس و توضیح بازوی اصلی را در @botfather بگذار (بله این‌ها را از طریق برنامه نمی‌پذیرد). عکس: `website/assets/icon-512.png`.
- سایت را باز کن: `https://SITE_DOMAIN` (هر بار `docker compose up -d --build` سایت با آدرس واقعی دوباره ساخته می‌شود).
- یک خرید واقعی با یک حساب دیگر انجام بده و ببین پول به کیف پول فروشنده رسیده است.

## ۸. ثبت سایت در گوگل (Google Search Console)
1. به search.google.com/search-console برو، «Add property» ← نوع **URL prefix** ← `https://SITE_DOMAIN`.
2. روش تأیید **HTML tag** را انتخاب کن و فقط مقدار `content="…"` را کپی کن.
3. در `.env` بگذار: `GOOGLE_SITE_VERIFICATION=همان‌مقدار` و بزن: `docker compose up -d site`
4. در Search Console «Verify» را بزن، بعد در بخش **Sitemaps** این را ثبت کن: `sitemap.xml`
5. چند روز تا چند هفته طول می‌کشد تا صفحه‌ها در گوگل بیایند. کاربرانی که از سایت می‌آیند در `/stats` زیر «site_…» شمرده می‌شوند.

## کارهای روزمره
| کار | دستور |
|---|---|
| به‌روزرسانی بعد از تغییر کد | `git pull && docker compose up -d --build` |
| دیدن لاگ | `docker compose logs -f bot` |
| وضعیت سرویس‌ها | `docker compose ps` |
| ری‌استارت بازو | `docker compose restart bot` |
| پشتیبان‌ها | پوشه‌ی `backups/` (روزانه، ۱۴ روز آخر) |

پشتیبان‌ها روی همان سرورند؛ هر چند وقت یک بار یکی را روی کامپیوتر خودت هم کپی کن. دیتابیس بدون `ENCRYPTION_KEY` به درد نمی‌خورد، پس `.env` را هم جدا نگه دار.

### برگرداندن پشتیبان
```
gunzip -c backups/FILE.sql.gz | docker compose exec -T db psql -U uploadfly -d uploadfly
```
(روی دیتابیس خالی؛ قبلش با Claude هماهنگ کن.)

## نصب روی سرور مشترک (سروری که Caddy خودش و برنامه‌های دیگری دارد)
روی چنین سروری پورت‌های ۸۰ و ۴۴۳ دست وب‌سرور خود سرور است، پس UploadFly وب‌سرور جدا بالا نمی‌آورد و کاملاً جدا می‌ماند:
پوشه‌ی خودش (`/srv/uploadfly-bale`)، پروژه‌ی Docker خودش (`uploadfly-bale`)، دیتابیس خودش، و هیچ پورتی رو به بیرون.

1. کد را در `/srv/uploadfly-bale` بگذار و کنار آن `.env` بساز (همان مقدارهای بخش ۴؛ به‌علاوه‌ی `APP_PORT=18700` و
   `WEBAPP_URL=https://app.دامنه` وقتی دامنه آماده شد).
2. روشن کردن:
   ```
   cd /srv/uploadfly-bale
   sudo docker compose -f docker-compose.shared.yml up -d --build
   sudo docker compose -f docker-compose.shared.yml logs -f bot
   ```
3. ساخت سایت معرفی (بعد از گذاشتن `SITE_DOMAIN` در `.env`):
   ```
   sudo docker compose -f docker-compose.shared.yml --profile site run --rm site
   ```
4. وصل کردن دامنه به وب‌سرور خود سرور: فایل `deploy/shared-host/uploadfly.caddy.example` را با دامنه‌ی واقعی در
   `/etc/caddy/uploadfly-bale.caddy` بگذار و **فقط یک خط** به آخر `Caddyfile` اصلی اضافه کن:
   `import /etc/caddy/uploadfly-bale.caddy`
   قبلش از Caddyfile پشتیبان بگیر، بعد `caddy validate --config /etc/caddy/Caddyfile` و اگر درست بود `systemctl reload caddy`.
5. به‌روزرسانی بعد از تغییر کد: کد تازه را در همان پوشه بگذار و دستور قدم ۲ را دوباره بزن.

چیزی که با بقیه‌ی برنامه‌های سرور مشترک است فقط همان یک خط `import` در Caddyfile است؛ اگر روزی Caddyfile از نو
نوشته شد و آن خط افتاد، فقط UploadFly از دسترس خارج می‌شود (بقیه‌ی سایت‌ها نه) و با برگرداندن همان خط درست می‌شود.
