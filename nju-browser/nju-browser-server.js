const http = require('http');
const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const PORT = parseInt(process.argv.find(a => a.startsWith('--port='))?.split('=')[1] || process.argv[process.argv.indexOf('--port') + 1]) || 4100;
const CHROME_PATH = 'C:/Users/wangzhiheng/.cache/puppeteer/chrome/win64-148.0.7778.97/chrome-win64/chrome.exe';

let browser = null;
let page = null;
let loggedInStatus = false;

async function launch() {
  console.log('[BS] Launching browser (Chrome for Testing 148)...');
  browser = await puppeteer.launch({
    headless: false,
    executablePath: CHROME_PATH,
    defaultViewport: { width: 1280, height: 900 },
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  await page.goto('https://search.nju.edu.cn/', { waitUntil: 'domcontentloaded', timeout: 20000 }).catch(() => {});
  loggedInStatus = !page.url().includes('/authserver/');
  console.log('[BS] Browser ready. Logged in:', loggedInStatus);

  if (!loggedInStatus) {
    waitForLoginInBackground();
  }

  browser.on('disconnected', () => {
    console.log('[BS] Browser disconnected');
    process.exit(1);
  });
}

async function waitForLoginInBackground() {
  try {
    await page.waitForSelector('#qr_img', { timeout: 10000 }).catch(() => {});
    await new Promise(r => setTimeout(r, 2000));
    const qrFile = path.join(__dirname, '.nju-qr.png');
    const el = await page.$('#qr_img');
    if (el) await el.screenshot({ path: qrFile });

    console.log('[BS] 等待扫码登录...');
    while (page.url().includes('/authserver/')) {
      await new Promise(r => setTimeout(r, 1000));
    }
    loggedInStatus = true;
    console.log('[BS] 登录成功');
    await new Promise(r => setTimeout(r, 3000));
  } catch (e) {
    console.log('[BS] 登录等待异常:', e.message);
  }
}

async function ensureLogin() {
  if (!page) return { error: 'browser not ready' };
  try {
    await page.goto('https://search.nju.edu.cn/', { waitUntil: 'domcontentloaded', timeout: 15000 });
    if (page.url().includes('/authserver/')) {
      console.log('[BS] Need login, triggering QR...');
      await page.waitForSelector('#qr_img', { timeout: 10000 }).catch(() => {});
      await new Promise(r => setTimeout(r, 2000));
      const qrFile = path.join(__dirname, '.nju-qr.png');
      const qrEl = await page.$('#qr_img');
      if (qrEl) await qrEl.screenshot({ path: qrFile });
      else await page.screenshot({ path: qrFile, fullPage: true });

      console.log('[BS] Waiting for QR scan...');
      while (page.url().includes('/authserver/')) await new Promise(r => setTimeout(r, 1000));
      console.log('[BS] Login successful');
      await new Promise(r => setTimeout(r, 3000));
    }
    return { ok: true, url: page.url() };
  } catch (e) {
    return { error: e.message };
  }
}

const server = http.createServer(async (req, res) => {
  const send = (data, status = 200) => {
    res.writeHead(status, {
      'Content-Type': typeof data === 'string' && data.startsWith('<') ? 'text/html' : 'application/json',
      'Access-Control-Allow-Origin': '*',
    });
    res.end(typeof data === 'string' ? data : JSON.stringify(data, null, 2));
  };
  const sendError = (msg, status = 500) => send({ error: msg }, status);

  const pathname = new URL(req.url, `http://${req.headers.host}`).pathname;
  let body = '';
  req.on('data', c => body += c);
  req.on('end', async () => {
    try {
      const params = body ? JSON.parse(body) : {};

      switch (pathname) {
        case '/status': {
          if (!browser || !page) return send({ alive: false, error: 'not started' });
          const cookies = await page.cookies();
          send({
            alive: true,
            loggedIn: loggedInStatus,
            url: page.url(),
            title: await page.title(),
            cookies: cookies.length,
          });
          break;
        }

        case '/login': {
          const r = await ensureLogin();
          if (r.error) return sendError(r.error);
          loggedInStatus = true;
          send({ ok: true, url: r.url });
          break;
        }

        case '/search': {
          if (!page) return sendError('browser not ready');
          const { keyword, type, page: p, size } = params;
          if (!keyword) return sendError('keyword required');
          const js = `fetch("/aisearch/api/api/v1/aisearch/search",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({keyword:${JSON.stringify(keyword)},type:${JSON.stringify(type || 'zh')},page:${p || 1},size:${size || 10}})}).then(r=>r.json()).then(d=>JSON.stringify(d))`;
          const raw = await page.evaluate(js);
          try { send(JSON.parse(raw)); }
          catch { send({ error: 'parse failed', raw }); }
          break;
        }

        case '/navigate': {
          if (!page) return sendError('browser not ready');
          await page.goto(params.url, { waitUntil: 'networkidle2', timeout: 30000 });
          send({ ok: true, url: page.url(), title: await page.title() });
          break;
        }

        case '/screenshot': {
          if (!page) return sendError('browser not ready');
          const buf = await page.screenshot({ fullPage: params.fullPage !== false });
          res.writeHead(200, { 'Content-Type': 'image/png', 'Content-Length': buf.length });
          res.end(buf);
          break;
        }

        case '/evaluate': {
          if (!page) return sendError('browser not ready');
          if (!params.js) return sendError('js required');
          const result = await page.evaluate(params.js);
          send({ result: JSON.stringify(result) });
          break;
        }

        case '/extract': {
          if (!page) return sendError('browser not ready');
          const data = await page.evaluate(() => ({
            title: document.title,
            url: location.href,
            text: document.body.innerText.slice(0, 10000),
            links: Array.from(document.querySelectorAll('a[href]')).slice(0, 30).map(a => ({ text: a.textContent.trim().slice(0, 80), href: a.href })),
          }));
          send(data);
          break;
        }

        case '/page': {
          if (!page) return sendError('browser not ready');
          const html = await page.content();
          send({
            url: page.url(),
            title: await page.title(),
            html: html.slice(0, 50000),
          });
          break;
        }

        case '/cookies': {
          if (!page) return sendError('browser not ready');
          const cookies = await page.cookies();
          send(cookies.map(c => ({ name: c.name, domain: c.domain, expires: c.expires ? new Date(c.expires * 1000).toISOString() : 'session', httpOnly: c.httpOnly })));
          break;
        }

        case '/shutdown': {
          send({ ok: true, message: 'shutting down' });
          setTimeout(async () => {
            if (browser) await browser.close();
            server.close();
            process.exit(0);
          }, 500);
          break;
        }

        default:
          send({
            name: 'NJU Browser Server',
            commands: ['/status', '/login', '/search', '/navigate', '/screenshot', '/evaluate', '/extract', '/page', '/cookies', '/shutdown'],
            usage: { search: { keyword: 'string', type: '"zh"|"xwzx"|"xmt"|"xsbg"|"jszy"', page: 1, size: 10 } }
          });
      }
    } catch (e) {
      sendError(e.message);
    }
  });
});

(async () => {
  await launch();
  server.listen(PORT, () => {
    console.log('\n═══════════════════════════════════════════');
    console.log(`  NJU Browser Server running on port ${PORT}`);
    console.log('  API: http://127.0.0.1:' + PORT);
    console.log('═══════════════════════════════════════════\n');
    console.log('  Commands:');
    console.log('    curl http://127.0.0.1:' + PORT + '/status');
    console.log('    curl -X POST -H "Content-Type: application/json" \\');
    console.log('      -d \'{"keyword":"机器学习"}\' \\');
    console.log('      http://127.0.0.1:' + PORT + '/search');
    console.log('    curl -X POST http://127.0.0.1:' + PORT + '/shutdown\n');
  });
})();