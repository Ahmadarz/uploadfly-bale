# UploadFly for Bale — project context for Claude Code

> **This repository is the Bale (بله) version** (owner decision 2026-10-12): a separate product for Iran, in its own repo
> (`uploadfly-bale`), with no link to the Telegram repo or its server. Everything below the line "Original Telegram
> context" describes the code this port started from; treat Telegram-only parts as *not yet ported*.

## Bale port: facts and decisions
- Owner's PC is Windows: project at `E:/cloud/uploadfly-bale`, venv at `.venv/Scripts/python.exe` (**Python 3.10**, so
  no 3.11-only APIs such as `asyncio.timeout`; the Docker image is 3.12), secrets in `bot/.env`.
  Tests (PowerShell): `$env:PYTHONUTF8='1'; .venv/Scripts/python.exe -m pytest -q` (without UTF-8 mode some tests fail
  on cp1252; 184 tests on 2026-10-13: bot + website). No ffmpeg, Docker, cloudflared or `gh` here yet.
  Test bot on Bale: `@uploadflybot`; the owner's test shop is `@babkad_bot` (public test wallet token).
  The owner starts the bot with `start-bot.bat` (repo root); Claude runs it as a background task
  (`cd bot && PYTHONUTF8=1 ../.venv/Scripts/python.exe -m app.main > bot.log 2>&1`). Never two copies at once.
  `.gitattributes` keeps LF everywhere (server scripts break with CRLF); only `*.bat` is CRLF.
  Edit scripts: Git Bash heredocs break on Persian text with quotes; write a small Python script with the Write tool.
- Bale Bot API = Telegram-like at `https://tapi.bale.ai` (docs: docs.bale.ai, docs.bale.ai/miniapp). aiogram works against
  it through `app/bale.py` (`make_bale_bot`): custom API server + a request middleware that converts the app's HTML texts
  to Bale Markdown and skips methods Bale lacks. Keep writing texts as HTML; never add `parse_mode`.
