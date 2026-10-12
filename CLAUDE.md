# UploadFly — project context for Claude Code

## Working with the owner
- The owner has ~10 years in IT but **no programming knowledge**. You write the code; explain what you did and what they must do in **simple Persian (Farsi)**, step by step.
- Be **critical**. Keep the main goal in view. If a task is unnecessary or harmful to the goal, say so or skip it before doing it.
- **User growth matters more than revenue.**
- Never print, log, or commit the bot token or any secret. Secrets live only in `.env` (git-ignored).
- After each change: restart the bot and tell the owner exactly what to test in Telegram.
- Work in small, testable steps. Do not start the next step until the owner confirms the current one works.
- **Test everything yourself before handing off** (owner's explicit rule): run `.venv/bin/python -m pytest -q` (also on PostgreSQL with `TEST_DATABASE_URL=postgresql+asyncpg://...`, and inside Docker with `docker build --target test`) (fake Telegram in `tests/conftest.py`: flows as seller and buyer, chat and Mini App API), add a test for every new flow or bug, and check the Mini App at phone size in the browser pane with signed test `initData`. Only ask the owner to test what needs a real Telegram client (payments, real uploads), and say what you already verified.

## Product
Telegram uploader bot. Anyone sends any content (file, photo, video, music, voice, video note, GIF, text) and gets a link. A link is either free, or paid with Telegram Stars to unlock the content.

**Direction (owner decision 2026-10-10): creator platform inside Telegram (only loosely inspired by OnlyFans; never name it to users).** Not adult content:
creators of any kind (fitness, education, art, music…) get a page with subscriptions, locked posts, tips and paid
messages; 0% commission (Stars go to the creator's own bot). Adult content rules stay exactly as in decision 5 (seller bots
only, marked sensitive, never in Explore) plus a one-time 18+ confirmation for buyers. The free uploader stays as a side tool.
Owner was told the legal risk of adult content in Iran and Telegram's ToS; revisit only if the owner asks.

## Key decisions (do not change without asking)
1. **Stars must go directly to sellers, never to the platform.** A single shared bot can't do this (bot payments credit the bot's own balance). So: free links live in the main UploadFly bot; a seller who wants to sell gets **their own bot**, created in one tap via Telegram **Managed Bots** (Bot API 9.6: `t.me/newbot/Uploadfly_Bot/<username>` → `managed_bot` update → `getManagedBotToken`; "Bot Management Mode" is on in BotFather) or connected by pasting a token. The seller owns the bot. We run it multi-bot; buyers pay the seller's bot; the seller withdraws via Fragment themselves.
2. `file_id` is per-bot. Paid content must be uploaded inside the seller's own bot. Every `Content` row stores `bot_id`.
3. **All delivered content is protected** (`protect_content=True`), free and paid: no forwarding or saving (owner decision 2026-10-06; replaces "free links are forwardable"). Growth comes from sharing the *link*, which forces recipients to open the bot. Note: screen capture on desktop/web or filming with another device cannot be prevented by any bot.
4. **Fraud prevention is automatic, no human reviewer:**
   - System-verified specs from Telegram metadata (type, size, duration, resolution, file name) — not seller claims.
   - System-generated preview the seller can't choose (blurred PDF first page, random video frames, audio snippet, first text lines). Bot API download limit is 20 MB; larger files get specs only until a local Bot API server is added.
   - AI check: caption vs real specs; block forbidden content. **Postponed** (owner decision 2026-10-07: unsure about running costs). Options presented: Claude API (needs an account in a supported country) or a self-hosted open-source image classifier after the server exists. Revisit later.
   - Refund only before the buyer opens the content (`opened_at` = content delivered to chat; same for every type), ≤24h, max 3 refunds/buyer/30 days.
   - **Reports never act automatically** (owner decision 2026-10-08: several cheap purchases from different accounts could kill a competitor's shop). Buyer picks a reason (`REPORT_REASONS`: mismatch, broken, forbidden, other); "forbidden" alerts `ADMIN_IDS` immediately; admin reviews with `/reports` and decides with `/suspend`, `/unsuspend`, `/takedown`, `/ban`. Reports do not lower the price cap.
   - Gradual trust: new sellers have a low price cap that rises with good history (`app/trust.py`: <5 sales 100⭐, <20 → 300, <100 → 1000, else 10000). Reviews only from real buyers.
   - Blacklist by `file_unique_id` (`Blacklist` table), set by admin `/takedown`. Admin commands in `app/admin.py` for `ADMIN_IDS` (`/takedown`, `/ban`, `/unban`, `/reports`, `/suspend`, `/unsuspend`, `/stats`, `/srclink`, `/refundtests`). `/refundtests` refunds, after confirmation, every unrefunded payment and membership in the shops the sender owns, and cancels subscriptions. It exists to return the owner's own test Stars.
5. **Forbidden content** (must be blocked): weapons trafficking, drugs, human trafficking, scams, and **any sexual content involving minors (zero tolerance)**. Copyright is not policed.
   - **Adult content** (legal, adults only): forbidden in the main bot; allowed only in seller bots and must be marked **sensitive**. Rationale: reports then hit the seller's bot, not @Uploadfly_Bot. Step 3 AI must detect unmarked adult content.
   - **Sensitive content** (`Content.is_sensitive`, set by seller via toggle when pricing): auto-deleted after a view window (`content.view_seconds`: duration + 2 min, photo 1 min, text 2 min, document 5 min); buyer re-opens the link to see it again without paying. Deletions are persisted in `DeleteJob` and run by `BotManager._delete_loop`.
6. Languages: Persian, English, Russian, Arabic, Chinese (Simplified) — owner decision 2026-10-07. Mini App: `webapp/i18n/<lang>.json`. Bot chat: fa/en in `app/texts.py`, ru/ar/zh in `app/i18n/<lang>.json` (missing keys fall back to English; `tests/test_texts.py` checks keys, placeholders and Telegram HTML). `/lang` offers all 5; seller bot descriptions are set in all 5. New users get their language from Telegram's `language_code` (`texts.detect_language`: ru/uk/be/kk→ru, ar→ar, zh→zh, everything else incl. en→fa because most Iranian users run Telegram in English).
7. Cut from the original mockup: public chat (removed), fake rank/stats, in-app language picker screen, long splash, Tailwind/CDN assets (self-hosted instead; Google Fonts is blocked in Iran).
8. **Mini App is built now, before buying a server** (owner decision 2026-10-06), developed on the Mac through a Cloudflare quick tunnel (`app/tunnel.py`); production uses a fixed `WEBAPP_URL`. Owner wants most work done in the Mini App: shop creation (token form), product management, sales, storefront, in-app payment via the seller bot's invoice link, uploads up to 50 MB. **Stays in chat:** forwarding files from other chats/channels and big files (up to 2 GB), and **delivery of purchased content** (`protect_content` only works in chat).
9. **Design system is locked in `design.md`**: "Soft files" (owner references 2026-10-08: Dribbble "Cloud Storage App, Beyond Neumorphism" + "File Manager App Concept"; replaces the rejected "Night market"). Theme follows Telegram light/dark (`data-theme`); light = soft neumorphic, dark = charcoal file manager; one colour per content kind; navy balance card with withdraw ring; bottom bar with 4 tabs (Home, Products, Purchases, Profile) + center upload button; language is a sheet in Profile. Tokens in `webapp/tokens.css`. Every UI change reads `design.md` first.
10. **Chat and Mini App, no "mode" choice** (owner decision 2026-10-08): no asking users to pick chat or Mini App. Chat = quick actions (send/forward → link, pricing buttons, delivery of purchases); Mini App = management. Don't rebuild every Mini App feature in chat. **Notifications:** loud only for what needs attention (new sale, purchase delivery/"paid" message, refund, report, suspension, takedown, shop ready/revoked); everything else that is only a record (preview echo, link/published confirmation, auto-delete notice, "report" offer, "Powered by") is sent with `disable_notification=True` (`tests/test_notify.py`). Command menu (`texts.COMMANDS`, `bots.setup_commands`/`set_user_menu`) is per language: default Persian, ru/ar/zh by Telegram language, a per-user menu when the chosen language differs.

## Brand (owner decision 2026-10-11)
- Logo "Lift-off": a U-shaped vault holding a gold Star; its right leg breaks off and rises as an upload arrow. Tagline: «فایلت پرواز می‌کنه؛ پولت پیش خودت می‌مونه.» / "Your files fly. Your Stars stay yours."
- Brand book (logo files, colours, type, voice, social and bot templates) is a Design System artifact made in a claude.ai session ("UploadFly Brand Book"). Brand colours are the Mini App's own tokens (indigo #5b5bd6, sky #33c3e8, navy #1b1d3f, gold for Stars only), so the Mini App design system is unchanged.
- The robot-bee picture (`bot/webapp/logo.jpg`) is retired as a logo; replace it with the new icon when the Mini App is next touched.
- Profile picture everywhere: the sky avatar (white mark, gold Star, indigo-to-sky gradient).
- Brand voice for all video voiceovers (owner decision 2026-10-11): ElevenLabs designed voice "UploadFly Voice (test 1)", voice_id `uzRbOCCL1qz5xYpmNlv4` (male, about 30, warm and playful). Generate with model `eleven_v4` and emotion tags ([surprised], [laughs], [warmly] ...): flat reads sound synthetic. Publishing needs a paid ElevenLabs plan (Starter or higher) for the commercial licence; captions say the voice is AI-made.

## Revenue ideas for later (not in MVP)
Premium plan for sellers paid in Stars to the main bot (big-file previews, analytics, bundles, promo codes, remove "Powered by UploadFly"); featured listings; ads before free-link delivery.

## Stack
Python 3.11+, aiogram 3, SQLAlchemy 2 (async). SQLite locally, PostgreSQL in production (same code, `DATABASE_URL`). Later: Docker on an EU VPS, ffmpeg + PyMuPDF for previews, Alembic migrations.

## Layout
**Folders (owner request 2026-10-11):** `bot/` = bot + Mini App (all paths below under `bot/` unless they start with `website/` or `deploy/`), `website/` = marketing site (was `site/`), `deploy/` + `docker-compose.yml` at the root (server runs both). On the Mac the runtime files live in `bot/` too: `bot/.env`, `bot/uploadfly.db`, `bot/bot.log`, `bot/cache/`; `.venv/` is shared at the root. Tests: `.venv/bin/python -m pytest -q` from the root runs bot + website (root `pytest.ini`, `pythonpath = bot`); `cd bot` runs only the bot (Docker test image: `docker build --target test ./bot`). The website has its own image (`website/Dockerfile`) and test (`website/test_site.py`).
- `app/main.py` — entry point; builds the shared Dispatcher and starts `BotManager`
- `app/bots.py` — `BotManager`: one polling loop per bot (main + sellers), add/remove seller bots at runtime
- `app/handlers.py` — shared handlers (main and seller bots): links, /mylinks, /lang, upload, pricing
- `app/connect.py` — main bot only: one-tap shop creation (managed bots), `/connect` (token, encrypted), `/disconnect`; `attach_bot` shared by both; one shop per user; owner change disconnects
- `app/shop.py` — main bot only: "My shop" button panel (`/shop`, `shop:*` callbacks): balance, sales, links, withdraw guide, disconnect
- Wallet (owner decision 2026-10-08): Stars stay in the seller's own bot (Telegram has no bot→user Star transfer; `sendGift` gifts can't be converted; being a Stars reseller via Fragment would make us a money middleman, rejected). Mini App wallet page (`/api/wallet`, `shop.wallet_view`): balance, available vs 21-day hold (estimated from our sales), next unlock, sales history, withdraw guide; **Telegram Premium for the owner paid from the bot balance** (`/api/wallet/premium`, `giftPremiumSubscription`: 3/6/12 months = 1000/1500/2500★). **Trust package** (sellers fear for their money): "Your money stays with you" card (home without shop + wallet), "Check yourself in Telegram" sheet (bot profile → Edit → Balance), money FAQ sheet (also in Profile) linking telegram.org/tos/stars, and a special first-sale chat message (`first_sale`); every sale message says the Stars went to the seller's own bot
- **Creator features** (`app/creator.py`, chat; `app/web_creator.py`, Mini App API; `webapp/creator.js`, UI; texts in `app/texts_creator.py` + `webapp/i18n`):
  - Tips: payload `t:<amount>[:<content>]`, `Tip` table, `/tip` in seller bots and a tip sheet in the store; loud message to the creator.
  - **Anonymous to the creator:** the creator never sees a fan's name, @username or Telegram id (DM header, donation notice, Fans list); only a stable per-bot number (`creator.fan_numbers`, order of `Follower`), shown as «فن شماره‌ی N». No reactions on the creator's messages.
  - Fan DMs work like anonymous-chat bots, threaded both ways (`DmLink.fan_message_id`): the fan's message reaches the owner, the owner's Reply reaches the fan as a reply to the fan's message, and a fan's Reply comes back as a reply to the owner's message. A Reply to a fan clears any half-finished owner step. The store's Message button calls `POST /api/store/<bot>/dm`: the creator bot posts a "write here" prompt in the fan's chat and the Mini App closes (opening the same bot's chat from its own Mini App does nothing). Tips are called "donate" (fa «دونیت», command `/donate`, old `/tip` still works).
  - Fan DMs: a non-owner message in a seller bot is copied to the owner (header "message from…" with block button, `DmLink`, `DmBlock`); the owner answers with Reply (copy, protected). `Seller.dm_mode`: all / fans (default; buyers, members, tippers) / off. 30 messages per fan per hour.
  - Paid messages: owner replies with media → price buttons (`ppv:<content>:<fan|b>:<price>`) → hidden post (`in_store=False`) + offer to that fan.
  - Broadcasts: `/broadcast` (also `?start=broadcast`) → segment (all followers+fans, active subscribers, expired, buyers) → text (copy) or media (free/locked); silent, background (`creator.TASKS`), max 3 per 24h (`Broadcast`).
  - `Follower` = anyone who used the creator bot (recorded in `DbMiddleware`). Fans list `/api/fans`, earnings by type in `/api/wallet`.
  - Welcome message (`Seller.welcome`) after the first paid join or a free trial. Free trial (`Showcase.trial_days`, monthly only, once per user, `Membership` with `charge_id` `trial:<sc>:<user>`); a trial member can subscribe. Bundles (`Showcase.bundles`, 3/6/12 months, 0–50% off, one-time payment `s:<id>:<months>`, extends from current end; not while an auto-renewing subscription is on).
  - Likes (`Like`), "notify fans" once per post (`Content.notified_at`, silent), scheduled drafts (`Content.publish_at`, `BotManager._scheduled_loop` every minute), photo watermark with the buyer's username (`Seller.watermark`), creator referral `?start=ref_<id>` (`User.referrer_id`), 18+ confirmation (`User.adult_ok`; chat button `adult:<code>`, Mini App `POST /api/store/<bot>/adult`).
  - Explore `/api/explore` (main bot only): listed, not suspended, has public posts, **no active sensitive content**; `Seller.bio`, `Seller.category` (`creator.CREATOR_CATEGORIES`), `Seller.listed`.
