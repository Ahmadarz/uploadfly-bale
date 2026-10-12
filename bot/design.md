# Design — UploadFly

A locked design system for the UploadFly Mini App. Every screen reads this file before
emitting code. Extend or amend this file when the system needs to grow; never improvise per screen.

**"Soft files"**, approved direction 2026-10-08. It replaces "Night market", which the owner rejected.
The owner's references:
- *Cloud Storage App, Beyond Neumorphism* (light, soft raised tiles, navy hero card)
- *File Manager App Concept* (dark charcoal, colourful per-type icons, progress ring)

## Genre
Utility / file manager. Calm, friendly, tactile. Content types are the organising idea.

## Theme follows Telegram
`tg.colorScheme` → `<html data-theme="light|dark">`, updated live on `themeChanged`.
Telegram header, background and bottom bar are painted with `--color-paper` of the active theme.

| Token | Light (neumorphic) | Dark (file manager) | Use |
|---|---|---|---|
| `--color-paper` | #e9ebf3 | #15161b | canvas, Telegram chrome |
| `--color-paper-2` | #f1f2f8 | #1f2027 | cards, tiles, nav bar |
| `--color-paper-3` | #e2e4ee | #2a2b34 | inputs, inset controls, pressed |
| `--color-rule` | ink 7 % | white 7 % | hairlines |
| `--color-ink` | #1c1e3a | #f2f3f7 | text |
| `--color-ink-2` | #575b7d | #a9acba | secondary text |
| `--color-ink-3` | #8a8dab | #737686 | hints |
| `--color-accent` | #5b5bd6 | #7c7cf8 | primary action, selection, ring |
| `--color-accent-2` | #33c3e8 | #3ad0f0 | second gradient stop (ring, bars) |
| `--color-star` | #e6a100 | #ffc53d | Stars amounts only (balance, prices) |
| `--hero-*` | navy gradient #2d3060 → #1b1d3f, white ink | same | balance / create-shop card |
| `--shadow-raised` | dual soft (dark bottom-right, white top-left) | single deep drop | tiles, cards |
| `--shadow-inset` | inset dual | inset dark | search, inputs |

**Kind colours** (one per content type; icon glyph in colour on a 16 % tint of it):
photo orange, video red, animation pink, video_note coral, audio blue, voice teal,
document purple, text green (`--k-<kind>`, `--k-<kind>-soft`).

## Typography (per script; each user downloads only their own script)
| Script | Body | Headings |
|---|---|---|
| Persian (fa) | Vazirmatn | Vazirmatn 700 |
| Arabic (ar) | IBM Plex Sans Arabic | IBM Plex Sans Arabic 600 |
| Latin + Cyrillic (en, ru) | Onest | Onest 700 |
| Chinese (zh) | system (PingFang SC, Noto Sans SC, YaHei) | same |
- Numbers: Onest tabular figures. Wordmark "UPLOADFLY": Unbounded 700, only in splash and header.
- Headings roman, sentence case.

## Shape and spacing
Radius: card 24, tile 20, control 16, pill. 4-pt spacing scale (`--space-*`), gutter 16.
Light theme: surfaces have no borders; depth comes from `--shadow-raised`. Dark: 1px rule plus a drop shadow.

## Layout (Workbench)
- Header: avatar + name on one side, shop status pill on the other.
- **Home** (seller):
  1. Hero card: balance and a ring showing progress to the withdrawal minimum, plus 3 mini stats.
  2. "File types" tiles (count per kind; a tile opens Products filtered by that kind).
  3. 7-day chart.
  4. Shop-window share card.
- **Home** (no shop):
  1. Hero card with create shop.
  2. Recent purchases.
- **Products:** search (inset), status segment, list rows by default (kind icon, name, meta, price); grid optional.
- **Purchases:** its own tab (file-manager rows). Not in Profile.
- **Profile:** centered avatar card, then grouped settings lists. Language is one row that opens a sheet.
- **Bottom bar:** floating surface bar with 4 tabs (Home, Products, Purchases, Profile) and a raised
  circular **upload button** in the middle (shop bot when there is a shop, else the main bot).
- **Buyer (Catalogue):** shop header card, category chips, 2-column cards, bottom sheet, MainButton buy.

