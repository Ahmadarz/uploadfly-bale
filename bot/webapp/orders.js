// UploadFly Mini App — سفارش‌های کالای فیزیکی (فروشنده): فهرست، کپی نشانی، ثبت ارسال با کد رهگیری، لغو،
// و هزینه‌ی ارسال. بعد از app.js و creator.js بار می‌شود و از همان کمک‌تابع‌ها (api, t, $, tap, toast, ...) استفاده می‌کند.

const orders = { tab: "waiting", items: [], current: null };

// ردیف «سفارش‌های کالا» در خانه‌ی فروشنده (app.js: renderHome)
orders.renderRow = function renderRow() {
  const shop = me.shop;
  if (!shop) return;
  const n = shop.orders_waiting || 0;
  $("cr-orders-n").textContent = n || "";
  $("cr-orders-n").classList.toggle("alert", n > 0);
  $("cr-orders-hint").textContent = n ? t("ord_row_waiting", n) : shop.physical || shop.orders_total ? t("ord_row_none") : t("ord_row_intro");
  $("cr-orders").onclick = () => { tap(); orders.open(); };
};

orders.open = async function open() {
  openSubPage("page-orders");
  document.querySelectorAll("#ord-tabs .tab").forEach((b) => {
    b.onclick = () => { if (orders.tab !== b.dataset.tab) { tap(); orders.tab = b.dataset.tab; orders.load(); } };
  });
  $("ord-fee-save").onclick = orders.saveFee;
  await orders.load();
};

orders.load = async function load() {
  document.querySelectorAll("#ord-tabs .tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === orders.tab));
  let d;
  try { d = await api(`/api/orders?tab=${orders.tab}`); } catch (e) { return toast(errMsg(e.code)); }
  orders.items = d.items;
  for (const k of ["waiting", "shipped", "canceled"]) $(`ordc-${k}`).textContent = d.counts[k] || "";
  if (document.activeElement !== $("ord-fee")) $("ord-fee").value = d.shipping_fee || "";
  if (me.shop) me.shop.orders_waiting = d.counts.waiting;
  orders.render();
};

const orderDate = (iso) => (iso ? new Intl.DateTimeFormat(LANGS[lang].locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(iso)) : "");
// نشانی به شکل متن ساده، آماده‌ی چسباندن روی بسته یا در سامانه‌ی پست
const addressText = (o) => [o.name, o.phone, o.address, o.postal ? `${t("ord_postal")}: ${o.postal}` : ""].filter(Boolean).join("\n");

orders.render = function render() {
  const list = $("ord-list"), items = orders.items;
  $("ord-empty").classList.toggle("hidden", items.length > 0);
  $("ord-empty-text").textContent = t(`ord_empty_${orders.tab}`);
  list.innerHTML = items.map((o) => `
    <article class="card ord-card" data-id="${o.id}">
      <div class="ord-top">
        <b><bdi class="num">#${o.id}</bdi> · ${esc(o.title)}</b>
        <span class="ord-total">${toman(o.amount)}</span>
      </div>
      <small class="muted">${esc(orderDate(o.status === "shipped" ? o.shipped_at : o.paid_at))}${o.shipping_fee ? ` · ${t("ord_fee_part", o.shipping_fee)}` : ""}</small>
      <dl class="ord-addr">
        ${o.address ? `<div><dt>${t("ord_name")}</dt><dd>${esc(o.name)}</dd></div>
        <div><dt>${t("ord_phone")}</dt><dd><bdi class="num">${esc(o.phone)}</bdi></dd></div>
        <div><dt>${t("ord_address")}</dt><dd>${esc(o.address)}</dd></div>
        <div><dt>${t("ord_postal")}</dt><dd><bdi class="num">${esc(o.postal || "—")}</bdi></dd></div>` : `<div><dd class="muted">${t("ord_address_gone")}</dd></div>`}
        ${o.status === "shipped" ? `<div><dt>${t("ord_tracking")}</dt><dd><bdi class="num">${esc(o.tracking || t("ord_no_tracking"))}</bdi></dd></div>` : ""}
      </dl>
      <div class="btn-row">
        ${o.address ? `<button class="btn-soft js-copy"><svg><use href="#i-link"/></svg><span>${t("ord_copy")}</span></button>` : ""}
        ${o.status === "paid" ? `<button class="btn-accent js-ship"><svg><use href="#i-box"/></svg><span>${t("ord_ship")}</span></button>` : ""}
      </div>
      ${o.status === "paid" ? `<button class="text-btn danger js-cancel">${t("ord_cancel")}</button>` : ""}
    </article>`).join("");
  list.querySelectorAll(".ord-card").forEach((card) => {
    const o = items.find((x) => x.id === Number(card.dataset.id));
    const copy = card.querySelector(".js-copy");
    if (copy) copy.onclick = () => copyText(addressText(o), card.querySelector(".ord-addr"));
    const ship = card.querySelector(".js-ship"), cancel = card.querySelector(".js-cancel");
    if (ship) ship.onclick = () => { tap(); orders.openShip(o); };
    if (cancel) cancel.onclick = () => { tap(); orders.cancel(o); };
  });
};

// برگه‌ی «ارسال کردم»: کد رهگیری (اختیاری)
orders.openShip = function openShip(o) {
  orders.current = o;
  $("ship-title").textContent = t("ord_ship_title", o.id);
  $("ship-code").value = "";
  $("ship-send").onclick = () => orders.ship($("ship-code").value.trim());
  $("ship-none").onclick = () => orders.ship("");
  openSmallSheet("ship-sheet");
};

orders.ship = async function ship(code) {
  const o = orders.current; if (!o) return;
  if (code && (code.length < 4 || code.length > 64)) { haptic("error"); return toast(errMsg("bad_tracking")); }
  try {
    await api(`/api/orders/${o.id}/ship`, { method: "POST", body: JSON.stringify({ tracking: code || null }) });
    haptic("success"); toast(t("ord_shipped_ok"));
    closeLangSheet(); tg.BackButton.show();   // هنوز در زیرصفحه‌ی سفارش‌ها هستیم
    orders.current = null;
    await orders.load();
  } catch (e) { haptic("error"); toast(errMsg(e.code)); }
};

orders.cancel = function cancel(o) {
  tg.showConfirm(t("ord_cancel_confirm", { id: o.id, total: o.amount }), async (yes) => {
    if (!yes) return;
    try {
      await api(`/api/orders/${o.id}/cancel`, { method: "POST" });
      haptic("success"); toast(t("ord_canceled_ok"));
      await orders.load();
    } catch (e) { haptic("error"); toast(errMsg(e.code)); }
  });
};

orders.saveFee = async function saveFee() {
  tap();
  const fee = Number($("ord-fee").value || 0);
  if (!Number.isInteger(fee) || fee < 0) { haptic("error"); return toast(errMsg("bad_shipping")); }
  try {
    await api("/api/creator", { method: "PATCH", body: JSON.stringify({ shipping_fee: fee }) });
    if (me.shop) me.shop.shipping_fee = fee;
    haptic("success"); toast(t("saved"));
  } catch (e) { haptic("error"); toast(errMsg(e.code)); }
};
