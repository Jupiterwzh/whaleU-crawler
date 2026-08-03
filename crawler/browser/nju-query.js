/**
 * nju-query.js
 *
 * 向运行中的浏览器服务器发送搜索请求。快速返回，不启动任何进程。
 *
 * 用法:
 *   node nju-query.js "机器学习" zh
 *   node nju-query.js "南京大学" xwzx
 *   node nju-query.js "深度学习" zh 2
 */
const http = require('http');

const PORT = 4100;

function api(method, path, data) {
  return new Promise((resolve, reject) => {
    const body = data ? JSON.stringify(data) : null;
    const opts = {
      hostname: '127.0.0.1', port: PORT,
      path, method,
      headers: { 'Content-Type': 'application/json', 'Content-Length': body ? Buffer.byteLength(body) : 0 },
    };
    const req = http.request(opts, (res) => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => {
        try { resolve(JSON.parse(d)); }
        catch { resolve({ raw: d }); }
      });
    });
    req.on('error', () => resolve(null));
    if (body) req.write(body);
    req.end();
  });
}

(async () => {
  const args = process.argv.slice(2);
  const keyword = args[0] || '';
  const type = args[1] || 'zh';
  const page = parseInt(args[2]) || 1;
  const size = parseInt(args[3]) || 8;

  if (!keyword) {
    // Status check
    const s = await api('GET', '/status');
    if (!s) { console.log('服务器未运行'); process.exit(1); }
    console.log(`状态: ${s.loggedIn ? '已登录' : '未登录'} | ${s.url}`);
    console.log(`Cookies: ${s.cookies} 个`);
    process.exit(0);
  }

  const r = await api('POST', '/search', { keyword, type, page, size });
  if (!r) { console.log('搜索失败（服务器未就绪）'); process.exit(1); }

  const arts = r?.data?.articles?.articles || [];
  const total = r?.data?.articles?.total || 0;

  console.log(`[${type}] "${keyword}" — 共 ${total} 条\n`);
  arts.forEach((a, i) => {
    const title = (a.title || '').replace(/<[^>]+>/g, '').trim();
    const url = a.url || '';
    const t = (a.publishTime || '').slice(0, 10);
    const src = a.sourceName || a.siteName || '';
    const summary = (a.summary || '').replace(/<[^>]+>/g, '').slice(0, 120).trim();
    console.log(`${i + 1}. ${title}`);
    console.log(`   ${url}`);
    if (src || t) console.log(`   ${src}${src && t ? ' | ' : ''}${t}`);
    if (summary) console.log(`   ${summary}`);
    console.log();
  });
})();