## Showcase looks (buyer page only)
Like Linktree: the seller picks one of 4 looks for each showcase (owner decision 2026-10-09).
The dashboard always stays "Soft files", so users don't feel lost between pages.
- `soft` follows Telegram light/dark. `sunset` is light and warm, with glass cards. `aurora` is dark navy with a mint/violet glow.
  `noir` is black with gold hairlines and a gold ring around the logo.
- A look only re-defines tokens on `:root[data-look]` (in `app.css`), plus the Telegram header colour and the MainButton. Never style components per look.
- Banner (per showcase) and logo (whole shop) are uploaded by the seller. Without a banner, the look's gradient is used.
  `soft` falls back to the blurred preview of the first item.
- **Style** (owner request 2026-10-09). Only curated choices, validated by the server (`looks.STYLE_CHOICES`), so every combination stays readable:
  - Card shape: round, sharp, pill, polaroid.
  - Layout: posts, 2 columns, 3 columns Instagram-style, Linktree list.
  - Main colour: theme colour or 6 accents, each with a light and a dark variant.
  - Buttons: gradient, solid, outline.
  - Sections on/off: stats, other showcases, categories, social links.
  - Pinned post. Social links are shop-wide, https only, on the network's own domain.
  - 5 ready-made styles: minimal, insta, luxury, colourful, glow.
- Style lives in `<html data-card|data-btn|data-accent|data-dark>` and affects the buyer page only.
- Story card: 1080×1920 canvas with the look's palette, banner, logo, title, entry badge and QR (always dark on white).
  Content stays inside the Instagram safe zone (top 250 px, bottom 340 px).

## Motion
`--ease-out` cubic-bezier(0.16,1,0.3,1); 160/280/520 ms. Page fade + 8px rise; list stagger 40 ms
(max 8); ring and bars draw in once; balance count-up once. Reduced motion → opacity only.

## Microinteractions
Haptic on every tap; native `showConfirm` for destructive actions; press = scale(0.97) and inset
shadow; focus = 2px accent ring. Toast only when the result is off-screen.

## CTA voice
- Primary: Telegram MainButton in accent colour with white text, or the accent pill in a page.
- Secondary: surface pill. Labels are verbs.

## Creator tools (owner decision 2026-10-10: creator direction)
Same "Soft files" system; no new colours or fonts. Code in `webapp/creator.js` (loaded after `app.js`).
- **Home (creator):** "Creator tools" list card under the start checklist: Fans (count), Message all fans (opens the
  creator bot's `/broadcast`; shows broadcasts left today), My page settings, Invite creators.
- **Home (no shop):** hero says "Create your creator page"; an "Explore creators" card under it. Profile has an Explore row.
- **Pages** (sub-pages with Telegram BackButton): `page-creator` (bio, category chips, Explore switch, DM mode segment,
  welcome message, watermark switch, invite link card), `page-fans` (4 count tiles, broadcast button, fan rows with
  total spent in Stars colour and a status tag), `page-explore` (search, category chips, cards with cover + avatar).
- **Buyer page:** bio under the name; "Tip" and "Message" soft pills; heart likes on feed posts and in the buy sheet
  (`--k-video` red when on); join card adds a free-trial soft button and discounted bundle rows; a trial member sees
  "Free trial until …" and a subscribe button. Tip = small sheet with preset chips + amount input.
- **Editors:** product editor gets "Schedule" (drafts) and "Notify fans" (published, once); showcase access page gets
  trial-day chips and 3/6/12-month discount inputs (monthly only).
- **Wallet:** "Earnings by type" card (paid posts/messages, subscriptions, tips; all-time + 30 days).

## Home banners (owner request 2026-10-10)
- A swipeable slider of 3 banners replaces "Best sellers" on the creator home (best sellers moved to the wallet, under "Earnings by type").
  Newcomers see their own 3 banners under the create-page card. Code: `creator.renderBanners()` in `webapp/creator.js`.
- Banner = text side (title, up to 3 lines, accent CTA pill) + art side (tilted icon tile, dashed ring, dots, small chip).
  Tones only from tokens: `navy` (same as the balance card), `warm` (star/photo tints), `rose` (animation/document), `mint` (text/audio).
- Every text is an i18n key (`bn_<k>_t/_d/_cta/_chip`), so banners re-render in the new language. Auto-advance every 5 s only while
  Home is visible; off with reduced motion; dots under the track. Never name other platforms (e.g. OnlyFans) in any user-facing text.