- Verified live on 2026-10-12:
  - Formatting: no HTML. `*bold*`, `_italic_`, `[text](url)`, triple-backtick block work. Single backticks and backslash
    escapes do NOT work. `_` and `*` inside ordinary words are left alone.
  - Works: inline buttons (callback, url, copy_text, web_app), edit/delete message, `setMyCommands` (also with scope and
    language_code), deep links `ble.ir/<bot>?start=<param>`, `sendInvoice`/`createInvoiceLink` (currency `IRR`, amounts in
    rials, `provider_token` = wallet token per bot from Bale's @botfather; test token `WALLET-TEST-1111111111111111`),
    `pre_checkout_query`, `successful_payment`, `inquireTransaction`.
  - Missing: `protect_content` (accepted but ignored), `setMyDescription`/`setMyShortDescription`, `setChatMenuButton`,
    `getUserProfilePhotos`, `sendVideoNote`, Stars, subscriptions, managed bots (no bot creation by API).
  - **File uploads**: Bale rejects aiogram's `attach://` form ("failed to get HTTP URL content"); the file must sit
    in its own field. `bale.BaleSession.build_form_data` does this. This bug kept the owner's first products as drafts
    (preview upload failed while pricing). `sendMediaGroup` accepts uploads and file_ids but its response carries no
    `photo`/file_ids, so previews with several frames are uploaded one by one (`preview.create`), and sending a
    preview can never block publishing any more.
  - `refundStarPayment` exists as a handler but returned 500 on a test-token payment; real refunds are unverified.
  - **From Bale's own docs (read 2026-10-13, docs.bale.ai and /miniapp):**
    - Payment: the bot needs a "توکن پرداخت کیف پول" made in @botfather for that bot; the money goes at once to the
      wallet of the bot's developer. Card-to-card invoices were removed; the wallet is the only official way. Wallets
      come as personal / business / organisational; the wallet API lists transaction inquiry, **reversal** and
      **split (تسهیم)** services (a possible future path for refunds or a platform fee; not explored).
    - **Rate limits are "interactive"**: a bot's sending capacity depends on how much its users interact with it in
      private chats. Bulk or re-engagement messages are meant for the paid business API
      (`tapi.bale.ai/business/bot<TOKEN>/…`, charged per message from a business panel balance; only getMe,
      sendMessage, forwardMessage and file_id sends). So `/broadcast` may be cut off: `creator.run_broadcast` stops on
      `TelegramRetryAfter` or after 12 failures in a row and tells the owner (`bc_limited`).
    - Files: by file_id no limit; multipart upload 10 MB photos / 50 MB other; bots download up to 20 MB;
      `sendVoice` needs ogg ≤ 1 MB.
    - Mini App: every bot has one **main Mini App**, enabled in @botfather (direct link `ble.ir/<bot>?startapp[=p]`,
      search, bot profile, chat list); the menu button can also be pointed at a Mini App there. Bale web opens Mini
      Apps in an iframe (CSP `frame-src https://*.bale.ai`, no `X-Frame-Options`; already so). Old clients:
      `Bale.WebApp.isMiniAppSupported` is false and `openInvoice` needs SDK version ≥ 1.3; the adapter answers
      `"unsupported"` and the app sends the buyer to pay in the shop chat (`payInChat`). Bale says in-app payment
      can break on old Android with URL-based routers; this app has no router (keep it that way).
  - `editMessageText` returns `message_id: 0`; `successful_payment` messages also have `message_id: 0`.
- Decisions (owner, 2026-10-12):
  1. **Money goes straight to the seller**: each seller creates their own bot in Bale's @botfather and gives us the bot
     token and the wallet token (guided, manual; Bale cannot create bots by API). We never hold sellers' money.
  2. No forward lock exists on Bale; the owner accepts this. Planned mitigation: show purchased content inside the Mini
     App instead of sending it to chat (works up to the 20 MB bot download limit).
  3. Link codes are letters and digits only.
  4. **Persian only.** `T()` always returns Persian; `LANGUAGES == ("fa",)`; `/lang` just says so. The old
     en/ru/ar/zh texts are still in the files but unreachable. Bale-specific chat texts live in
     `app/texts_bale.py` (overrides on top of the old Persian texts); say «بازو», «کیف پول بله», «تومان».
  5. **No adult content at all** on Bale (Iranian law and Bale's rules); `/terms` says so. This replaces the
     Telegram decision 5 below. (Changed by Claude on 2026-10-12 as a legal necessity; owner informed.)
     Consequences (2026-10-13): "sensitive" only means *ephemeral* (auto-deleted after the view window). There is no
     18+ confirmation anywhere (chat gate, `/api/store/<bot>/adult` and the Mini App dialog were removed; the column
     `User.adult_ok` is unused), and shops with sensitive items are no longer hidden from Explore.
  6. **Honest wording is enforced by a test** (`tests/test_texts.py::test_no_false_claims_for_bale`): neither chat texts
     nor `webapp/i18n/fa.json` may say content "cannot be forwarded/saved", mention 18+/adult, Telegram or Stars. The
     Mini App "allow copy and save" switch was removed (Bale ignores `protect_content`, so it did nothing).
- Money model in code:
  - Internal unit is **toman** everywhere (`app/money.py`: limits, presets, `toman()` formatter; real unit 1000,
    tests run with `PRICE_UNIT=1`). The columns `price_stars`/`amount` and the internal currency tag `"XTR"` are old
    names only. `app/bale.py` converts at the border: outgoing invoices → `IRR` ×10 + the shop's wallet token
    (`set_wallet`, `NoWallet`), incoming payments → toman (`to_toman`, called in `BotManager._handle`).
  - Seller connect (`app/connect.py`): `/connect` → bot token → wallet token (`Seller.wallet_enc`, encrypted, checked
    with a throw-away `createInvoiceLink`); `/wallet` to set it later, `/skip` to postpone. No wallet = free content
    only (`wallet_need`).
  - `REFUNDS` in `.env` (default off): off = content is delivered right after payment, no refund button, refund
    endpoints answer `refund_failed`. Turn on only after a real-wallet refund is verified on Bale.
  - Monthly showcases have no auto-renewal: each payment adds 30 days (`Membership.canceled=True`), members may renew
    early; reminders ask them to pay again.
  - Wallet page: `balance` = sum of recorded income; no hold period, no minimum, no Premium.
  - **A shop without a working wallet must never fail silently** (2026-10-13). Guards: chat pricing (`wallet_need`),
    Mini App pricing and paid showcases (`error("no_wallet")`), `/donate`, tips hidden in the store (`shop.pay`).
    Safety net for everything else: `bale.invoice_failed(exc)` (NoWallet, or any API error on `SendInvoice` /
    `CreateInvoiceLink`) → bot side `payments.pay_unavailable` (registered on `dp.errors` in `main.build_dispatcher`):
    the buyer gets `pay_unavailable`, the owner gets `pay_broken_owner` at most every 6 hours; web side middleware
    `web.invoice_errors` answers `pay_unavailable` (409). Mini App home shows a "register your wallet" card and a
    checklist step (`me.shop.wallet`, `wallet_link` = `ble.ir/<main>?start=wallet`, which starts the `/wallet` step).
- Growth and seller acquisition (owner request 2026-10-12: make it practical and marketable on Bale):
  - Positioning used in every text: sell files on Bale with no website and no payment gateway; money goes straight to
    the seller's own Bale wallet; we take no share. Claims must stay literally true (no "cannot be forwarded").
  - `/start` welcome leads with selling; a user without a shop gets one button straight to the 3-step guide
    (`shop:create`), a user with a shop gets "my shop".
  - Onboarding tolerance (`connect.find_bot_token` / `find_wallet_token`): users paste the whole @botfather message;
    the token is found inside it. A bot token sent without `/connect` still starts the connection (and is deleted),
    so it can never become a public "free link".
  - After publishing, the link message has "copy link" and "copy ready-made post" (`products.post_text`, ≤256
    chars: title, price, link) for the seller's channel. There is no share URL on Bale; never link to `ble.ir/share`.
  - Growth loop (`handlers.invite_viewer`): someone who opens another person's free link in the main bot and has made
    nothing yet gets one silent invite with the selling button, at most once a week (`User.cta_at`).
  - **Buyer's name on the file** replaces the missing forward lock: `Seller.watermark` (default ON for new shops,
    toggle in `/shop` → `shop:mark`, also in Mini App settings) stamps `@username`/`id N` on bought photos and on every
    page of bought PDFs (`creator.watermark_pdf`, PyMuPDF, Latin text only, files ≤ 20 MB). The buyer is told
    (`marked_note`). Videos, audio and other files are sent as they are.
  - Already there and useful for ads: `/srclink <tag>` tracked links, `/stats` funnel and sources, `ref_<id>`
    referrals, "Made with UploadFly" footer, `powered_by` after a purchase.
  - Not done yet (need the owner): server + domain (24/7 bot, HTTPS for the Mini App, website), a real-wallet purchase
    and Bale's wallet fee, the bot's name/photo/description in Bale's @botfather, support account in `.env`.
    Ideas offered, not built: Bale landing website (the `website/` folder is still the Telegram text), discount codes.
- **Physical goods** (owner request 2026-10-12; `app/orders.py`, tests `tests/test_orders.py`):
  - A product becomes physical with the "📦 کالای فیزیکی" toggle on the price keyboard (`phys:<id>`, drafts only;
    Mini App API: `physical` on drafts). `Content.is_physical`, `Content.stock` (None = unlimited, 0 = sold out),
    `Seller.shipping_fee` (toman per order, set in the main bot `/shop` → `shop:shipping`). Must have a price; no
    blurred preview (the real photo is the product picture).
  - Buyer opens the link → product card (`orders.send_card`) with "order" → 4-step chat form (name, mobile, address,
    postal code; the last address is offered again) → `Order(status=pending)` → invoice `o:<order_id>` with two lines
    (price + shipping) → pre-checkout re-checks owner/stock/price → `order_paid`: `Order.paid`, a `Purchase` with the
    total (so stats, wallet, ratings and reports work unchanged), stock −1, loud message to the seller with the
    address and a "shipped" button → seller sends the tracking code (or "no code") → buyer is told and can rate.
    `/orders`: seller sees orders waiting to ship, buyer sees own orders. Owner sets stock from the product card.
  - A buyer may order the same product again; physical items are never "bought/opened" in the Mini App and can only
    be paid through the order form (a `c:` invoice is refused, `/api/store/.../invoice` answers `{open: chat link}`).
    The orders router is included before `creator` so form answers are not treated as DMs to the seller; opening any
    link in a seller bot clears a half-filled form.
  - Reports for orders: 30 days from payment, reasons `undelivered / mismatch / forbidden / other`
    (`payments.report_rules`). There is no escrow and no automatic refund: money is already in the seller's wallet.
    Buyer protection is the price cap, ratings and admin action on reports. Tell the owner if this proves too weak.
  - New-seller price caps were raised for Bale (`money.TIER_CAPS`): 500k / 2M / 5M toman, top 10M. Lower caps made
    goods unsellable; higher caps raise the take-the-money-and-vanish risk. Owner may tune.
  - **Orders in the Mini App** (2026-10-13; `app/web_orders.py`, `webapp/orders.js`, page `page-orders`): home row
    "سفارش‌های کالا" (red count while orders wait), tabs waiting/shipped/cancelled, copy address, "shipped" sheet
    with optional tracking code, cancel, shipping-fee field (`PATCH /api/creator {shipping_fee}`). Product editor:
    physical switch (drafts only) + stock field; product cards show a "کالا" / stock / sold-out chip. Buyers see order
    status and tracking in "خریدها" (`/api/purchases` → `order`). Owner-only: a guest of the seller bot gets 403.
  - **Cancel** (`orders.cancel_order`; chat buttons `ocancel:` → `ocancelyes:`, API `POST /api/orders/<id>/cancel`):
    status `canceled`, stock +1, buyer is told to get the money back from the seller, with a report button. The
    `Purchase` is NOT marked refunded (we cannot verify the seller paid back; the buyer must still be able to report).
  - **Buyer addresses are not kept forever** (`orders.cleanup`, every 30 minutes): unpaid forms are deleted after 48h;
    name/phone/address of shipped or cancelled orders are blanked 90 days later (the order row stays for stats). The
    website privacy page promises exactly this; change both together.
  - Not built: quantity per order, product variants (size/colour), several photos per product, cities/zones with
    different shipping fees, a reminder to sellers who do not ship.
- Mini App on Bale (`bot/webapp/`):
  - `bale-sdk.js` = Bale's official `tapi.bale.ai/miniapp.js`, vendored inside an IIFE (the original leaks dozens of
    short globals such as `me`, which broke `app.js`). `bale.js` = adapter that exposes `window.Telegram.WebApp` on top
    of `Bale.WebApp`, so `app.js`/`creator.js` keep using `tg.*`. What Bale lacks is built in-page: MainButton (fixed
    bottom bar, `.bale-main`), `showConfirm`/`showAlert` (modal), haptics (vibrate), no CloudStorage (localStorage),
    `isVersionAtLeast()` is always false (hides story share, file download, home-screen shortcut).
  - Same launch protocol as Telegram: init data arrives in the URL hash (`#tgWebAppData=…&tgWebAppVersion=…&
    tgWebAppPlatform=web`), validated server-side with the same HMAC (`aiogram.utils.web_app`). Local test in the
    browser pane: build such a URL signed with the main bot token, platform `web`.
  - Persian only (`i18n/fa.json`; other language files deleted). Money shown as «N تومان» (`toman()`, `num()` with
    thousands separators; `.cur` span replaces the Star icon). Share buttons use the phone's share sheet or copy
    (Bale has no share URL). No ring/hold/Premium/TON in the wallet.
  - Bale cannot set the menu button by API: `/start` carries a web_app button (`btn_open_app`) when `WEBAPP_URL` is
    set; the owner should also register the Mini App URL in Bale's @botfather once a fixed HTTPS address exists.
  - Logo: `webapp/logo.png` is the brand icon (committed). Bale has no `getUserProfilePhotos`, so the old
    "copy the bot's profile photo" step was removed.
  - Scripts: `app.js`, then `creator.js`, then `orders.js` (each versioned in `web.index`). New pages follow the
    sub-page pattern (`openSubPage`), small sheets use `openSmallSheet` / `closeLangSheet`.
  - In-app payment result: the shape Bale gives back is still unseen on a real phone, so `bale.js` maps every
    common form to Telegram's words (`paid` / `cancelled` / `failed` / `unknown`) and, unless it is plainly `paid`,
    `app.js: paidOnServer` asks the server for a few seconds whether the purchase or membership was recorded
    (the payment reaches the seller bot on its own). Keep the server as the source of truth.
  - Small stat tiles shorten millions (`shortSum`: "12.5" + "میلیون تومان"); full numbers do not fit at 375px.
  - Story card "save": Bale has no `downloadFile`; the phone's share sheet is tried (`navigator.share` with a file),
    then the long-press hint.
  - Date fields (`<input type="date">`: product expiry, showcase expiry, schedule) open the phone's Gregorian
    picker; the same day is written in the Persian calendar right under the field (`syncJalali`, `.jdate`).
  - CSP allows framing by `*.bale.ai` (Bale web opens Mini Apps in an iframe); never send `X-Frame-Options`.
