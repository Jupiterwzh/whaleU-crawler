/**
 * NJU 智能搜索爬虫 v2
 *
 * API 信息（从 APP_CONFIG 获取）：
 *   Base: /aisearch/api/api/v1
 *   搜索类型: zh(综合), xwzx(新闻), xmt(公众号), xsbg(讲座), jszy(教师)
 *           image(图片), video(视频), bs(办事服务)
 */
const fs = require('fs');
const https = require('https');
const path = require('path');
const { URL } = require('url');

const BASE = 'https://search.nju.edu.cn';
const API = '/aisearch/api/api/v1';
const COOKIE_FILE = path.join(__dirname, '.nju-cookies.json');

function loadCookies() {
  try { return JSON.parse(fs.readFileSync(COOKIE_FILE)); }
  catch { return []; }
}

function apiRequest(apiPath, params = {}) {
  const cookies = loadCookies();
  const cookieStr = cookies.map(c => c.name + '=' + c.value).join('; ');
  const url = new URL(apiPath, BASE);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));

  return new Promise((resolve, reject) => {
    https.get(url.toString(), {
      headers: {
        Cookie: cookieStr,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': BASE + '/',
      }
    }, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        const location = res.headers.location || '';
        if (res.statusCode >= 301 && res.statusCode <= 303 && location.includes('/authserver/')) {
          reject(new Error('Cookie expired, re-login needed'));
          return;
        }
        try {
          resolve({ status: res.statusCode, data: JSON.parse(data) });
        } catch {
          resolve({ status: res.statusCode, raw: data.slice(0, 500) });
        }
      });
    }).on('error', reject);
  });
}

// 探索 API 端点
async function exploreAPI() {
  const endpoints = [
    { path: '/aisearch/api/api/v1/search', label: '综合搜索' },
    { path: '/aisearch/api/api/v1/search/zh', label: '综合搜索 v2' },
    { path: '/aisearch/api/api/v1/search/zh/list', label: '综合搜索列表' },
    { path: '/aisearch/api/api/v1/search/xwzx', label: '新闻搜索' },
    { path: '/aisearch/api/api/v1/search/xmt', label: '公众号搜索' },
    { path: '/aisearch/api/api/v1/search/xsbg', label: '学术讲座搜索' },
    { path: '/aisearch/api/api/v1/search/jszy', label: '教师主页搜索' },
    { path: '/aisearch/api/api/v1/search/bs', label: '办事服务搜索' },
    { path: '/aisearch/api/api/v1/search/image', label: '图片搜索' },
    { path: '/aisearch/api/api/v1/search/video', label: '视频搜索' },
    { path: '/aisearch/api/api/v1/searchall', label: '全站搜索' },
    { path: '/aisearch/api/api/v1/hot', label: '热搜' },
    { path: '/aisearch/api/api/v1/hotword', label: '热词' },
    { path: '/aisearch/api/api/v1/suggest', label: '搜索建议' },
    { path: '/aisearch/api/api/v1/suggestion', label: '搜索建议 v2' },
  ];

  const term = process.argv[2] || '机器学习';

  for (const ep of endpoints) {
    try {
      const params = { keyword: term, page: 1, size: 5 };
      if (ep.path.includes('suggest') || ep.path.includes('hot')) delete params.keyword;
      const result = await apiRequest(ep.path, params);
      const status = result.status;
      const summary = result.data
        ? `OK ${JSON.stringify(result.data).slice(0, 120)}`
        : (result.raw || 'no data');
      console.log(`[${status === 200 ? '✓' : '✗'}] ${ep.label.padEnd(12)} ${ep.path}`);
      console.log(`     ${status} | ${summary}\n`);
    } catch (e) {
      console.log(`[!] ${ep.label}: ${e.message}`);
    }
  }
}

// 执行搜索并输出结构化结果
async function search(type = 'zh', keyword = '机器学习', page = 1, size = 10) {
  const result = await apiRequest(`/aisearch/api/api/v1/search/${type}`, { keyword, page, size });
  if (result.status === 200 && result.data) {
    console.log(JSON.stringify(result.data, null, 2));
  } else {
    console.log(`HTTP ${result.status}:`, result.raw || result.data);
  }
}

// Main
(async () => {
  const args = process.argv.slice(2);

  if (args.includes('--explore')) {
    await exploreAPI();
    return;
  }

  if (args.includes('--search')) {
    const type = args[args.indexOf('--search') + 1] || 'zh';
    const keyword = args[args.indexOf('--keyword') + 1] || '机器学习';
    const page = parseInt(args[args.indexOf('--page') + 1]) || 1;
    const size = parseInt(args[args.indexOf('--size') + 1]) || 10;
    await search(type, keyword, page, size);
    return;
  }

  // 默认：探索 API
  console.log('NJU Search Crawler\ncookie:', loadCookies().length, '个\n');
  await exploreAPI();
})();