- `app/payments.py` — seller bots only: offer + Stars invoice (`XTR`), pre-checkout check, protected delivery, `Purchase`
- `app/preview.py` — system-made previews built when a paid price is set (blurred photo, 3 random video frames, PDF page 1 + page count, 15s audio, first text lines; sensitive = stronger blur; >20MB = Telegram thumbnail). Stored as file_ids in `Content.preview`. Needs ffmpeg, Pillow, PyMuPDF
- **Showcases** (`app/showcases.py`, owner request 2026-10-08, creator page; aim: sellers put the showcase link in their Instagram bio): main showcase = `Content.in_store` (always free) + extra `Showcase`s per shop with access `free` / `once` / `monthly` (Telegram Stars subscription, 30 days, `subscription_period`). `ShowcaseItem.member_free` = free for members, else the item's own price. `Membership` = paid entry (refundable 24h only until the first item is opened); member-free items are delivered via a 0-Star `Purchase` (`charge_id` `m<membership>:<content>`) so protected delivery, purchases list and reports reuse the normal path. Link `t.me/<shop_bot>?start=sc_<code>` → chat button → Mini App `?store=&bot=&sc=`. UI: Home "My showcases" cards with "Bio link" copy, 3-step editor sheet, showcase chips in the product editor, buyer page with cover/avatar/stats/join button/locks and a "Made with UploadFly" growth footer. Monthly: `showcases.subscription_tick` (every 30 min in `BotManager`) sends a renewal reminder 3 days before and an end message after expiry; members can turn auto-renewal off/on (`editUserStarSubscription` with the first charge id, `Membership.sub_charge_id`). Seller sees member stats in the showcase editor; memberships count in wallet and home stats (0-Star unlocks never count as sales). **Ratings** (`Review`): 1–5 stars only from buyers who opened the content (chat buttons after delivery + buy sheet), shown on cards and shop header. Home shows best sellers (30 days)
- **Showcase look + story card + start checklist** (owner request 2026-10-09; `app/looks.py`, design.md § Showcase looks):
  - 4 themes: soft, sunset, aurora, noir. Banner is per showcase (`Showcase.cover`; the main showcase uses `Seller.cover`). Logo is per shop (`Seller.logo`).
  - Images: re-encoded JPEG stored in the `images` table with a random id. Served at `/api/images/{id}` (buyers too).
  - Look editor: owner opens their showcase → "Look" sheet with a live preview. Endpoint: `PATCH /api/look`.
  - Story card: drawn in the phone (canvas, QR from `/api/qr`). Uploaded to `/api/story` and served for 30 minutes at the public `/story/<token>.jpg`, so Telegram `downloadFile`/`shareToStory` can fetch it.
  - Style editor (sheet with 4 tabs: theme, cards, layout, sections):
    - `Showcase.style` / `Seller.style` JSON (`looks.style_of`, `merge_style`).
    - Pinned post must belong to that showcase.
    - Shop-wide social links: `Seller.links` (`looks.clean_links`).
    - Stage 2: background image (`background` column, re-encoded 1080×1920, faded under the content) and header `cover`/`center`.
    - Title font `classic`/`bold`/`light`/`plex`: only self-hosted fonts.
  - Home "Get started" checklist: product → look → bio link (copy tracked in CloudStorage) → first sale.