- **Website for Bale** (2026-10-13; `website/`, Persian only): pages `/`, `/sell/`, `/goods/` (physical goods),
  `/free-link/`, `/showcase/`, `/guide/` (bot + wallet token in 3 steps), `/faq/`, `/terms/`, `/privacy/`, `/404.html`.
  CTAs are `ble.ir/<bot>?start=src_site_<page>`. No English page, no globe, no Telegram/Stars words
  (`test_site.py::test_no_trace_of_the_telegram_version`); internal links are checked. `build.SOCIAL` is empty until
  official Bale-version profiles exist (the Telegram product's channels and Instagram must not be linked).
  `assets/og-fa.jpg` was drawn in the browser on a canvas (Pillow here has no raqm, so it cannot shape Persian):
  a throw-away local page draws 1200×630 and POSTs the PNG back; keep the tab in the foreground while it draws.
- **Deploy for Bale** (`deploy/README.fa.md`, `docker-compose.yml`): same Docker stack (bot, PostgreSQL, Caddy, site,
  daily backup) plus log rotation. The guide recommends a server **inside Iran** and warns that Docker Hub is usually
  blocked there (registry mirror needed). Nothing in the guide marked "⚠️ بررسی‌نشده" has been tried on a real server.
  The server starts with an empty database (the PC data is test data).
- Port roadmap: [x] 1. main bot on Bale → free links. [x] 2. chat texts for Bale/toman. [x] 3. seller's own bot +
  wallet token, toman prices, purchase flow (verified by tests and live on Bale: the owner paid a test-wallet invoice
  in `@babkad_bot` and got the file). [~] 4. Mini App on `Bale.WebApp`: ported and checked locally in the browser
  pane at phone size (dashboard, wallet, products, editor, orders, support, storefront; no JS errors); NOT yet opened
  inside the Bale app, because that needs an HTTPS address (`WEBAPP_URL`). In-app payment (`openInvoice`), opening
  chat links and the back button are untested on a real client. [ ] 5. in-app viewer (optional; the buyer's name on
  photos/PDFs is the current answer to "no forward lock"). [~] 6. website and deploy files are ready for Bale; the
  server and domain are not bought yet.
- **Open before launch (owner):** buy server + domain; a purchase with a real wallet token and Bale's fee; the exact
  wallet-token menu in Bale's @botfather (the step-3 guide text and `/guide/` page describe it loosely on purpose);
  name/photo/description of the main bot in @botfather; `SUPPORT_USERNAME`/`SUPPORT_EMAIL`/`ADMIN_IDS`; order a
  physical product with a second Bale account. Claude told the owner on 2026-10-13 that an Iranian online shop may
  need eNamad (اینماد) and that this is the owner's legal check, not something the code solves.
- **Not verified / known risks:** PostgreSQL run of the test suite (no PostgreSQL on this PC); ffmpeg previews
  (video frames, audio snippet); real refunds (`REFUNDS` stays off); Bale's API rate limits (broadcasts) and how many
  long-polling seller bots one process can run (webhooks would scale better); Bale wallet token format.

---
# Original Telegram context

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
