// UploadFly Mini App — صفحه‌ی سازنده: ابزار سازنده در خانه، تنظیمات، فن‌ها، کشف سازنده‌ها،
// انعام، لایک، دوره‌ی آزمایشی و بسته‌ی چندماهه، زمان‌بندی پست و «خبر به فن‌ها». بعد از app.js بار می‌شود و از
// همان کمک‌تابع‌ها (api, t, $, tap, toast, openSubPage, ...) استفاده می‌کند. app.js در چند نقطه creator.* را صدا می‌زند.

const creator = {
  data: null,           // /api/creator
  explore: { q: "", cat: null, timer: null, items: [] },
  tipFor: null,         // انعام روی یک پست (content_id) یا null = خود سازنده
};

// ---------------- خانه‌ی سازنده: کارت «ابزار سازنده» ----------------
creator.renderTools = async function renderTools() {
  if (!me.shop) return;
  $("cr-fans").onclick = () => { tap(); creator.openFans(); };
  $("cr-settings").onclick = () => { tap(); creator.openSettings(); };
  $("cr-invite").onclick = () => { tap(); creator.openSettings(true); };
  $("cr-broadcast").onclick = () => { tap(); openTelegram(`https://t.me/${me.shop.bot}?start=broadcast`); };
  try { creator.data = await api("/api/creator"); } catch (e) { return; }
  const d = creator.data;
  $("cr-fans-n").textContent = d.followers || "";
  $("cr-invite-n").textContent = d.referral.shops ? t("cr_invite_n", d.referral.shops) : "";
  $("cr-broadcast-left").textContent = t("cr_broadcast_left", d.broadcasts_left);
};

// ---------------- تنظیمات سازنده ----------------
creator.openSettings = async function openSettings(scrollToInvite = false) {
  openSubPage("page-creator");
  try { creator.data = await api("/api/creator"); } catch (e) { return toast(errMsg(e.code)); }
  creator.fillSettings();
  if (scrollToInvite) $("cr-ref-link").scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "center" });
};

creator.fillSettings = function fillSettings() {
  const d = creator.data;
  $("cr-bio").value = d.bio; $("cr-welcome").value = d.welcome;
  $("cr-bio-count").textContent = `${d.bio.length}/${d.bio_max}`;
  $("cr-listed").checked = d.listed; $("cr-watermark").checked = d.watermark;
  $("cr-cats").innerHTML = d.categories.map((c) =>
    `<button class="chip ${c === d.category ? "active" : ""}" data-c="${c}">${t("ccats")[c] || c}</button>`).join("");
  $("cr-cats").querySelectorAll(".chip").forEach((b) => {
    b.onclick = () => { tap(); creator.save({ category: d.category === b.dataset.c ? null : b.dataset.c }); };
  });
  document.querySelectorAll("#cr-dm button").forEach((b) => {
    b.classList.toggle("active", b.dataset.v === d.dm_mode);
    b.onclick = () => { if (b.dataset.v !== creator.data.dm_mode) { tap(); creator.save({ dm_mode: b.dataset.v }); } };
  });
  $("cr-listed").onchange = () => creator.save({ listed: $("cr-listed").checked });
  $("cr-watermark").onchange = () => creator.save({ watermark: $("cr-watermark").checked });
  // متن‌ها: بعد از تمام شدن تایپ ذخیره می‌شوند (نه با هر حرف)
  $("cr-bio").oninput = () => { $("cr-bio-count").textContent = `${$("cr-bio").value.length}/${d.bio_max}`; };
  $("cr-bio").onchange = () => creator.save({ bio: $("cr-bio").value.trim() });
  $("cr-welcome").onchange = () => creator.save({ welcome: $("cr-welcome").value.trim() });
  const ref = d.referral;
  $("cr-ref-link").textContent = ref.link;
  $("cr-ref-stats").textContent = t("cr_invite_stats", { n: ref.invited, s: ref.shops });
  $("cr-ref-copy").onclick = () => copyText(ref.link, $("cr-ref-link"));
  $("cr-ref-share").onclick = () => { tap(); openTelegram(`https://t.me/share/url?url=${encodeURIComponent(ref.link)}&text=${encodeURIComponent(t("cr_invite_share"))}`); };
};

creator.save = async function save(patch) {
  try {
    creator.data = await api("/api/creator", { method: "PATCH", body: JSON.stringify(patch) });
    haptic("success"); toast(t("saved")); creator.fillSettings();
  } catch (e) { haptic("error"); toast(errMsg(e.code)); creator.fillSettings(); }
};