- **Security rule**: initData signed by a *seller* bot (`X-Bot-Id`) is trusted only for that bot's own store and showcases (`guest_of_seller_bot`), unless the user owns that bot. A seller has their token and could otherwise sign as anyone. Every new `/api/*` route must be checked against `allowed_for_guest`.
- Free links in the Mini App: Files tab has two sides, "Shop" (products) and "Free links" (`/api/links`: own main-bot content, thumb, disable); users without a shop see only free links
- Shop window visibility: `Content.in_store` (default on; editor switch). Off = hidden from the store window/Explore but its own link still sells (owner request 2026-10-08)
- `app/web.py` — Mini App web server (aiohttp, same process): `/api/*` requires Telegram-signed `initData` (`Authorization: tma ...`); static files from `webapp/`
- `app/tunnel.py` — Cloudflare quick tunnel for local HTTPS; sets the main bot's menu button to the Mini App. Watchdog: if the tunnel URL stops answering 3× while Cloudflare itself is reachable, the app exits so launchd restarts it with a new tunnel
- `webapp/` — Mini App front end: `index.html`, `tokens.css` (design tokens + fonts), `app.css`, `app.js`, `i18n/*.json` (one file per language; same keys and `{placeholders}`, checked by a test), self-hosted fonts (SIL OFL). First-run 4-step guide (seen-flag in Telegram CloudStorage + localStorage)
- `Dockerfile` (targets `app` and `test`), `docker-compose.yml` (bot, postgres, caddy HTTPS, daily backup), `deploy/` (Caddyfile, backup.sh, Persian server guide `README.fa.md`), `scripts/migrate_sqlite_to_postgres.py` (one-time data move, refuses non-empty target)
- `tests/` — pytest suite with a fake Telegram (`MockSession` records every bot call) and a temp SQLite DB; `test_flows.py` (bot flows), `test_web.py` (Mini App API)
- `app/content.py` — extract content metadata from messages / resend by file_id
- `app/db.py` — models: `User`, `Content`, `Seller`, `Purchase`, `DeleteJob`; `_ADDED_COLUMNS` = tiny migration until Alembic
- `app/middlewares.py` — DB session, user upsert, ban check; sets `data["seller"]` (None in main bot); `main_bot` / `seller_bot` filters
- `app/crypto.py` — Fernet encryption of seller tokens (`ENCRYPTION_KEY` in `.env`; never change it)
- `app/texts.py` — fa/en chat texts (+ loads `app/i18n/{ru,ar,zh}.json`), spec and wait-time formatting. Default language is Persian; users switch with `/lang`

