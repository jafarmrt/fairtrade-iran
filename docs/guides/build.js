// node build.js admin.html out.pdf
// Two passes: the first finds on which page each chapter starts (read back from the PDF outline
// with outline.py / pypdf), the second writes those numbers into the table of contents.
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const fa = n => String(n).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);

async function render(page, out) {
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({ path: out, format: 'A4', printBackground: true, preferCSSPageSize: true, tagged: true, outline: true });
}

(async () => {
  const [src, out] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + path.resolve(src), { waitUntil: 'load' });
  const ids = await page.evaluate(() => {
    const ids = [];
    const ol = document.querySelector('.toc ol');
    document.querySelectorAll('[data-toc]').forEach((el, i) => {
      const id = 'T' + String(i).padStart(2, '0');
      const h = el.querySelector('h1, h2');
      ids.push([id, h ? h.textContent.trim() : '']);
      if (!ol) return;
      const li = document.createElement('li');
      li.className = el.dataset.tocKind || 'ch';
      li.innerHTML = '<span class="t"></span><span class="dots"></span><span class="pg">۰۰</span>';
      li.querySelector('.t').textContent = el.dataset.toc;
      li.querySelector('.pg').dataset.for = id;
      ol.appendChild(li);
    });
    return ids;
  });
  const tmp = out + '.pass1.pdf';
  await render(page, tmp);
  const pages = Number(execFileSync('pdfinfo', [tmp]).toString().match(/Pages:\s+(\d+)/)[1]);
  const outline = JSON.parse(execFileSync('python3', [__dirname + '/outline.py', tmp]).toString());
  const where = {}; let k = 0;
  for (const [id, title] of ids) {
    const j = outline.findIndex((o, n) => n >= k && o[0] === title);
    if (j >= 0) { where[id] = outline[j][1]; k = j + 1; }
  }
  await page.evaluate(({ where, digits }) => {
    const fa = n => String(n).replace(/\d/g, d => digits[d]);
    document.querySelectorAll('.toc .pg').forEach(s => { s.textContent = where[s.dataset.for] ? fa(where[s.dataset.for]) : '–'; });
  }, { where, digits: '۰۱۲۳۴۵۶۷۸۹' });
  await render(page, out);
  fs.unlinkSync(tmp);
  const missing = ids.filter(([i]) => !where[i]).map(x => x[1]);
  console.log(out, 'pages:', pages, missing.length ? 'missing: ' + missing : 'toc ok');
  await browser.close();
})();