// ---------------- فن‌ها ----------------
creator.openFans = async function openFans() {
  openSubPage("page-fans");
  $("fans-broadcast").onclick = () => { tap(); openTelegram(`https://t.me/${me.shop.bot}?start=broadcast`); };
  let d;
  try { d = await api("/api/fans"); } catch (e) { return toast(errMsg(e.code)); }
  const c = d.counts;
  $("fans-counts").innerHTML = [["all", c.all], ["subscribers", c.subscribers], ["buyers", c.buyers], ["expired", c.expired]]
    .map(([k, n]) => `<div><b>${n}</b><span>${t("fans_seg_" + k)}</span></div>`).join("");
  $("fans-empty").classList.toggle("hidden", d.fans.length > 0);
  $("fans-list").classList.toggle("hidden", !d.fans.length);
  const tag = { subscriber: ["sub", t("fan_sub")], expired: ["expired", t("fan_expired")], buyer: ["", t("fan_buyer")] };
  $("fans-list").innerHTML = d.fans.map((f) => {
    const [cls, label] = tag[f.status];
    const name = t("fan_alias", f.number);   // ناشناس: فقط شماره‌ی فن
    return `<div class="row">
      <span class="avatar sm num">${f.number}</span>
      <span class="purchase-meta"><b>${esc(name)}${f.blocked ? " 🚫" : ""}</b>
        <small>${f.last ? shortDate(f.last) : ""}</small>
        <span class="tag ${cls}">${label}</span></span>
      <span class="fan-amount">${f.spent} ★</span>
    </div>`;
  }).join("");
};

// ---------------- کشف سازنده‌ها ----------------
creator.openExplore = async function openExplore() {
  tap();
  creator.exploreFrom = document.querySelector(".page.active")?.id || "page-home";
  openSubPage("page-explore");
  $("ex-q").value = creator.explore.q;
  $("ex-q").oninput = (e) => {
    clearTimeout(creator.explore.timer);
    creator.explore.timer = setTimeout(() => { creator.explore.q = e.target.value.trim(); creator.loadExplore(); }, 300);
  };
  await creator.loadExplore();
};

creator.loadExplore = async function loadExplore() {
  const { q, cat } = creator.explore;
  let d;
  try { d = await api(`/api/explore?q=${encodeURIComponent(q)}${cat ? `&cat=${cat}` : ""}`); }
  catch (e) { return toast(errMsg(e.code)); }
  creator.explore.items = d.items;
  $("ex-cats").innerHTML = [null, ...d.categories].map((c) =>
    `<button class="chip ${c === cat ? "active" : ""}" data-c="${c ?? ""}">${c ? t("ccats")[c] || c : t("all_cats")}</button>`).join("");
  $("ex-cats").querySelectorAll(".chip").forEach((b) => {
    b.onclick = () => { tap(); creator.explore.cat = b.dataset.c || null; creator.loadExplore(); };
  });
  $("ex-empty").classList.toggle("hidden", d.items.length > 0);
  $("ex-list").innerHTML = d.items.map((s, i) => `
    <button class="card ex-card" data-bot="${s.bot_id}" style="animation-delay:${Math.min(i, 8) * 40}ms">
      <div class="ex-cover"></div>
      <div class="ex-body">
        <span class="avatar">${esc((s.name || s.bot).trim().charAt(0).toUpperCase())}</span>
        <span class="ex-text"><b>${esc(s.name)}</b>
          <small>${s.category ? esc(t("ccats")[s.category] || s.category) + " · " : ""}${t("ex_posts", s.posts)}${s.members ? " · " + t("ex_members", s.members) : ""}${s.rating ? ` · ★ ${s.rating.avg}` : ""}</small>
          ${s.bio ? `<p>${esc(s.bio)}</p>` : ""}</span>
      </div>
    </button>`).join("");
  $("ex-list").querySelectorAll(".ex-card").forEach((card) => {
    const s = d.items.find((x) => String(x.bot_id) === card.dataset.bot);
    if (s.cover) imageUrl(s.cover).then((u) => { card.querySelector(".ex-cover").style.backgroundImage = `url(${u})`; }).catch(() => {});
    if (s.logo) paintAvatar(card.querySelector(".avatar"), s.logo, (s.name || s.bot).trim().charAt(0).toUpperCase());
    card.onclick = () => { tap(); subPage.current = null; creator.backToExplore = true; openStore(s.bot_id, true); };
  });
};