**Payment support (Telegram rule for Stars sellers):**
- `/paysupport` in seller bots (also in the seller menu): refund rules, report button, seller contact.
- `/paysupport` in the main bot points to the shop's bot.
- `/terms` works in both bots.

**Source tracking** (owner decision 2026-10-09):
- `User.source` is recorded on first contact. Values: `src_<tag>` (ad link `t.me/Uploadfly_Bot?start=src_<tag>`, made with admin `/srclink <tag>`), `link` (free link), `shop` (seller bot / store), `direct`, `miniapp`, `src_made` ("Made with UploadFly" footer).
- `/stats` shows the last 30 days per source: users, shops, shops with a sale, buyers.

**Stars help for Iran:**
- "No Stars? Where to buy" button in the buy sheet and the join card opens a sheet with the user's own @username to copy.
- `/stars` in chat, linked under every offer.
- Wallet has a "Stars to toman" card: Fragment → TON → Iranian exchange. We name no specific seller or exchange.

**Admin panel: cancelled** (owner decision 2026-10-09, after a Mini App version and a desktop web version were built). All of it was removed: no `/admin`, `admin_api`/`admin_auth`, `AdminSession`/`AdminLog`, free admin view of paid content, or `Purchase.report_status`. Admin work stays in the main-bot chat commands (`app/admin.py`). Don't rebuild a panel unless the owner asks again.

