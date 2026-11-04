// Helpers for guide screenshots: sign in, mark parts of a page with numbered gold discs, save as JPEG.
const BASE = 'http://127.0.0.1:8000';
const OUT = __dirname + '/shots/';

async function adminLogin(page, user) {
  await page.goto(BASE + '/admin/logout/').catch(() => {});
  await page.context().clearCookies();
  await page.goto(BASE + '/admin/login/');
  await page.fill('input[name=username]', user);
  await page.fill('input[name=password]', 'demo12345');
  await page.click('button[type=submit]');
  await page.waitForLoadState('networkidle');
}

async function memberLogin(page) {
  await page.context().clearCookies();
  await page.goto(BASE + '/fa/panel/login/');
  await page.fill('input[name=username]', 'demo-member');
  await page.fill('input[name=password]', 'demo12345');
  await page.locator('main form button[type=submit], main form input[type=submit]').first().click();
  await page.waitForLoadState('networkidle');
}

// marks: [{sel, n, pad?, side?}] — outline each element and put a numbered disc at its corner.
async function annotate(page, marks) {
  await page.evaluate((marks) => {
    const fa = n => String(n).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
    document.querySelectorAll('.guide-mark').forEach(e => e.remove());
    for (const m of marks) {
      let el;
      try { el = typeof m.sel === 'string' ? document.querySelector(m.sel) : null; } catch (e) { el = null; }
      if (m.text) el = [...document.querySelectorAll(m.within || 'a,button,h1,h2,h3,label,span,th,li,div,p')].find(e => e.textContent.trim().startsWith(m.text) && e.offsetParent !== null) || el;
      if (!el) { console.log('MISSING ' + (m.sel || m.text)); continue; }
      const r = el.getBoundingClientRect();
      const pad = m.pad ?? 4;
      const box = document.createElement('div');
      box.className = 'guide-mark';
      Object.assign(box.style, { position: 'absolute', left: (r.left + scrollX - pad) + 'px', top: (r.top + scrollY - pad) + 'px',
        width: (r.width + pad * 2) + 'px', height: (r.height + pad * 2) + 'px', border: '3px solid #cf9d2b', borderRadius: '8px',
        zIndex: 99998, pointerEvents: 'none', boxShadow: '0 0 0 3px rgba(255,255,255,.7)' });
      if (m.box === false) box.style.border = 'none', box.style.boxShadow = 'none';
      const disc = document.createElement('div');
      disc.className = 'guide-mark';
      disc.textContent = fa(m.n);
      const M = (document.querySelector('main') || document.body).getBoundingClientRect();
      const lo = m.inSidebar ? 0 : Math.max(0, M.left), hi = m.inSidebar ? innerWidth : Math.min(innerWidth, M.right);
      let left = m.side === 'left' ? r.left - pad - 15 : r.right + pad - 15;
      left = Math.min(Math.max(left, lo + 4), hi - 36);
      const top = Math.max(r.top - pad - 15, 4);
      Object.assign(disc.style, { position: 'absolute', left: (left + scrollX) + 'px', top: (top + scrollY) + 'px',
        width: '30px', height: '30px', borderRadius: '50%', background: '#1c1f4a', color: '#fff', font: '700 17px/30px Vazirmatn, Tahoma',
        textAlign: 'center', zIndex: 99999, border: '2px solid #fff', boxShadow: '0 1px 4px rgba(0,0,0,.35)' });
      document.body.appendChild(box); document.body.appendChild(disc);
    }
  }, marks);
}

async function shot(page, name, opts = {}) {
  await page.addStyleTag({ content: 'wagtail-userbar,.w-userbar{display:none!important}' }).catch(() => {});
  await page.waitForTimeout(250);
  let clip = opts.clip; const vp = page.viewportSize();
  if (opts.full) {
    const h = await page.evaluate(() => Math.max(...[...document.querySelectorAll('main, body, html, .content-wrapper, .w-overflow-auto')].map(e => e.scrollHeight)));
    await page.setViewportSize({ width: vp.width, height: Math.min(h, opts.maxH || 1900) }); await page.waitForTimeout(300);
  }
  if (opts.main) {
    const r = await page.evaluate(() => { const m = document.querySelector('main') || document.body; const b = m.getBoundingClientRect();
      return { x: Math.max(0, b.left + scrollX), y: 0, width: Math.min(b.width, innerWidth), height: Math.max(document.documentElement.scrollHeight, innerHeight) }; });
    clip = { x: r.x, y: 0, width: r.width, height: page.viewportSize().height };
  }
  if (opts.from) {
    await page.addStyleTag({ content: '.site-header{position:static!important}' });
    const y = await page.evaluate(sel => { const e = document.querySelector(sel); return e ? Math.max(0, e.getBoundingClientRect().top + scrollY - 28) : 0; }, opts.from);
    clip = { x: 0, y, width: page.viewportSize().width, height: opts.h || 760 };
  }
  await page.screenshot({ path: OUT + name + '.jpg', type: 'jpeg', quality: 84, clip, fullPage: !!opts.from });
  if (opts.full) await page.setViewportSize(vp);
  console.log('shot', name);
}

module.exports = { BASE, adminLogin, memberLogin, annotate, shot };