// ---------------- ویترین خریدار: معرفی، انعام، پیام، لایک، آزمایشی، بسته‌ها ----------------
creator.renderStore = function renderStore() {
  const { shop } = store.data, sc = store.data.showcase;
  if (!sc && shop.bio) { $("store-desc").classList.remove("hidden"); $("store-desc").textContent = shop.bio; }
  $("store-actions").classList.toggle("hidden", !!shop.is_owner || shop.suspended);
  $("store-tip").onclick = () => { tap(); creator.openTip(null); };
  $("store-message").classList.toggle("hidden", shop.dm_mode === "off");
  $("store-message").onclick = creator.startChat;

  // اشتراک ماهانه: دوره‌ی آزمایشی + بسته‌های چندماهه با تخفیف
  const showJoin = sc && !$("store-join-box").classList.contains("hidden");
  const trialOk = sc && sc.trial_available;
  $("store-trial").classList.toggle("hidden", !(showJoin && trialOk));
  if (trialOk) $("store-trial-text").textContent = t("trial_btn", sc.trial_days);
  $("store-trial").onclick = creator.startTrial;
  const bundles = (sc && sc.bundles) || [];
  $("store-bundles").classList.toggle("hidden", !(showJoin && bundles.length));
  $("store-bundles").innerHTML = bundles.map((b) => `
    <button class="bundle-opt" data-m="${b.months}"><span>${t("bundle_months", b.months)} ${b.off ? `<span class="off">−${b.off}%</span>` : ""}</span><b>${b.price} ★</b></button>`).join("");
  $("store-bundles").querySelectorAll(".bundle-opt").forEach((x) => { x.onclick = () => creator.joinBundle(Number(x.dataset.m)); });
  // عضو آزمایشی: دکمه‌ی «مشترک شو» تا قطع نشود
  const trialMember = sc && sc.is_member && sc.is_trial;
  $("store-subscribe").classList.toggle("hidden", !trialMember);
  if (trialMember) {
    $("store-member-note").textContent = t("trial_until", shortDay(sc.expires_at));
    $("store-subscribe").textContent = t("sc_join_monthly", sc.price);
    $("store-subscribe").onclick = () => joinShowcase();
  }

  // لایک روی پست‌های فید
  document.querySelectorAll("#store-items .post").forEach((card) => {
    const item = store.data.items.find((x) => x.id === Number(card.dataset.id));
    const foot = card.querySelector(".post-foot");
    if (!item || !foot || foot.querySelector(".like-btn")) return;
    foot.insertAdjacentHTML("afterbegin", creator.likeHtml(item));
    foot.querySelector(".like-btn").onclick = (e) => { e.stopPropagation(); creator.toggleLike(item); };
  });
};

// «پیام»: ربات سازنده در چت فن می‌نویسد «همین‌جا بنویس»؛ اگر Mini App از همان ربات باز شده، فقط بسته می‌شود
creator.startChat = async function startChat() {
  tap();
  const { shop } = store.data;
  try {
    const r = await api(`/api/store/${STORE}/dm`, { method: "POST", body: "{}" });
    haptic("success");
    if (VIA_BOT === String(STORE) && r.sent) { toast(t("dm_go_chat")); setTimeout(() => tg.close(), 700); }
    else openTelegram(r.chat);
  } catch (e) { haptic("error"); toast(errMsg(e.code)); }
};

creator.likeHtml = (item) =>
  `<span class="like-btn ${item.liked ? "on" : ""}" role="button" tabindex="0" aria-pressed="${!!item.liked}"><svg><use href="#i-heart"/></svg><b class="num">${item.likes || 0}</b></span>`;

creator.toggleLike = async function toggleLike(item) {
  tap();
  try {
    const r = await api(`/api/store/${STORE}/like/${item.id}`, { method: "POST", body: "{}" });
    item.liked = r.liked; item.likes = r.likes;
    if (r.liked) haptic("success");
    renderStore();
    if (store.current === item) creator.renderBuy(item);
  } catch (e) { toast(errMsg(e.code)); }
};

