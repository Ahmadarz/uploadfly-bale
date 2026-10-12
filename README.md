# UploadFly

ربات تلگرام برای صفحه‌ی سازنده (اشتراک، پست قفل‌دار، دونیت، پیام پولی، فروش فایل با استارز) + Mini App + سایت معرفی.

## پوشه‌ها
| پوشه | چیست |
|---|---|
| `bot/` | ربات تلگرام و Mini App (کد `app/`، صفحه‌ها `webapp/`، تست‌ها `tests/`، اسکریپت‌ها `scripts/`، `Dockerfile`، `design.md`). روی مک، `.env` و دیتابیس و `bot.log` هم همین‌جاست (در گیت نیستند). |
| `website/` | سایت معرفی برای گوگل (`build.py`، `pages.py`، `assets/`، `Dockerfile`، تست `test_site.py`). خروجی: `website/dist`. |
| `deploy/` | تنظیمات سرور: Caddy (HTTPS)، پشتیبان‌گیری روزانه، راهنمای فارسی راه‌اندازی سرور. |
| `docker-compose.yml` | روی سرور همه را با هم بالا می‌آورد: ربات، دیتابیس، سایت، Caddy، پشتیبان. |

## راه‌اندازی اولیه روی مک
```
cd ~/Projects/UploadFly
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -r bot/requirements.txt -r bot/requirements-dev.txt
cp bot/.env.example bot/.env      # توکن ربات و ENCRYPTION_KEY را در bot/.env بگذار
brew install ffmpeg cloudflared
```

## کنترل ربات (سرویس launchd، پوشه‌ی کار: bot/)
- ری‌استارت بعد از تغییر کد: `launchctl kickstart -k gui/$(id -u)/com.uploadfly.bot`
- خاموش: `launchctl bootout gui/$(id -u)/com.uploadfly.bot`
- روشن: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.uploadfly.bot.plist`
- لاگ: `tail -f ~/Projects/UploadFly/bot/bot.log`

## تست‌ها
- همه (ربات + سایت): `.venv/bin/python -m pytest -q`
- ساخت سایت روی مک: `.venv/bin/python website/build.py --url https://دامنه`
