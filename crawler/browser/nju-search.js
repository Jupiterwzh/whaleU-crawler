const fs = require('fs');
const https = require('https');
const path = require('path');

const BASE = 'https://search.nju.edu.cn';
const COOKIE_FILE = path.join(__dirname, '.nju-cookies.json');

function loadCookies() {
  try { return JSON.parse(fs.readFileSync(COOKIE_FILE)); }
  catch { return []; }
}

function request(method, apiPath, body = null) {
  const cookies = loadCookies();
  const cookieStr = cookies.map(c => c.name + '=' + c.value).join('; ');
  const url = new URL(apiPath, BASE);
  return new Promise((resolve, reject) => {
    const opts = {
      hostname: url.hostname,
      path: url.pathname + url.search,
      method,
      headers: {
        'Cookie': cookieStr,
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Referer': BASE + '/',
      }
    };
    const req = https.request(opts, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        const loc = res.headers.location || '';
        if (res.statusCode >= 301 && res.statusCode <= 303 && loc.includes('/authserver/')) {
          reject(new Error('Auth expired'));
          return;
        }
        try { resolve({ status: res.statusCode, data: JSON.parse(data) }); }
        catch { resolve({ status: res.statusCode, raw: data.slice(0, 1000) }); }
      });
    });
    req.on('error', reject);
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

(async () => {
  const args = process.argv.slice(2);
  const keyword = args[0] || '人工智能';

  console.log('NJU Intelligent Search\n');

  // Check cookies
  const castgc = loadCookies().find(c => c.name === 'CASTGC');
  if (castgc) console.log('CASTGC expires:', new Date(castgc.expires * 1000).toLocaleString());

  // Try search
  console.log('Searching:', keyword, '\n');
  try {
    const result = await request('POST', '/aisearch/api/api/v1/aisearch/search', {
      searchType: 'zh',
      pageSize: 5,
      pageNum: 1,
      searchWord: keyword,
    });
    console.log('HTTP', result.status);
    const d = result.data;
    if (d) {
      console.log('Code:', d.code, '| Msg:', d.msg || d.message);
      const list = d.data || d.result || d.rows || d.list || [];
      const total = d.total || d.totalNum || d.count || list.length;
      console.log('Total results:', total, '\n');
      (Array.isArray(list) ? list : (list.records || [])).slice(0, 10).forEach((item, i) => {
        const title = item.title || item.name || item.content || '(no title)';
        const url = item.url || item.link || item.href || '';
        const summary = (item.summary || item.description || item.content || '').slice(0, 120);
        console.log((i + 1) + '. ' + title.replace(/<[^>]+>/g, ''));
        if (url) console.log('   ' + url);
        if (summary) console.log('   ' + summary.replace(/<[^>]+>/g, ''));
        console.log();
      });
    }
  } catch (e) {
    console.log('Search failed:', e.message);
  }
})();