creator.renderBuy = function renderBuy(item) {
  const like = $("buy-like");
  like.classList.toggle("on", !!item.liked);
  $("buy-likes").textContent = item.likes || 0;
  like.onclick = () => creator.toggleLike(item);
  const canTip = (item.bought || item.unlocked) && !store.data.shop.is_owner && !store.data.shop.suspended;
  $("buy-tip").classList.toggle("hidden", !canTip);
  $("buy-tip").onclick = () => { tap(); creator.openTip(item.id); };
};

creator.startTrial = async function startTrial() {
  tap();
  try {
    await api(`/api/sc/${SC}/trial`, { method: "POST", body: "{}" });
    haptic("success"); toast(t("trial_started")); await reloadStore();
  } catch (e) { haptic("error"); toast(errMsg(e.code)); }
};

creator.joinBundle = async function joinBundle(months) {
  tap();
  try {
    const res = await api(`/api/sc/${SC}/join`, { method: "POST", body: JSON.stringify({ months }) });
    if (res.member) return reloadStore();
    tg.openInvoice(res.invoice, async (status) => {
      if (status !== "paid") return;
      haptic("success"); toast(t("sc_joined_toast"));
      for (let i = 0; i < 8; i++) {
        await reloadStore();
        if (store.data.showcase?.is_member && !store.data.showcase?.is_trial) break;
        await new Promise((r) => setTimeout(r, 1500));
      }
    });
  } catch (e) { haptic("error"); toast(errMsg(e.code)); }
};

// ---------------- انعام ----------------
creator.openTip = function openTip(contentId) {
  creator.tipFor = contentId;
  const presets = store.data.shop.tips || [10, 50, 100, 500];
  $("tip-amount").value = presets[1] || presets[0];
  const sync = () => {
    const v = Math.floor(Number($("tip-amount").value) || 0);
    $("tip-chips").querySelectorAll(".chip").forEach((c) => c.classList.toggle("active", Number(c.dataset.v) === v));
    $("tip-send").textContent = v > 0 ? t("tip_send", v) : t("tip_btn");
    $("tip-send").disabled = !(v >= 1 && v <= (store.data.shop.tip_max || 2500));
  };
  $("tip-chips").innerHTML = presets.map((v) => `<button class="chip" data-v="${v}">${v} ★</button>`).join("");
  $("tip-chips").querySelectorAll(".chip").forEach((c) => { c.onclick = () => { tap(); $("tip-amount").value = c.dataset.v; sync(); }; });
  $("tip-amount").oninput = sync;
  $("tip-send").onclick = creator.sendTip;
  sync();
  openSmallSheet("tip-sheet");
};

creator.sendTip = async function sendTip() {
  const amount = Math.floor(Number($("tip-amount").value) || 0);
  try {
    const res = await api(`/api/store/${STORE}/tip`, { method: "POST",
      body: JSON.stringify({ amount, ...(creator.tipFor ? { content_id: creator.tipFor } : {}) }) });
    closeLangSheet();
    tg.openInvoice(res.invoice, (status) => { if (status === "paid") { haptic("success"); toast(t("tip_thanks_toast")); } });
  } catch (e) { haptic("error"); toast(errMsg(e.code)); }
};

// ---------------- ۱۸+ ----------------
// خرید محتوای حساس: یک بار تأیید سن؛ بعد خرید دوباره امتحان می‌شود
creator.confirmAdult = function confirmAdult(retry) {
  tg.showConfirm(t("adult_confirm"), async (ok) => {
    if (!ok) return;
    try { await api(`/api/store/${STORE}/adult`, { method: "POST", body: "{}" }); me.adult_ok = true; retry(); }
    catch (e) { toast(errMsg(e.code)); }
  });
};

// ---------------- ویرایشگر پست: زمان‌بندی و «خبر به فن‌ها» ----------------
const toLocalInput = (iso) => {
  const d = new Date(iso), p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
};

creator.renderEditor = function renderEditor(p) {
  const draft = p.status === "draft";
  $("ed-schedule").classList.toggle("hidden", !draft);
  $("ed-schedule-at").value = p.publish_at ? toLocalInput(p.publish_at) : "";
  $("ed-schedule-at").min = toLocalInput(new Date(Date.now() + 5 * 60000).toISOString());
  $("ed-schedule-note").textContent = p.publish_at ? t("ed_scheduled_for", shortDay(p.publish_at) + " " + toLocalInput(p.publish_at).slice(11))
    : t("ed_schedule_hint");
  $("ed-schedule-btn").textContent = p.publish_at && !$("ed-schedule-at").value ? t("ed_schedule_cancel") : t("ed_schedule_btn");
  $("ed-schedule-btn").onclick = creator.schedule;
  $("ed-schedule-at").onchange = () => { $("ed-schedule-btn").textContent = t("ed_schedule_btn"); };
  $("ed-notify").classList.toggle("hidden", p.status !== "active");
  $("ed-notify").disabled = !!p.notified;
  $("ed-notify-text").textContent = p.notified ? t("ed_notified") : t("ed_notify");
  $("ed-notify").onclick = creator.notifyFans;
};

