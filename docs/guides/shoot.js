// Screenshots for the two guides, from the running demo site (http://127.0.0.1:8000).
// node shoot.js [only-prefix]
const { chromium, devices } = require('playwright');
const L = require('./lib');
const { BASE, annotate, shot } = L;
const only = process.argv[2] || '';
// Tracking code of the demo application that is with the commission (it changes with every seed_demo).
const TRACK = process.env.TRACK_CODE || require('child_process').execFileSync(
  __dirname + '/../../.venv/bin/python', [__dirname + '/../../manage.py', 'shell', '-c',
    "from membership.models import MembershipApplication as A; print(A.objects.get(status='commission').tracking_code)"],
).toString().trim().split('\n').pop();
const want = n => !only || n.startsWith(only) || only.split(',').some(o => n.startsWith(o));

async function step(name, fn) {
  if (!want(name)) return;
  try { await fn(); } catch (e) { console.log('FAIL', name, e.message.split('\n')[0]); }
}

(async () => {
  const browser = await chromium.launch();
  const desk = await browser.newContext({ viewport: { width: 1280, height: 820 }, deviceScaleFactor: 1.5, locale: 'fa-IR' });
  const phoneCtx = await browser.newContext({ ...devices['iPhone 13'], locale: 'fa-IR' });
  const p = await desk.newPage();
  p.on('console', m => { if (m.text().startsWith('MISSING')) console.log('  ', m.text()); });
  const go = async (u) => { await p.goto(BASE + u); await p.waitForLoadState('networkidle'); };

  // ---------------- public site ----------------
  await step('u01', async () => {
    await go('/fa/');
    await annotate(p, [{ sel: '.main-nav', n: 1 }, { sel: '.panel-link', n: 2 }, { sel: '.lang-switch', n: 3, side: 'left' }]);
    await shot(p, 'u01-home');
  });
  await step('u02', async () => {
    const q = await phoneCtx.newPage(); await q.goto(BASE + '/fa/'); await q.waitForLoadState('networkidle');
    await q.screenshot({ path: __dirname + '/shots/u02-home-phone.jpg', type: 'jpeg', quality: 84 }); console.log('shot u02'); await q.close();
  });
  await step('u03', async () => {
    await go('/fa/shop/');
    await annotate(p, [{ sel: '.filters select, .filters__field select', n: 1 }, { sel: '.filters__field:nth-of-type(2) select', n: 2 }]);
    await shot(p, 'u03-shop', { from: 'main h1', h: 760 });
  });
  let productUrl = null;
  await step('u04', async () => {
    await go('/fa/shop/');
    productUrl = await p.locator('.grid--products a').first().getAttribute('href');
    await go(productUrl);
    await shot(p, 'u04-product');
  });
  // order 1: online payment
  await step('u05', async () => {
    await go('/fa/shop/');
    const links = await p.locator('.grid--products a').evaluateAll(as => [...new Set(as.map(a => a.getAttribute('href')))]);
    for (const href of links.slice(0, 2)) {
      await go(href);
      await p.locator('form button[type=submit]:has-text("سبد")').first().click();
      await p.waitForLoadState('networkidle');
    }
    await go('/fa/shop/cart/');
    await shot(p, 'u05a-cart', { from: 'main h1', h: 760 });
    await go('/fa/shop/checkout/');
    const fill = async (name, v) => { const f = p.locator(`[name="${name}"]`); if (await f.count()) await f.first().fill(v); };
    await fill('buyer_name', 'مریم احمدی'); await fill('phone', '09121234567'); await fill('email', 'buyer@example.com');
    await fill('city', 'تهران'); await fill('address', 'خیابان نمونه، کوچهٔ یک، پلاک ۱۰'); await fill('postal_code', '1234567890');
    const prov = p.locator('select[name="province"]'); if (await prov.count()) await prov.selectOption({ index: 8 });
    await p.check('[name=accept_terms]');
    await shot(p, 'u05-checkout', { from: 'main h1', h: 900 });
    await p.locator('main form button[type=submit]').last().click();
    await p.waitForLoadState('networkidle');
    await shot(p, 'u06-order', { from: 'main h1', h: 760 });
    console.log('order url', p.url());
    // pay online with the test gateway
    const pay = p.locator('button:has-text("پرداخت آنلاین"), a:has-text("پرداخت آنلاین")').first();
    if (await pay.count()) {
      await pay.click(); await p.waitForLoadState('networkidle');
      const ok = p.locator('button:has-text("موفق"), button:has-text("پرداخت")').first();
      await ok.click(); await p.waitForLoadState('networkidle');
    }
  });
  // order 2: bank transfer receipt
  await step('u06b', async () => {
    await go('/fa/shop/');
    const links = await p.locator('.grid--products a').evaluateAll(as => [...new Set(as.map(a => a.getAttribute('href')))]);
    await go(links[2]);
    await p.locator('form button[type=submit]:has-text("سبد")').first().click(); await p.waitForLoadState('networkidle');
    await go('/fa/shop/checkout/');
    const fill = async (name, v) => { const f = p.locator(`[name="${name}"]`); if (await f.count()) await f.first().fill(v); };
    await fill('buyer_name', 'علی رضایی'); await fill('phone', '09351234567'); await fill('email', 'buyer2@example.com');
    await fill('city', 'شیراز'); await fill('address', 'خیابان نمونه، پلاک ۵'); await fill('postal_code', '7134567890');
    const prov = p.locator('select[name="province"]'); if (await prov.count()) await prov.selectOption({ index: 17 });
    await p.check('[name=accept_terms]');
    await p.locator('main form button[type=submit]').last().click(); await p.waitForLoadState('networkidle');
    console.log('  after checkout', p.url(), await p.evaluate(() => [...document.querySelectorAll('.errorlist, .field-error, [class*=error]')].map(e => e.textContent.trim()).join(' | ')));
    const t = p.locator('summary:has-text("واریز کردم"), button:has-text("واریز کردم")').first();
    if (await t.count()) await t.click();
    const ref = p.locator('input[name="reference"]'); if (await ref.count()) await ref.fill('۴۵۶۷۸۹');
    const send = p.locator('form:has(input[name="reference"]) button[type=submit]'); if (await send.count()) { await send.click(); await p.waitForLoadState('networkidle'); }
  });
  await step('u07', async () => { await go('/fa/shop/orders/'); await shot(p, 'u07-track'); });
  await step('u08', async () => {
    await go('/en/wholesale/');
    await p.fill('[name=qty_1]', '200'); await p.fill('[name=qty_4]', '50');
    await shot(p, 'u08-wholesale');
    const fill = async (name, v) => { const f = p.locator(`[name="${name}"]`); if (await f.count()) await f.first().fill(v); };
    await fill('company', 'Green Bazaar GmbH'); await fill('contact_name', 'Anna Weber'); await fill('email', 'anna@example.com');
    await fill('country', 'Germany'); await fill('city', 'Berlin');
    const bt = p.locator('select[name="buyer_type"]'); if (await bt.count()) await bt.selectOption({ index: 1 });
    await p.waitForTimeout(5000);
    await p.locator('main form button[type=submit]').last().click(); await p.waitForLoadState('networkidle');
    console.log('  after wholesale', p.url(), await p.evaluate(() => [...document.querySelectorAll('.errorlist, .field-error, [class*=error]')].map(e => e.textContent.trim()).join(' | ')));
  });
  await step('u09', async () => {
    await go('/fa/complaint/');
    await shot(p, 'u09-complaint');
  });
  await step('u10', async () => { await go('/fa/membership/apply/producer/'); await shot(p, 'u10-apply'); });
  await step('u11', async () => {
    await go('/fa/membership/track/');
    await p.fill('input[name="code"], input[name="tracking_code"]', TRACK).catch(() => {});
    await p.fill('input[name="email"]', 'applicant@example.com').catch(() => {});
    await p.locator('main form button[type=submit]').first().click(); await p.waitForLoadState('networkidle');
    await shot(p, 'u11-track');
  });
  await step('u12', async () => {   // contact form message, for the admin «پیام‌های فرم‌ها» shot
    await go('/fa/contact/');
    const f = p.locator('main form');
    const inputs = f.locator('input[type=text]:not([name=website]), input[type=email], textarea');
    const n = await inputs.count();
    for (let i = 0; i < n; i++) {
      const el = inputs.nth(i); const type = await el.getAttribute('type');
      await el.fill(type === 'email' ? 'reza@example.com' : (await el.evaluate(e => e.tagName)) === 'TEXTAREA' ? 'سلام، برای همکاری در نمایشگاه بهار با شما تماس می‌گیرم.' : 'رضا محمدی');
    }
    await p.waitForTimeout(4000);
    await f.locator('button[type=submit]').click(); await p.waitForLoadState('networkidle');
    console.log('  after contact', p.url());
  });

  // ---------------- member panel ----------------
  await step('p01', async () => { await p.context().clearCookies(); await go('/fa/panel/login/'); await shot(p, 'p01-login'); });
  await step('p02', async () => { await go('/fa/panel/login/sms/'); await shot(p, 'p02-sms'); });
  await L.memberLogin(p);
  await step('p03', async () => {
    await go('/fa/panel/');
    await annotate(p, [{ text: 'پیشخوان', within: 'nav a, .tabs a, a', n: 1 }, { sel: '.member-card, .panel-card, .card', n: 2 }]);
    await shot(p, 'p03-dashboard', { full: true });
  });
  await step('p03b', async () => {
    // the two folds of the member-panel menu, «بیشتر» open
    await go('/fa/panel/1/orders/');
    await p.evaluate(() => { const d = document.querySelector('.panel-nav__more:not(.panel-nav__account)'); if (d) d.open = true; });
    await annotate(p, [{ sel: '.panel-nav__more:not(.panel-nav__account) summary', n: 1 }, { sel: '.panel-nav__account summary', n: 2, side: 'left' }]);
    await shot(p, 'p03b-menu', { from: 'main h1', h: 520 });
  });
  await step('p04', async () => { await go('/fa/panel/1/profile/'); await shot(p, 'p04-profile'); });
  await step('p05', async () => { await go('/fa/panel/1/products/'); await shot(p, 'p05-products', { from: 'main h1', h: 760 }); });
  await step('p06', async () => { await go('/fa/panel/1/products/new/'); await shot(p, 'p06-product-form'); });
  await step('p07', async () => { await go('/fa/panel/1/selling/'); await shot(p, 'p07-selling', { from: 'main h1', h: 900 }); });
  await step('p08', async () => { await go('/fa/panel/1/orders/?f=all'); await shot(p, 'p08-orders', { from: 'main h1', h: 760 }); });
  await step('p09', async () => {
    await go('/fa/panel/1/orders/?f=all');
    const a = p.locator('main a[href*="/orders/"]').filter({ hasNotText: 'همه' });
    const href = await a.first().getAttribute('href'); await go(href); await shot(p, 'p09-order', { from: 'main h1', h: 900 });
  });
  await step('p10', async () => {
    await go('/fa/panel/1/wholesale/');
    const a = p.locator('a[href*="/panel/1/wholesale/"]').filter({ hasText: 'پاسخ' }); if (await a.count()) { await go(await a.first().getAttribute('href')); }
    await shot(p, 'p10-wholesale', { from: 'main h1', h: 760 });
  });
  await step('p11', async () => { await go('/fa/panel/1/membership/'); await shot(p, 'p11-membership', { from: 'main h1', h: 760 }); });
  await step('p12', async () => {
    await go('/fa/panel/1/assembly/');
    const a = p.locator('main a[href*="/assembly/"]'); if (await a.count()) await go(await a.first().getAttribute('href'));
    await shot(p, 'p12-assembly', { from: 'main h1', h: 900 });
  });
  await step('p13', async () => {   // a complaint from the panel, for the admin shot
    await go('/fa/panel/1/complaints/');
    const f = p.locator('main form:has(textarea)');
    await f.locator('[name=subject_of_complaint]').fill('فروشندهٔ نمونه در نمایشگاه پاییز');
    await f.locator('[name=category]').selectOption({ index: 3 });
    await f.locator('[name=description]').fill('در نمایشگاه پاییز، محصولی با نام یکی از اعضا فروخته می‌شد که ساخت آن عضو نبود.');
    await f.locator('button[type=submit]').click(); await p.waitForLoadState('networkidle');
    await shot(p, 'p13-complaints', { from: 'main h1', h: 760 });
  });

  // ---------------- admin ----------------
  await step('a01', async () => { await p.context().clearCookies(); await go('/admin/login/'); await shot(p, 'a01-login'); });
  await L.adminLogin(p, 'demo-admin');
  await step('a02', async () => {
    await go('/admin/');
    await p.setViewportSize({ width: 1280, height: 1100 });
    await annotate(p, [{ sel: '.sidebar-main-menu, nav[aria-label] ul', n: 1, side: 'left', pad: 2, inSidebar: true }, { sel: '#wagtail-sidebar form, aside form', n: 2, side: 'left', pad: 2, inSidebar: true }, { sel: '.ft-pending', n: 3 }, { sel: '.ft-shortcuts__grid', n: 4 }]);
    await shot(p, 'a02-dashboard');
    await p.setViewportSize({ width: 1280, height: 820 });
  });
  await step('a04', async () => {
    const id = await p.evaluate(async () => { const r = await fetch('/admin/api/main/pages/?slug=fa&fields=_,id'); const j = await r.json(); return j.items[0].id; });
    await go(`/admin/pages/${id}/`);
    await shot(p, 'a04-pages', { main: true });
  });
  await step('a05', async () => {
    const id = await p.evaluate(async () => { const r = await fetch('/admin/api/main/pages/?slug=about&fields=_,id&locale=fa'); const j = await r.json(); return j.items[0].id; });
    await go(`/admin/pages/${id}/edit/`);
    await annotate(p, [{ sel: '[role=tablist]', n: 1 }, { text: 'منتشرشده', within: 'button,a,span', n: 2, side: 'left' }, { sel: 'footer .w-dropdown-button, footer [type=submit]', n: 3 }]);
    await shot(p, 'a05-editor', { main: true });
  });
  await step('a06', async () => {
    const id = await p.evaluate(async () => { const r = await fetch('/admin/api/main/pages/?slug=news&fields=_,id&locale=fa'); const j = await r.json(); return j.items[0].id; });
    await go(`/admin/pages/add/news/newspage/${id}/`);
    await shot(p, 'a06-news', { main: true });
  });
  await step('a07', async () => {
    await go('/admin/documents/multiple/add/');
    await annotate(p, [{ sel: 'select[name="collection"], #id_adddocument_collection', n: 1 }]);
    await shot(p, 'a07-documents', { main: true });
  });
  await step('a08', async () => {
    await go('/admin/forms/');
    const a = p.locator('main a[href*="/admin/forms/submissions/"]'); if (await a.count()) await go(await a.first().getAttribute('href'));
    await shot(p, 'a08-forms', { main: true });
  });
  await step('a09', async () => {
    await go('/admin/membership_applications/');
    await annotate(p, [{ sel: 'main form', n: 1 }, { text: 'خروجی اکسل', within: 'a', n: 2 }, { text: 'مهلت', within: 'th', n: 3 }]);
    await shot(p, 'a09-applications', { main: true });
  });
  await step('a10', async () => {
    await go('/admin/membership_applications/1/');
    await annotate(p, [{ text: 'وضعیت:', within: 'p,li,div,dd,dt,span', n: 1 }, { text: 'اقدام‌های شما', within: 'h2,h3', n: 2 }, { text: 'مشخصات متقاضی', within: 'h2,h3', n: 3 }]);
    await shot(p, 'a10-application', { main: true, full: true });
  });
  await step('a11', async () => { await go('/admin/membership_applications/2/'); await shot(p, 'a11-commission', { main: true }); });
  await step('a12', async () => { await go('/admin/snippets/membership/applicationquestion/'); await shot(p, 'a12-questions', { main: true }); });
  await step('a13', async () => { await go('/admin/snippets/members/member/edit/1/'); await shot(p, 'a13-member', { main: true }); });
  await step('a14', async () => { await go('/admin/standing/'); await shot(p, 'a14-standing', { main: true }); });
  await step('a15', async () => {
    await go('/admin/standing/');
    const a = p.locator('main a:has-text("ارموز")'); await go(await a.first().getAttribute('href'));
    await shot(p, 'a15-standing-member', { main: true, full: true });
  });
  await step('a16', async () => { await go('/admin/snippets/products/product/'); await shot(p, 'a16-products', { main: true }); });
  await step('a17', async () => {
    await go('/admin/shop_orders/?f=all');
    await annotate(p, [{ text: 'فروش پرداخت‌شده', within: 'p,div,li,span', n: 1 }, { sel: 'main form', n: 2 }, { text: 'گزارش ماهانه', within: 'a', n: 3 }]);
    await shot(p, 'a17-orders', { main: true });
  });
  await step('a18', async () => {
    await go('/admin/shop_orders/?f=all');
    const a = p.locator('main table a[href*="/admin/shop_orders/"]'); await go(await a.first().getAttribute('href'));
    await shot(p, 'a18-order', { main: true, full: true });
  });
  await step('a19', async () => {
    await go('/admin/wholesale_inquiries/');
    const a = p.locator('table a[href*="/admin/wholesale_inquiries/edit/"]'); if (await a.count()) await go(await a.first().getAttribute('href'));
    await shot(p, 'a19-wholesale', { main: true });
  });
  await step('a20', async () => {
    await go('/admin/complaints/');
    const a = p.locator('table a[href*="/admin/complaints/edit/"]'); if (await a.count()) await go(await a.first().getAttribute('href'));
    await shot(p, 'a20-complaint', { main: true });
  });
  await step('a21', async () => {
    await go('/admin/assembly_control/');
    const a = p.locator('main a[href*="/admin/assembly_control/"]').filter({ hasNotText: 'فراخواندن' }); if (await a.count()) await go(await a.first().getAttribute('href'));
    await shot(p, 'a21-assembly', { main: true, full: true });
  });
  await step('a22', async () => { await go('/admin/settings/core/sitesettings/'); await shot(p, 'a22-settings', { main: true }); });
  await step('a23', async () => { await go('/admin/settings/core/membershipsettings/'); await shot(p, 'a23-membership-settings', { main: true }); });
  await step('a24', async () => {
    await go('/admin/users/new/');
    const tab = p.locator('[role=tab]:has-text("نقش")'); if (await tab.count()) await tab.first().click();
    await shot(p, 'a24-user', { main: true });
  });
  await step('a03', async () => {
    const q = await phoneCtx.newPage(); await L.adminLogin(q, 'demo-secretariat'); await q.goto(BASE + '/admin/'); await q.waitForLoadState('networkidle');
    await q.screenshot({ path: __dirname + '/shots/a03-dashboard-phone.jpg', type: 'jpeg', quality: 84 }); console.log('shot a03'); await q.close();
  });
  // ---------------- phone versions for the user guide ----------------
  await step('ph', async () => {
    await phoneCtx.clearCookies();  // the secretariat phone shot above signed in to the admin
    const q = await phoneCtx.newPage();
    const pshot = async (u, name, prep) => { await q.goto(BASE + u); await q.waitForLoadState('networkidle'); if (prep) await prep(q);
      await q.waitForTimeout(250); await q.screenshot({ path: __dirname + '/shots/' + name + '.jpg', type: 'jpeg', quality: 82 }); console.log('shot', name); };
    const scrollTo = sel => async (q) => { await q.evaluate(sel => { const e = document.querySelector(sel); if (e) window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 70); }, sel); };
    await q.goto(BASE + '/fa/shop/'); const prod = await q.locator('.grid--products a').first().getAttribute('href');
    await pshot(prod, 'u04p-product');
    await pshot('/fa/shop/orders/', 'u07p-track', scrollTo('main form'));
    await pshot('/en/wholesale/', 'u08p-wholesale', async (q) => { await q.fill('[name=qty_1]', '200'); await scrollTo('main form')(q); });
    await pshot('/fa/complaint/', 'u09p-complaint', scrollTo('main form'));
    await pshot('/fa/membership/apply/producer/', 'u10p-apply', scrollTo('main form'));
    await pshot('/fa/membership/track/', 'u11p-track', async (q) => {
      await q.fill('input[name="code"], input[name="tracking_code"]', TRACK).catch(() => {});
      await q.fill('input[name="email"]', 'applicant@example.com').catch(() => {});
      await q.locator('main form button[type=submit]').first().click(); await q.waitForLoadState('networkidle'); await scrollTo('main h1')(q); });
    await pshot('/fa/panel/login/', 'p01p-login', scrollTo('main h1'));
    await pshot('/fa/panel/login/sms/', 'p02p-sms', scrollTo('main h1'));
    await L.memberLogin(q);
    await pshot('/fa/panel/1/profile/', 'p04p-profile', scrollTo('main form'));
    await pshot('/fa/panel/1/products/new/', 'p06p-product-form', scrollTo('main form'));
    await pshot('/fa/panel/', 'p03p-dashboard', scrollTo('main h1'));
    await q.close();
  });
  await browser.close();
})();