**Support** (owner decision 2026-10-10; the ticket system was removed): Mini App Profile → Support (`page-support`, also `?page=support`).
- Searchable FAQ in 5 categories: start, sell, buy, money (reuses `faq_q1-5`), safety. Keys `help_qN`/`help_aN`, in all 5 languages.
- Then "Didn't find your answer?" with **direct chat to the support Telegram account** and **email**. The values come from `.env` (`SUPPORT_USERNAME`, `SUPPORT_EMAIL`, validated in `config.py`); a button is hidden while its value is empty.
- The card also shows the user's ID with a copy button.
- Chat `/support` (also `?start=support`, for the website and shop bots) shows the same options.
- `/paysupport` points to `/support`.
- One Telegram BackButton handler (`onBack`) closes only the top layer.
- Image uploads: max 40 per day per seller; unused images are deleted after a day (`looks.cleanup_orphans` in the 30-minute loop).
- Invoice creation: max 30 per user per 10 minutes (`rate_ok`).
- Never query with a session outside its `async with` block: it leaks DB connections (seen in `/api/me`).

**Admin `/stats`** includes a growth funnel (`admin.funnel`) for all users and for the last 7 days: joined → made a link → shop → published → first sale, plus buyers.

**Website** (owner request 2026-10-10, for Google traffic): static site in `website/` (was `site/`).
- `build.py`, stdlib only: `python3 website/build.py --url https://domain` writes `website/dist` (clears the folder's contents, not the folder: on the server it is a Docker volume).
- `pages.py` holds the content. Persian pages: `/`, `/sell/`, `/free-link/`, `/showcase/`, `/telegram-stars/`, `/faq/`, `/terms/`, `/privacy/`, `/404.html`. English: `/en/`.
- `assets/`: self-hosted fonts, CSS, a tiny JS for the mobile menu, icon, OG images. Since the 2026-10-11 brand, `icon.svg`, `icon-512.png`, `og-fa.png`, `og-en.png` come from the brand kit ("Lift-off" logo); `make_images.py` still draws the OLD design, so don't rerun it.
- Official profiles in `build.SOCIAL` (Organization `sameAs` + footer): Instagram @UploadFly, Telegram channels @UploadflyFA (fa footer) and @UploadflyEN (en footer).
- SEO keywords (Google autocomplete research 2026-10-11): ربات آپلودر تلگرام (رایگان، ساخت، چیست) → /free-link/; فروش فایل در تلگرام، ربات فروشگاهی تلگرام، آموزش فروش در تلگرام، فروش فایل PDF/دوره → /sell/; لینک بیو اینستاگرام، ساخت کانال VIP در تلگرام → /showcase/; استارز تلگرام چیست، خرید استارز، نقد کردن استارز → /telegram-stars/. Not targeted on purpose: VPN/config bots, trading-signal VIP channels.
- SEO: title, description, canonical, hreflang, OG, JSON-LD (Organization, WebSite, SoftwareApplication, FAQPage, BreadcrumbList), `sitemap.xml`, `robots.txt`, optional `GOOGLE_SITE_VERIFICATION`.
- Every CTA is `t.me/<bot>?start=src_site_<page>`, so Google traffic shows in `/stats` sources.
- Honest copy only: no invented numbers or testimonials.
- Deploy: the compose service `site` (image `./website`) builds into a volume with `SITE_URL=https://${SITE_DOMAIN}`. Caddy serves `SITE_DOMAIN` (www redirects to it); the bot and Mini App are on `DOMAIN` (e.g. `app.`). The DNS steps are in `deploy/README.fa.md` §2.5 and §8.
- Home (fa/en) has a "Your market: Earth" globe section (owner request 2026-10-10, inspired by Cloudflare's "Region: Earth"): `assets/globe.js`, plain canvas, land dots from `assets/globe-land.js` (Natural Earth mask made by `make_globe.py`), drag to spin, Star arcs from world cities to Tehran (illustrative, no numbers). Scripts load only on pages with `data-globe`.
- Test: `website/test_site.py`.

**Local backup until the server exists:**
- `bot/scripts/backup_local.sh` runs as the launchd job `com.uploadfly.backup` (daily at 04:00, or on wake).
- It does a sqlite `.backup`, then an integrity check, then gzip into `~/UploadFly-backups`, keeping 30 days.
- The DB is useless without `ENCRYPTION_KEY`; the owner keeps `.env` safe separately.

Project lives at `~/Projects/UploadFly` (moved off the Desktop: macOS blocks background services from Desktop).
Run locally as a launchd service `com.uploadfly.bot` (`~/Library/LaunchAgents/com.uploadfly.bot.plist`, WorkingDirectory `bot/`): starts at login, restarts on crash, `caffeinate` keeps the Mac awake; if the Cloudflare tunnel dies the app exits and launchd restarts it with a new tunnel. Log: `bot/bot.log`.
- Restart after code changes: `launchctl kickstart -k gui/$(id -u)/com.uploadfly.bot`
- Stop: `launchctl bootout gui/$(id -u)/com.uploadfly.bot` · Start: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.uploadfly.bot.plist`
- Never run a second copy (e.g. `python -m app.main` by hand) while the service runs: two pollers conflict.

## Roadmap — Phase 1 (MVP)
- [x] Step 1: main bot, any content → free link, `/mylinks`, verified specs stored, `file_unique_id` stored
- [x] Step 2: connect seller's own bot (multi-bot), paid links, Stars invoice (`XTR`), protected delivery
- [x] Step 3: auto preview, refund-before-viewing + scam reports + auto-suspend, price cap, blacklist, admin tools (AI moderation postponed)
- [x] Step 4: **deployed 2026-10-12** on ParsPack deVPS4 (Frankfurt, Ubuntu 24.04, IP 195.248.243.24), domain `uploadfly.cloud` (DNS at ParsPack: A records `@`, `www`, `app`, DNS-only). Code at `/root/uploadfly` (git clone via a read-only deploy key `~/.ssh/uploadfly_deploy`), `.env` at `/root/uploadfly/.env` (copied from the Mac, plus `POSTGRES_PASSWORD`, `DOMAIN=app.uploadfly.cloud`, `SITE_DOMAIN=uploadfly.cloud`, `MAIN_BOT`). SSH from the Mac: `ssh uploadfly` (key `~/.ssh/uploadfly_server`); password login and keyboard-interactive are off, ufw allows only 22/80/443. Update: `ssh uploadfly 'cd /root/uploadfly && git pull && docker compose up -d --build'`. Logs: `docker compose logs -f bot`. Data moved from SQLite with `bot/scripts/migrate_sqlite_to_postgres.py` (now copies every table; all 17 matched). **The Mac launchd jobs `com.uploadfly.bot` and `com.uploadfly.backup` are disabled** (`launchctl disable`): never start the Mac bot again, two pollers conflict; the Mac DB is a frozen copy (`~/UploadFly-backups/uploadfly-final-before-server.db`). Still to do: BotFather Main Mini App (owner), Local Bot API server, `SUPPORT_USERNAME`/`SUPPORT_EMAIL` in the server `.env`.
Phase 2: Mini App dashboard (reuse the owner's original design, rebuilt cleanly), stats, bundles.