creator.schedule = async function schedule() {
  const p = state.current; if (!p) return;
  const value = $("ed-schedule-at").value;
  const v = editorValues();
  const body = value ? { publish_at: new Date(value).toISOString(), price: v.price, title: v.title, description: v.description,
                         in_store: v.in_store, showcases: v.showcases, sensitive: v.sensitive }
    : { publish_at: null };
  try {
    const updated = await api(`/api/products/${p.id}`, { method: "PATCH", body: JSON.stringify(body) });
    haptic("success"); toast(value ? t("ed_scheduled_toast") : t("saved"));
    state.current = updated; creator.renderEditor(updated); loadProducts().catch(() => {});
  } catch (e) { haptic("error"); toast(errMsg(e.code)); }
};

creator.notifyFans = function notifyFans() {
  const p = state.current; if (!p || p.notified) return;
  tg.showConfirm(t("ed_notify_confirm"), async (ok) => {
    if (!ok) return;
    try {
      const r = await api(`/api/products/${p.id}/notify`, { method: "POST", body: "{}" });
      p.notified = true; haptic("success"); toast(t("ed_notify_sent", r.sent)); creator.renderEditor(p);
    } catch (e) { haptic("error"); toast(errMsg(e.code)); }
  });
};

// ---------------- ویرایشگر ویترین: آزمایشی و بسته‌ها (فقط اشتراک ماهانه) ----------------
const TRIAL_CHOICES = [0, 3, 7, 14, 30];
const BUNDLE_MONTHS = [3, 6, 12];

creator.renderSceAccess = function renderSceAccess() {
  const monthly = scEd.access === "monthly";
  $("sce-monthly-box").classList.toggle("hidden", !monthly);
  if (!monthly) return;
  if (scEd.trial === undefined) scEd.trial = scEd.data.trial_days || 0;
  if (!scEd.bundles) scEd.bundles = { ...(scEd.data.bundles || {}) };
  $("sce-trial").innerHTML = TRIAL_CHOICES.map((d) =>
    `<button class="chip ${d === scEd.trial ? "active" : ""}" data-d="${d}">${d ? t("trial_days", d) : t("trial_none")}</button>`).join("");
  $("sce-trial").querySelectorAll(".chip").forEach((c) => { c.onclick = () => { tap(); scEd.trial = Number(c.dataset.d); creator.renderSceAccess(); }; });
  const price = Math.floor(Number($("sce-price").value) || 0);
  $("sce-bundles").innerHTML = BUNDLE_MONTHS.map((m) => {
    const off = scEd.bundles[m] ?? scEd.bundles[String(m)];
    const total = off === undefined || off === "" ? "" : Math.max(1, Math.round(price * m * (100 - off) / 100));
    return `<label>${t("bundle_months", m)}<input type="number" inputmode="numeric" min="0" max="50" data-m="${m}" value="${off ?? ""}" placeholder="—"><span>${total ? `${total} ★` : "&nbsp;"}</span></label>`;
  }).join("");
  $("sce-bundles").querySelectorAll("input").forEach((inp) => {
    inp.onchange = () => {
      const v = inp.value === "" ? undefined : Math.max(0, Math.min(50, Math.floor(Number(inp.value) || 0)));
      if (v === undefined) delete scEd.bundles[inp.dataset.m]; else scEd.bundles[inp.dataset.m] = v;
      creator.renderSceAccess();
    };
  });
};

creator.sceAccessBody = function sceAccessBody() {
  if (scEd.access !== "monthly") return {};
  const bundles = {};
  Object.entries(scEd.bundles || {}).forEach(([m, v]) => { if (v !== undefined && v !== "") bundles[String(m)] = Number(v); });
  return { trial_days: scEd.trial || 0, bundles };
};

// ---------------- کیف پول: درآمد به تفکیک ----------------
creator.renderEarnings = function renderEarnings(w) {
  const e = w.earnings; if (!e) return;
  for (const k of ["sales", "subs", "tips"]) {
    $(`we-${k}`).textContent = e[k];
    $(`we-${k}-m`).textContent = t("cr_earn_month", e.month[k]);
  }
};

// ---------------- بنرهای خانه (اسلایدر) ----------------
// متن هر بنر از i18n است؛ با عوض شدن زبان، renderHome دوباره صدا زده می‌شود و بنرها هم به زبان تازه ساخته می‌شوند.
// طرح: همان زبان «Soft files» — بنر اول سرمه‌ای مثل کارت موجودی، بقیه روشن با رنگ ملایم و آیکن رنگی.
const BANNERS = {
  seller: [
    { k: "sub", tone: "navy", icon: "i-calendar", go: () => openShowcaseEditor(null) },
    { k: "fans", tone: "warm", icon: "i-megaphone", go: () => openTelegram(`https://t.me/${me.shop.bot}?start=broadcast`) },
    { k: "bio", tone: "rose", icon: "i-instagram", go: () => openStory(null) },
  ],
  none: [
    { k: "explore", tone: "navy", icon: "i-compass", go: () => creator.openExplore() },
    { k: "money", tone: "warm", icon: "i-shield", go: () => openFaq() },
    { k: "free", tone: "mint", icon: "i-link", go: () => openTelegram(`https://t.me/${me.main_bot}`) },
  ],
};

creator.banner = { timer: null, index: 0 };

creator.renderBanners = function renderBanners() {
  const kind = me.shop ? "seller" : "none";
  const box = $(`banners-${kind}`);
  if (!box) return;
  const slides = BANNERS[kind];
  box.innerHTML = `<div class="banner-track" tabindex="0">${slides.map((b, i) => `
    <article class="banner tone-${b.tone}" aria-roledescription="slide" aria-label="${i + 1} / ${slides.length}">
      <div class="banner-text">
        <b>${esc(t(`bn_${b.k}_t`))}</b>
        <p>${esc(t(`bn_${b.k}_d`))}</p>
        <button class="banner-cta" data-i="${i}">${esc(t(`bn_${b.k}_cta`))}<svg><use href="#i-chev"/></svg></button>
      </div>
      <div class="banner-art" aria-hidden="true">
        <span class="ba-ring"></span><span class="ba-dot d1"></span><span class="ba-dot d2"></span>
        <span class="ba-icon"><svg><use href="#${b.icon}"/></svg></span>
        <span class="ba-chip">${esc(t(`bn_${b.k}_chip`))}</span>
      </div>
    </article>`).join("")}</div>
    <div class="banner-dots">${slides.map((_, i) => `<i data-i="${i}"></i>`).join("")}</div>`;
  const track = box.querySelector(".banner-track"), dots = [...box.querySelectorAll(".banner-dots i")];
  const dir = () => (LANGS[lang].dir === "rtl" ? -1 : 1);
  const mark = (i) => { creator.banner.index = i; dots.forEach((d, k) => d.classList.toggle("on", k === i)); };
  const go = (i) => {
    const n = (i + slides.length) % slides.length;
    track.scrollTo({ left: dir() * n * track.clientWidth, behavior: reducedMotion() ? "auto" : "smooth" });
    mark(n);
  };
  box.querySelectorAll(".banner-cta").forEach((b) => { b.onclick = () => { tap(); slides[Number(b.dataset.i)].go(); }; });
  dots.forEach((d) => { d.onclick = () => { tap(); go(Number(d.dataset.i)); restart(); }; });
  track.onscroll = () => {
    const i = Math.round(Math.abs(track.scrollLeft) / Math.max(1, track.clientWidth));
    if (i !== creator.banner.index) mark(i);
  };
  // خودکار هر ۵ ثانیه؛ فقط وقتی خانه دیده می‌شود. دست زدن کاربر زمان‌سنج را از نو شروع می‌کند
  const restart = () => {
    clearInterval(creator.banner.timer);
    if (reducedMotion()) return;
    creator.banner.timer = setInterval(() => {
      if (document.visibilityState !== "visible" || !$("page-home").classList.contains("active") || box.offsetParent === null) return;
      go(creator.banner.index + 1);
    }, 5000);
  };
  track.addEventListener("pointerdown", restart, { passive: true });
  track.addEventListener("touchstart", restart, { passive: true });
  mark(0); restart();
};
