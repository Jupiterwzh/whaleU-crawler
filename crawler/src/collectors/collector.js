/**
 * collector.js — 自动信息检索模块 独立爬虫
 *
 * 支持：
 *   --url <URL>          爬取单个页面
 *   --notices <URL>      爬取通知列表页（提取所有公告并爬取正文）
 *   --all                爬取全部站点首页
 *   --all-notices        爬取所有站点的通知列表（需 sites.js 支持）
 *   --http               使用 HTTP 模式（无需浏览器）
 *   --days <N>           只爬取 N 天内的通知
 *   --max-pages <N>      通知列表最多爬 N 页（默认 5）
 *
 * 用法示例：
 *   node collector.js --notices https://cs.nju.edu.cn/1702/list.htm
 *   node collector.js --notices https://cs.nju.edu.cn/1702/list.htm --days 365 --max-pages 10
 *   node collector.js --notices https://cs.nju.edu.cn/1702/list.htm --http
 */

const fs = require('fs');
const path = require('path');
const http = require('http');
const https = require('https');
const {
  getStrategy, saveStrategy, getDraft, saveDraft, confirmDraft,
  listStrategies, deleteStrategy, getAllStrategies,
} = require('../strategies/strategy-manager');
const { analyzeSite } = require('../analyzers/analyzer');
const { exploreSiteSimple } = require('../explorers/site-explorer');

// ============================================================
// 草稿构建辅助函数
// ============================================================

function buildDraftFromResult(result) {
  const now = new Date().toISOString();
  const entries = (result.entries || []).map(e => ({
    name: e.name || '未命名栏目',
    url: e.url,
    type: e.type || e.cmsType || 'other',
    paginationType: e.paginationType || 'none',
    paginationHint: e.paginationHint || '',
    estimatedCount: e.estimatedCount || 0,
    notes: e.notes || '',
  }));

  return {
    meta: {
      domain: result.domain,
      siteName: result.siteName || result.domain,
      discoveredAt: now,
      aiModel: result.mode === 'full' ? 'claude/openai' : 'heuristic',
      status: 'draft',
    },
    entries,
    pagination: entries.length > 0 ? {
      type: entries[0].paginationType,
      hint: entries[0].paginationHint,
    } : { type: 'none' },
    notes: result._raw?.overallNotes || '',
    _raw: result._raw,
  };
}

// ============================================================
// HTTP 工具
// ============================================================

function httpGet(targetUrl, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    let parsed;
    try { parsed = new URL(targetUrl); }
    catch (e) { return reject(new Error(`无效 URL: ${targetUrl}`)); }

    const lib = parsed.protocol === 'https:' ? https : http;
    const req = lib.get({
      hostname: parsed.hostname,
      port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
      path: parsed.pathname + parsed.search,
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
      },
      timeout: timeoutMs,
    }, (res) => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
        return httpGet(res.headers.location, timeoutMs).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) return reject(new Error(`HTTP ${res.statusCode}`));
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('请求超时')); });
    req.end();
  });
}

// ============================================================
// HTML 解析
// ============================================================

function extractText(html) {
  let text = html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<noscript[^>]*>[\s\S]*?<\/noscript>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/[\u200b-\u200f\ufeff]/g, '').replace(/\s+/g, ' ').trim();
  const m = html.match(/<title[^>]*>([^<]*)<\/title>/i);
  return { title: m ? m[1].trim() : '', text: text.slice(0, 20000) };
}

function makeAbsolute(href, baseUrl) {
  try {
    const base = new URL(baseUrl);
    if (href.startsWith('//')) return base.protocol + href;
    if (href.startsWith('/')) return base.origin + href;
    if (/^https?:\/\//i.test(href)) return href;
    return new URL(href, baseUrl).href;
  } catch { return null; }
}

/**
 * 判断 URL 是否指向微信公众号外链（mp.weixin.qq.com 等）。
 * 小组其他成员已实现公众号爬取，故这里不作为通知提取。
 */
function _isWechatUrl(href) {
  if (!href) return false;
  try {
    const host = new URL(href).hostname;
    return /(^|\.)weixin\.qq\.com$/i.test(host) || /(^|\.)wechat\.com$/i.test(host);
  } catch { return false; }
}

/**
 * 找到 JS 变量 dataList=[{...}] 中 infolist 数组的内容
 * 返回字符串片段（近似 JSON 格式，需进一步处理）
 */
function extractInfolistFromJs(html) {
  const startMarker = 'dataList=';
  const idx = html.indexOf(startMarker);
  if (idx === -1) return null;

  // 用括号计数找到 dataList=[...] 的结束位置
  let depth = 0;
  let start = -1;
  let i = idx + startMarker.length;

  while (i < html.length) {
    const ch = html[i];
    if (ch === '[' && start === -1) { start = i; depth = 1; i++; continue; }
    if (start === -1) { i++; continue; }
    if (ch === '{') { depth++; }
    else if (ch === '}') { depth--; if (depth === 0) { return html.slice(start, i + 1); } }
    else if (ch === ']') { depth--; if (depth === 0) { return html.slice(start, i + 1); } }
    i++;
  }
  return null;
}

/**
 * 从 JS infolist 字符串中提取多个 item
 * dataList=[{"infolist":[item1, item2, ...]}]
 */
function parseInfolistJson(infolistStr) {
  const notices = [];
  // 找 infolist 数组内容区域
  const arrM = infolistStr.match(/"infolist"\s*:\s*\[/);
  if (!arrM) return notices;
  const arrStart = arrM.index + arrM[0].length;
  const arrEnd = infolistStr.indexOf(']', arrStart);
  const arrContent = arrEnd > 0 ? infolistStr.slice(arrStart, arrEnd) : '';

  // 逐个提取 item 对象：匹配 { 开头到对应 } 结尾
  let pos = 0;
  while (pos < arrContent.length) {
    // 跳过空白和逗号
    while (pos < arrContent.length && /[\s,]/.test(arrContent[pos])) pos++;
    if (pos >= arrContent.length || arrContent[pos] !== '{') break;

    // 括号计数找 item 边界
    let depth = 0, start = pos;
    for (; pos < arrContent.length; pos++) {
      const ch = arrContent[pos];
      if (ch === '{') depth++;
      else if (ch === '}') { if (--depth === 0) { pos++; break; } }
    }
    const itemStr = arrContent.slice(start, pos);
    if (!itemStr) break;

    const href = extractField(itemStr, 'url') || extractField(itemStr, 'linktitle');
    const title = extractField(itemStr, 'title') || extractField(itemStr, 'infotitle');
    const date = extractField(itemStr, 'daytime');
    if (href) notices.push({ href, title: title || '', date });
  }
  return notices;
}

/**
 * 从 JS 对象字符串中提取字段值（支持双引号、单引号、无引号三种格式）
 */
function extractField(objStr, fieldName) {
  // "field": "value" 或 'field': 'value' 或 "field": value
  const patterns = [
    new RegExp(`"${fieldName}"\\s*:\\s*"([^"\\\\]*(?:\\\\.[^"\\\\]*)*)"`),
    new RegExp(`'${fieldName}'\\s*:\\s*'([^'\\\\]*(?:\\\\.[^'\\\\]*)*)'`),
    new RegExp(`"${fieldName}"\\s*:\\s*([^,}\\]]+)`),
  ];
  for (const re of patterns) {
    const m = objStr.match(re);
    if (m) {
      return m[1].replace(/\\./g, x => x[1]).replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').trim();
    }
  }
  return null;
}

/**
 * 从通知列表页提取公告条目
 * 支持多种 HTML 结构，返回 { href, title, date }[]
 */
/**
 * 多模式竞争提取通知列表。
 * 每种提取模式独立运行，返回带置信度的结果。
 * 最终按 confidence 降序去重，保证高质量结果覆盖低质量。
 */
function extractNotices(html, baseUrl) {
  const baseDomain = new URL(baseUrl).hostname;
  const allResults = [];

  // ---- 模式0: dataList JSON 嵌入 (software.nju.edu.cn 等 SPA) ----
  const infolistStr = extractInfolistFromJs(html);
  if (infolistStr) {
    const parsed = parseInfolistJson(infolistStr);
    if (parsed.length > 0) {
      for (const n of parsed) {
        const href = makeAbsolute(n.href || '', baseUrl);
        if (!href || _isWechatUrl(href)) continue;
        allResults.push({ href, title: n.title || n.listtitle || '', date: n.datetime || n.date || null, confidence: 95, source: 'dataList' });
      }
    }
  }

  // ---- 模式1: news_title + news_date 结构化 CMS（兼容 span/div）----
  const newsTitleRegex = /<(?:span|div)[^>]*class=["']news_title["'][^>]*>\s*<a[^>]+href=["']([^"']+)["'][^>]*(?:title=["']([^"']+)["'])?[^>]*>([^<]+)<\/a>/gi;
  let m;
  while ((m = newsTitleRegex.exec(html)) !== null) {
    const href = makeAbsolute(m[1], baseUrl);
    const title = (m[2] || m[3] || '').replace(/<[^>]+>/g, '').trim();
    if (href && title && !_isWechatUrl(href)) allResults.push({ href, title, date: null, confidence: 90, source: 'news_title' });
  }
  // 匹配 news_date 并就近分配
  const dateRegex = /<span[^>]+class=["'][^"']*news_date[^"']*["'][^>]*>([^<]+)<\/span>/gi;
  const allDates = [];
  while ((m = dateRegex.exec(html)) !== null) allDates.push({ pos: m.index, date: m[1].trim() });
  for (const r of allResults.filter(r => r.source === 'news_title' && !r.date)) {
    const pos = html.indexOf(r.href);
    for (const d of allDates) { if (d.pos < pos) r.date = d.date; else break; }
    if (r.date) r.confidence += 5;
  }

  // ---- 模式2: <a href="...">标题<span>日期</span></a> 行内式 ----
  const artRegex = /<a[^>]+href=["']([^"']+)["'][^>]*>\s*([^<\s][^<]{4,50}?)\s*(?:<span[^>]*>([^<\s][^<]{4,20})?<\/span>)?/gi;
  while ((m = artRegex.exec(html)) !== null) {
    const href = makeAbsolute(m[1], baseUrl);
    if (!href || href.includes('list.htm') || href.includes('javascript:') || href.match(/\/(?:main|index)\.htm$/i)) continue;
    const title = m[2].replace(/<[^>]+>/g, '').trim();
    const date = m[3] ? m[3].replace(/<[^>]+>/g, '').trim() : null;
    if (!title || title.length < 6 || /^[a-zA-Z\s]{1,10}$/.test(title)) continue;
    if (_isWechatUrl(href)) continue;
    const navKeywords = ['学院概览', '学院简介', '师资队伍', '科学研究', '人才培养', '党的建设', '热门', '热点', '专家', '教授', '首页', '返回', '更多', '栏目', '机构', '管理', '联系我们', 'English'];
    if (navKeywords.some(k => title.includes(k)) && title.length < 12) continue;
    allResults.push({ href, title, date, confidence: date ? 75 : 60, source: 'article_inline' });
  }

  // ---- 模式3: link-title（历史学院等） ----
  const linkTitleRegex = /<span[^>]+class=["']link-title["'][^>]*>\s*<a[^>]+href=["']([^"']+)["'][^>]*>([^<]+)<\/a>/gi;
  while ((m = linkTitleRegex.exec(html)) !== null) {
    const href = makeAbsolute(m[1], baseUrl);
    const title = (m[2] || '').replace(/<[^>]+>/g, '').trim();
    if (!href || !title || title.length < 4) continue;
    try { if (new URL(href).hostname !== baseDomain) continue; } catch { /* relative ok */ }
    const externalKeywords = ['研究中心', '研究所', '研究院', '委员会', '编辑部', '基地', '实验室', '学会', '协会', '编辑部', '办公室'];
    if (externalKeywords.some(k => title.includes(k)) && title.length < 15) continue;
    allResults.push({ href, title, date: null, confidence: 70, source: 'link_title' });
  }
  // link-title 日期就近分配
  const linkDateRegex = /<span[^>]+class=["'][^"']*(?:link-date|time|date|meta)[^"']*["'][^>]*>([^<]+)<\/span>/gi;
  const allLinkDates = [];
  while ((m = linkDateRegex.exec(html)) !== null) allLinkDates.push({ pos: m.index, date: m[1].trim() });
  for (const r of allResults.filter(r => r.source === 'link_title' && !r.date)) {
    const pos = html.indexOf(r.title);
    for (const d of allLinkDates) { if (d.pos < pos + 300) r.date = d.date; }
    if (r.date) r.confidence += 5;
  }

  // ---- 模式4: 纯文本日期+标题行（无 HTML 结构，如 history.nju.edu.cn 首页某些区块）----
  // 匹配 通知公告 附近结构：<div class="news_date">09-28</div><div class="news_arti">标题</div>
  const dateTitleRegex = /<div[^>]+class=["'][^"']*news_date[^"']*["'][^>]*>([^<]+)<\/div>[\s\S]{0,200}?<div[^>]+class=["'][^"']*news_arti[^"']*["'][^>]*>[\s\S]{0,50}?<span[^>]+class=["']news_title["'][^>]*>([^<]+)<\/span>/gi;
  while ((m = dateTitleRegex.exec(html)) !== null) {
    const date = m[1].trim();
    const title = m[2].replace(/<[^>]+>/g, '').trim();
    if (title && title.length >= 4) {
      allResults.push({ href: null, title, date, confidence: 80, source: 'news_date_arti' });
    }
  }

  // ---- 模式5: 通用的 <li> 条目列表（兜底）----
  // 找 <li> 内含 <a href="..."> 且附近有日期
  const liDateRegex = /<li[^>]*>([\s\S]{1,300}?href=["']([^"']+)["'][^>]*>)[\s\S]{1,200}?(?:(\d{4}[-\/]\d{2}[-\/]\d{2}|\d{2}[-\/]\d{2}[-\/]\d{4}))/gi;
  while ((m = liDateRegex.exec(html)) !== null) {
    const href = makeAbsolute(m[2], baseUrl);
    const date = m[3] ? m[3].trim() : null;
    const ctx = m[1];
    const titleMatch = ctx.match(/>([^<]{4,60}?)<\/a>/);
    const title = titleMatch ? titleMatch[1].replace(/<[^>]+>/g, '').trim() : '';
    if (!href || !title || title.length < 4 || href.includes('list.htm') || href.includes('javascript:')) continue;
    const navKeywords = ['学院概览', '学院简介', '师资队伍', '科学研究', '人才培养', '党的建设', '首页', 'English'];
    if (navKeywords.some(k => title.includes(k)) && title.length < 12) continue;
    allResults.push({ href, title, date, confidence: 40, source: 'li_fallback' });
  }

  // ---- 按 confidence 降序去重：同 href 保留最高置信度 ----
  allResults.sort((a, b) => b.confidence - a.confidence);
  const seen = new Set();
  const deduped = [];
  for (const r of allResults) {
    if (r.href && seen.has(r.href)) continue;
    if (r.href) seen.add(r.href);
    // href 为 null 的模式（news_date_arti）直接保留（它们没有唯一标识，只能叠放）
    deduped.push({ href: r.href || null, title: r.title, date: r.date || null });
  }
  return deduped;
}

/**
 * 从通知文章页提取标题、正文、发布时间、附件、视频
 */
function extractArticle(html, url) {
  const { title: pageTitle, text } = extractText(html);

  // 标题：优先从 title 标签
  let title = pageTitle;

  // 尝试从内容区提取标题
  const h1M = html.match(/<h1[^>]*>([^<]+)<\/h1>/i);
  if (h1M) title = h1M[1].trim();

  // 发布时间：<span class="arti_update">发布时间：2026-07-10</span>
  let publishTime = null;
  const pubM = html.match(/发布时间[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)/);
  if (pubM) publishTime = normalizeDate(pubM[1]);

  // 或者从 meta keywords 附近找日期
  if (!publishTime) {
    const dateM = html.match(/(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)/);
    if (dateM) publishTime = normalizeDate(dateM[1]);
  }

  // 正文内容：从 class~article 的 div 中提取
  let content = '';
  const articleM = html.match(/class=["'][^"']*article[^"']*["'][^>]*>([\s\S]+?)<\/div>/i);
  if (articleM) {
    content = cleanContent(articleM[1]);
  }
  if (!content) {
    content = text; // fallback
  }

  // 提取附件：从正文区域或全文中查找文件下载链接
  const attachmentUrls = [];
  const baseParsed = new URL(url);
  const attachmentPatterns = [
    /href=["']([^"']*\_upload\/article\/files\/[^"']+\.(?:pdf|doc|docx|xls|xlsx|zip|rar|ppt|pptx))["']/gi,
    /href=["']([^"']*(?:attachment|attach|file|download|附件)[^"']*\.(?:pdf|doc|docx|xls|xlsx|zip|rar|ppt|pptx))["']/gi,
  ];
  for (const pat of attachmentPatterns) {
    let m;
    while ((m = pat.exec(html)) !== null) {
      let fhref = m[1];
      try { fhref = makeAbsolute(fhref, url); } catch {}
      if (fhref && !attachmentUrls.includes(fhref)) attachmentUrls.push(fhref);
    }
  }

  // 视频检测：检测 <video> 标签或常见视频平台嵌入
  const hasVideo = /<video[\s>]/i.test(html) || /<embed[^>]+youtube/i.test(html) || /<iframe[^>]+video\.taobao/i.test(html);
  const hasAudio = /<audio[\s>]/i.test(html);

  return {
    title,
    content: content.slice(0, 20000),
    publishTime,
    url,
    attachments: attachmentUrls.slice(0, 20),
    hasVideo,
    hasAudio,
  };
}

function cleanContent(html) {
  return html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/[\u200b-\u200f\ufeff]/g, '').replace(/\n{3,}/g, '\n\n').replace(/^[\s\n\r]+|[\s\n\r]+$/g, '').trim();
}

function normalizeDate(s) {
  if (!s) return null;
  s = s.trim();
  // 2026年7月10日 → 2026-07-10
  s = s.replace(/年(\d)月/, '年0$1月').replace(/月(\d)日/, '月0$1日');
  const m = s.match(/(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})[日]?/);
  if (m) return `${m[1]}-${m[2].padStart(2,'0')}-${m[3].padStart(2,'0')}`;
  return null;
}

function inferDepartment(url) {
  try {
    const host = new URL(url).hostname;
    const map = {
      'jw.nju.edu.cn': '本科生院', 'xsxy.nju.edu.cn': '新生学院',
      'software.nju.edu.cn': '软件学院', 'cs.nju.edu.cn': '计算机学院',
      'ai.nju.edu.cn': '人工智能学院', 'med.nju.edu.cn': '医学院',
      'law.nju.edu.cn': '法学院', 'lib.nju.edu.cn': '图书馆',
      'grawww.nju.edu.cn': '研究生院', 'scit.nju.edu.cn': '科学技术研究院',
    };
    for (const [h, d] of Object.entries(map)) if (host.includes(h)) return d;
    return host.split('.')[1] || host.split('.')[0];
  } catch { return ''; }
}

function inferTags(url, title, content) {
  const tags = new Set();
  const text = `${title} ${content}`.toLowerCase();
  const map = [
    [/通知|公告|通告/, '通知公告'], [/招聘|人才|引进/, '招聘信息'],
    [/学术报告|讲座|研讨会/, '学术报告'], [/课程|选课|课表/, '课程信息'],
    [/成绩|绩点|考试/, '成绩考核'], [/暑期|夏令营|冬令营/, '暑期活动'],
    [/比赛|竞赛|大赛/, '竞赛信息'], [/获奖|成果|一等奖/, '获奖成果'],
    [/公示|结果|拟录取/, '结果公示'], [/科研|项目|课题/, '科研项目'],
    [/会议|论坛|峰会/, '会议论坛'], [/招生|录取|推免/, '招生信息'],
    [/就业|实习/, '就业指导'], [/党建|党纪|党组织/, '党建工作'],
  ];
  for (const [re, label] of map) if (re.test(text)) tags.add(label);
  return Array.from(tags).slice(0, 5);
}

function buildRecord(url, raw) {
  const title = raw.title || '';
  const content = raw.content || '';
  const publishTime = raw.publishTime || null;
  const attachments = raw.attachments || [];
  const hasVideo = raw.hasVideo || false;
  const hasAudio = raw.hasAudio || false;
  const dept = inferDepartment(url);
  return {
    title,
    url,
    content,
    publishTime,
    attachments,
    hasVideo,
    hasAudio,
    source: { author: '', department: dept, siteName: dept },
    tags: inferTags(url, title, content),
    crawler: 'nju-crawler',
    crawlTime: new Date().toISOString(),
  };
}

// ============================================================
// 通知列表爬取
// ============================================================

/**
 * 爬取通知列表页及其所有分页，提取每条通知的详情
 * @param {string} listUrl - 通知列表页 URL（如 https://cs.nju.edu.cn/1702/list.htm）
 * @param {object} opts
 * @param {number} opts.maxPages - 最多爬几页（默认5）
 * @param {number} opts.maxDays - 只爬 N 天内的通知（默认无限制）
 * @param {string} opts.outputFile - 保存到的文件名
 */
async function crawlNotices(listUrl, opts = {}) {
  const { maxPages = 5, maxDays = null, outputFile = null } = opts;
  const baseUrl = listUrl;
  const baseParsed = new URL(baseUrl);
  const basePath = baseParsed.pathname.replace(/[^/]*$/, ''); // /1702/

  const cutoffDate = maxDays
    ? new Date(Date.now() - maxDays * 86400000).toISOString().slice(0, 10)
    : null;

  let allNotices = [];
  let page = 1;
  let nextUrl = listUrl;

  console.log(`\n== 爬取通知列表: ${listUrl} ==`);
  if (cutoffDate) console.log(`  只爬 ${maxDays} 天内通知（${cutoffDate} 之后）`);
  console.log('');

  // 全局已爬过的 URL（防止重复）
  const visitedUrls = new Set();
  // 最终保存的记录（去重）
  const savedSet = new Set();

  while (page <= maxPages && nextUrl) {
    console.log(`[第${page}页] ${nextUrl}`);
    let html;
    try {
      html = await httpGet(nextUrl, 15000);
    } catch (e) {
      console.error(`  获取页面失败: ${e.message}`);
      break;
    }

    const notices = extractNotices(html, nextUrl);
    console.log(`  发现 ${notices.length} 条通知`);

    if (notices.length === 0) {
      console.log('  无通知链接，停止分页');
      break;
    }

    // 过滤日期
    let newNotices = notices;
    if (cutoffDate) {
      newNotices = notices.filter(n => {
        if (!n.date) return true;
        return n.date >= cutoffDate;
      });
      const dropped = notices.length - newNotices.length;
      if (dropped > 0) console.log(`  过滤掉 ${dropped} 条过期通知`);
    }
    allNotices.push(...newNotices);

    // 找下一页链接（找 list{N}.htm，N = 当前页+1，顺序遍历）
    nextUrl = null;
    if (page < maxPages) {
      const paginationRegex = new RegExp(`href=["']([^"']*${basePath}list(\\d+)\\.htm)["']`, 'gi');
      const matches = [...html.matchAll(paginationRegex)];
      const pageNums = matches.map(mm => parseInt(mm[2])).filter(n => n > page);
      if (pageNums.length > 0) {
        const nextPage = Math.min(...pageNums);
        nextUrl = baseParsed.origin + basePath + `list${nextPage}.htm`;
      } else if (page === 1) {
        nextUrl = baseParsed.origin + basePath + `list${page + 1}.htm`;
      }
    }

    page++;
    if (nextUrl && page <= maxPages) {
      await new Promise(r => setTimeout(r, 500));
    }
  }

  if (allNotices.length === 0) {
    console.log('\n未找到任何通知');
    return { notices: [], saved: 0 };
  }

  // 全局去重（同一 URL 只爬一次）
  const uniqueNotices = [];
  for (const n of allNotices) {
    if (!visitedUrls.has(n.href)) {
      visitedUrls.add(n.href);
      uniqueNotices.push(n);
    }
  }

  console.log(`\n共 ${allNotices.length} 条（含重复 ${allNotices.length - uniqueNotices.length} 条），去重后 ${uniqueNotices.length} 条，开始爬取详情...\n`);

  let saved = 0;
  const saveFile = outputFile || `notices_${Date.now()}.jsonl`;
  const savePath = path.join(DATA_DIR, saveFile);

  for (let i = 0; i < uniqueNotices.length; i++) {
    const { href, title: listTitle, date } = uniqueNotices[i];
    process.stdout.write(`[${i+1}/${uniqueNotices.length}] ${href} ... `);

    try {
      const artHtml = await httpGet(href, 15000);

      // 判断是否为通知列表页
      // 条件：news_title + news_meta 同时存在，且数量大致相等（比例 >= 0.5）
      // main.htm 有 41 个 title 但只有 4 个 date → 不算列表页
      // /1702/list.htm 有 14 个 title 和 14 个 date → 算列表页
      const newsTitleCount = (artHtml.match(/class=["']news_title["']/gi) || []).length;
      const newsMetaCount = (artHtml.match(/class=["']news_meta["']/gi) || []).length;
      const isListPage = newsTitleCount > 0 && newsMetaCount > 0 && newsMetaCount >= newsTitleCount * 0.5;

      if (isListPage) {
        // 是列表页 → 递归爬取（自动分页遍历）
        console.log(`[列表页]`);
        const baseParsed = new URL(href);
        const basePath = baseParsed.pathname.replace(/[^/]*$/, '');
        let subPage = 1;
        let subNextUrl = href;
        const subPageVisited = new Set();
        while (subNextUrl && subPage <= 20) {
          if (subPageVisited.has(subNextUrl)) break;
          subPageVisited.add(subNextUrl);
          let subPageHtml;
          try {
            subPageHtml = await httpGet(subNextUrl, 15000);
          } catch (e) {
            console.log(`  ↳ 获取失败: ${e.message}`);
            break;
          }
          const subNotices = extractNotices(subPageHtml, subNextUrl);
          console.log(`  ↳ 第${subPage}页: ${subNotices.length} 条`);

          for (const sub of subNotices) {
            if (visitedUrls.has(sub.href)) {
              process.stdout.write(`  ↳ ${sub.href} (已爬) ...\n`);
              continue;
            }
            visitedUrls.add(sub.href);
            process.stdout.write(`  ↳ ${sub.href} ... `);
            try {
              const subHtml = await httpGet(sub.href, 15000);
              const subArt = extractArticle(subHtml, sub.href);
              if (!subArt.publishTime && sub.date) subArt.publishTime = sub.date;
              if (cutoffDate && subArt.publishTime && subArt.publishTime < cutoffDate) {
                console.log('跳过（已过期）');
                continue;
              }
              if (savedSet.has(sub.href)) {
                console.log('已保存');
                continue;
              }
              const record = buildRecord(sub.href, subArt);
              fs.appendFileSync(savePath, JSON.stringify(record) + '\n', 'utf8');
              savedSet.add(sub.href);
              saved++;
              console.log(`✅ ${record.publishTime || '(无日期)'} | ${record.title.slice(0, 40)}`);
            } catch (e) {
              console.log(`❌ ${e.message}`);
            }
          }

          // 找子列表页下一页
          const subPagination = [...subPageHtml.matchAll(/href=["']([^"']*\/list(\d+)\.htm)["']/gi)];
          const subPageNums = subPagination.map(m => parseInt(m[2])).filter(n => n > subPage);
          if (subPageNums.length > 0) {
            const nextSub = Math.min(...subPageNums);
            subNextUrl = baseParsed.origin + basePath + `list${nextSub}.htm`;
          } else if (subPage === 1) {
            subNextUrl = baseParsed.origin + basePath + `list${subPage + 1}.htm`;
          } else {
            subNextUrl = null;
          }
          subPage++;
          if (subNextUrl) await new Promise(r => setTimeout(r, 500));
        }
        continue;
      }

      // 是文章页 → 检查是否已爬过
      if (savedSet.has(href)) {
        console.log('已保存');
        continue;
      }

      // 是文章页 → 提取正文
      const art = extractArticle(artHtml, href);
      // 如果列表页有日期而文章页没有，用列表页的
      if (!art.publishTime && date) art.publishTime = date;

      // 时间过滤（文章页可能也无日期）
      if (cutoffDate && art.publishTime && art.publishTime < cutoffDate) {
        console.log('跳过（已过期）');
        continue;
      }

      const record = buildRecord(href, art);
      fs.appendFileSync(savePath, JSON.stringify(record) + '\n', 'utf8');
      savedSet.add(href);
      saved++;
      console.log(`✅ ${record.publishTime || '(无日期)'} | ${record.title.slice(0, 40)}`);
    } catch (e) {
      console.log(`❌ ${e.message}`);
    }

    if (i < allNotices.length - 1) {
      await new Promise(r => setTimeout(r, 300));
    }
  }

  console.log(`\n== 完成 ==`);
  console.log(`共处理 ${allNotices.length} 条，保存 ${saved} 条`);
  console.log(`保存到: ${savePath}`);

  return { notices: allNotices, saved, savePath };
}

/**
 * 验证策略的每个入口是否可爬取的通知列表页。
 * 对每 entry URL 实测抓取，用 isNotificationListPage 判定，返回结构化报告。
 * 供策略 Agent 生成后自检、据反馈修正。
 * @param {string} strategyPath - 策略 JSON 文件路径
 * @returns {string} 验证报告文本
 */
async function verifyStrategy(strategyPath) {
  const fs = require('fs');
  let strategy;
  try {
    strategy = JSON.parse(fs.readFileSync(strategyPath, 'utf8'));
  } catch (e) {
    return `❌ 无法读取策略 ${strategyPath}: ${e.message}`;
  }

  const entries = strategy.entries || [];
  if (entries.length === 0) return '⚠️ 策略无 entries';

  const lines = [`=== 策略验证报告: ${strategy.meta?.domain || strategyPath} ===`];
  let okCount = 0;

  for (const entry of entries) {
    const url = entry.url;
    const name = entry.name || url;
    try {
      const html = await httpGet(url, 15000);
      const type = entry.type;
      const isList = isNotificationListPage(html, type);
      const notices = extractNotices(html, url);
      if (isList) {
        okCount++;
        lines.push(`✅ ${name}: 列表页 ✓ (发现 ${notices.length} 条, type=${type})`);
      } else {
        const title = (html.match(/<title>([^<]*)<\/title>/i) || [])[1] || '';
        lines.push(`⚠️ ${name}: 非列表页 (title="${(title||'').slice(0,30)}", notices=${notices.length})`);
      }
    } catch (e) {
      lines.push(`❌ ${name}: 抓取失败 (${e.message})`);
    }
  }

  lines.push(`\n结果: ${okCount}/${entries.length} 入口可爬取`);
  return lines.join('\n');
}

// ============================================================
// 全站自动发现爬取
// ============================================================

/**
 * 从页面 HTML 中提取同域名的内部链接
 */
function extractInternalLinks(html, baseUrl, domain) {
  const links = new Set();
  // 匹配各种 href 格式
  const hrefMatches = html.match(/href=["']([^"']+)["']/gi) || [];
  for (const match of hrefMatches) {
    const m = match.match(/href=["']([^"']+)["']/);
    if (!m) continue;
    let href = m[1];
    try {
      href = makeAbsolute(href, baseUrl);
      const parsed = new URL(href);
      if (parsed.hostname !== domain) continue;
      // 跳过媒体文件、静态资源、锚点
      if (/\.(jpg|jpeg|png|gif|svg|css|js|ico|pdf|zip|rar|woff|ttf|mp3|mp4|avi)($|\?|#)/i.test(parsed.pathname)) continue;
      // 跳过 javascript 和 mailto
      if (/^(javascript:|mailto:|tel:)/i.test(href)) continue;
      links.add(href);
    } catch {}
  }
  return links;
}

/**
 * 检查页面是否为通知列表页
 */
function isNotificationListPage(html, cmsType) {
  // 有策略时使用策略指定的类型判断（要求有合理数量，防止误判文章页为列表页）
  if (cmsType) {
    const threshold = { 'news_title': 3, 'link-title': 3, 'article_inline': 5, 'dataList': 1, 'news_date_arti': 2, 'li_fallback': 5 };
    const minCount = threshold[cmsType] || 3;
    if (cmsType === 'news_title') return (html.match(/class=["']news_title["']/gi) || []).length >= minCount;
    if (cmsType === 'link-title') return (html.match(/class=["']link-title["']/gi) || []).length >= minCount;
    if (cmsType === 'article_inline') return (html.match(/<a[^>]+href=["'][^"']+["'][^>]*>\s*[^<\s][^<]{4,50}?\s*<span[^>]*>\d{4}/gi) || []).length >= minCount;
    if (cmsType === 'dataList') return (html.match(/dataList\s*=\s*\[/gi) || []).length >= 1;
    if (cmsType === 'news_date_arti') return (html.match(/class=["'][^"']*news_date[^"']*["']/gi) || []).length >= 2;
    if (cmsType === 'li_fallback') return (html.match(/<li[^>]*>[\s\S]{1,200}?href=["'][^"']+["']/gi) || []).length >= 5;
  }

  // 默认启发式检测（无策略时）
  const newsTitleCount = (html.match(/class=["']news_title["']/gi) || []).length;
  const newsMetaCount = (html.match(/class=["']news_meta["']/gi) || []).length;
  if (newsTitleCount > 0 && newsMetaCount > 0 && newsMetaCount >= newsTitleCount * 0.5) return true;
  if (newsTitleCount > 10 && newsMetaCount === 0) return true;

  const linkTitleCount = (html.match(/class=["']link-title["']/gi) || []).length;
  const linkMetaCount = (html.match(/(?:class=["'][^"']*time[^"']*["']|class=["'][^"']*date[^"']*["']|class=["'][^"']*meta[^"']*["'])/gi) || []).length;
  if (linkTitleCount > 5 && linkMetaCount >= linkTitleCount * 0.3) return true;

  return false;
}

/**
 * 爬取整个站点，自动发现所有通知列表页并爬取
 * @param {string} rootUrl - 站点根 URL（如 https://cs.nju.edu.cn/）
 */
async function crawlSite(rootUrl, opts = {}) {
  const { maxDays = null, maxPages = 5, outputFile = null, forceStrategy = false } = opts;

  const cutoffDate = maxDays
    ? new Date(Date.now() - maxDays * 86400000).toISOString().slice(0, 10)
    : null;

  const parsedRoot = new URL(rootUrl);
  const domain = parsedRoot.hostname;

  // ---- 策略查询：首次爬取时自动分析生成策略 ----
  let strategy = forceStrategy ? null : getStrategy(domain);
  if (!strategy) {
    console.log(`\n== [策略] 未找到 ${domain} 的爬取策略，正在自动分析...`);
    strategy = await analyzeSite(rootUrl);
    if (!strategy) {
      console.error('[策略] 分析失败，回退到启发式多模式提取');
    } else {
      saveStrategy(domain, strategy);
      console.log(`[策略] 已保存策略（置信度 ${strategy.trust}%）`);
    }
  } else {
    console.log(`\n== 自动发现站点通知列表: ${rootUrl} (策略: ${strategy.listPage?.type || 'unknown'}, 置信度 ${strategy.trust}%) ==`);
  }
  if (cutoffDate) console.log(`  只爬 ${maxDays} 天内通知（${cutoffDate} 之后）`);
  console.log('');

  const visited = new Set();          // 已探索过的页面
  const listPages = new Set();         // 发现的列表页
  const savedSet = new Set();          // 已保存的文章 URL
  let explored = 0;
  const MAX_EXPLORE = 150;             // 最多探索 150 个页面以防耗时过长
  let totalSaved = 0;
  const savePath = path.join(DATA_DIR, outputFile || `site_${Date.now()}.jsonl`);

  // BFS 探索：先发现所有列表页
  const queue = [rootUrl];
  console.log('[发现] 正在探索站点结构...\n');

  while (queue.length > 0 && explored < MAX_EXPLORE) {
    const current = queue.shift();
    if (visited.has(current)) continue;
    if (!current.startsWith('http')) continue;
    visited.add(current);
    explored++;

    let html;
    try {
      html = await httpGet(current, 15000);
    } catch {
      continue;
    }

    const currentUrl = current;
    const isList = isNotificationListPage(html, strategy?.listPage?.type);

    if (isList) {
      listPages.add(current);
      const u = new URL(current);
      console.log(`  [列表] ${u.pathname}`);
    } else if (explored <= 30) {
      // 前 30 个页面详细显示
      const u = new URL(current);
      console.log(`  [探索] ${u.pathname}`);
    }

    // 提取同域名链接加入队列（限制队列总大小）
    if (!isList || listPages.size < 50) {
      const links = extractInternalLinks(html, current, domain);
      for (const link of links) {
        if (!visited.has(link) && queue.length < 500) {
          queue.push(link);
        }
      }
    }

    await new Promise(r => setTimeout(r, 200));
  }

  console.log(`\n发现 ${listPages.size} 个通知列表页，开始爬取...\n`);

  // 依次爬取每个列表页
  const listPageArray = [...listPages];
  for (let i = 0; i < listPageArray.length; i++) {
    const listUrl = listPageArray[i];
    const u = new URL(listUrl);
    console.log(`\n=== [${i + 1}/${listPageArray.length}] ${u.pathname} ===`);

    const result = await crawlSiteListPage(listUrl, {
      cutoffDate,
      maxPages,
      visited,
      savedSet,
      savePath,
    });
    totalSaved += result.saved;
  }

  console.log(`\n== 完成 ==`);
  console.log(`共爬取 ${listPages.size} 个列表页，保存 ${totalSaved} 条`);
  console.log(`保存到: ${savePath}`);

  return { listPages: listPageArray, saved: totalSaved, savePath };
}

/**
 * 爬取单个站点的列表页（被 crawlSite 调用）
 */
async function crawlSiteListPage(listUrl, opts) {
  const { cutoffDate, maxPages, visited, savedSet, savePath } = opts;

  const baseParsed = new URL(listUrl);
  const basePath = baseParsed.pathname.replace(/[^/]*$/, '');

  let page = 1;
  let nextUrl = listUrl;
  let allNotices = [];
  let subPageVisited = new Set();

  while (page <= maxPages && nextUrl) {
    if (subPageVisited.has(nextUrl)) break;
    subPageVisited.add(nextUrl);

    let html;
    try {
      html = await httpGet(nextUrl, 15000);
    } catch {
      break;
    }

    const notices = extractNotices(html, nextUrl);

    // 日期过滤
    let newNotices = notices;
    if (cutoffDate) {
      newNotices = notices.filter(n => {
        if (!n.date) return true;
        return n.date >= cutoffDate;
      });
    }
    allNotices.push(...newNotices);

    // 找下一页
    nextUrl = null;
    if (page < maxPages) {
      const paginationRegex = new RegExp(`href=["']([^"']*${basePath}list(\\d+)\\.htm)["']`, 'gi');
      const matches = [...html.matchAll(paginationRegex)];
      const pageNums = matches.map(m => parseInt(m[2])).filter(n => n > page);
      if (pageNums.length > 0) {
        nextUrl = baseParsed.origin + basePath + `list${Math.min(...pageNums)}.htm`;
      } else if (page === 1) {
        nextUrl = baseParsed.origin + basePath + `list${page + 1}.htm`;
      }
    }

    page++;
    if (nextUrl) await new Promise(r => setTimeout(r, 500));
  }

  // 去重
  const unique = [];
  for (const n of allNotices) {
    if (!visited.has(n.href)) {
      visited.add(n.href);
      unique.push(n);
    }
  }

  console.log(`  列表页共 ${unique.length} 条（含重复 ${allNotices.length - unique.length} 条跳过）`);

  let saved = 0;
  for (let i = 0; i < unique.length; i++) {
    const { href, title: listTitle, date } = unique[i];
    process.stdout.write(`  [${i + 1}/${unique.length}] ${href} ... `);

    // 只处理同域名链接
    try {
      const hrefParsed = new URL(href);
      if (hrefParsed.hostname !== baseParsed.hostname) {
        console.log('[外链跳过]');
        continue;
      }
    } catch {
      console.log('[无效链接]');
      continue;
    }

    if (savedSet.has(href)) {
      console.log('已保存');
      continue;
    }

    try {
      const artHtml = await httpGet(href, 15000);

      // 判断是否为列表页（子列表页）
      const newsTitleCount = (artHtml.match(/class=["']news_title["']/gi) || []).length;
      const newsMetaCount = (artHtml.match(/class=["']news_meta["']/gi) || []).length;
      const isListPage = newsTitleCount > 0 && newsMetaCount > 0 && newsMetaCount >= newsTitleCount * 0.5;

      if (isListPage) {
        console.log('[列表页]');
        continue; // 子列表页暂不递归（防止嵌套爆炸）
      }

      const art = extractArticle(artHtml, href);
      if (!art.publishTime && date) art.publishTime = date;
      if (cutoffDate && art.publishTime && art.publishTime < cutoffDate) {
        console.log('跳过（已过期）');
        continue;
      }

      const record = buildRecord(href, art);
      fs.appendFileSync(savePath, JSON.stringify(record) + '\n', 'utf8');
      savedSet.add(href);
      saved++;
      console.log(`✅ ${record.publishTime || '(无日期)'} | ${record.title.slice(0, 40)}`);
    } catch (e) {
      console.log(`❌ ${e.message}`);
    }
    await new Promise(r => setTimeout(r, 300));
  }

  return { saved };
}

// ============================================================
// 单页面爬取
// ============================================================

async function crawlOne(url, useHttp = false) {
  try {
    console.log(`[爬取] ${url}`);
    const html = await httpGet(url, 15000);
    const art = extractArticle(html, url);
    const record = buildRecord(url, art);
    console.log(`  标题: ${record.title || '(无)'}`);
    console.log(`  时间: ${record.publishTime || '(无)'}`);
    console.log(`  内容: ${record.content.length} 字符`);
    console.log(`  标签: ${record.tags.join(', ') || '无'}`);
    return record;
  } catch (e) {
    console.error(`  错误: ${e.message}`);
    return null;
  }
}

// ============================================================
// 数据存储
// ============================================================

const DATA_DIR = path.join(__dirname, '..', '..', 'data');
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

function saveJSONL(data, filename = null) {
  const items = Array.isArray(data) ? data : [data];
  const saveFile = filename || 'all_records.jsonl';
  const savePath = path.join(DATA_DIR, saveFile);

  const existingUrls = new Set();
  if (fs.existsSync(savePath)) {
    const content = fs.readFileSync(savePath, 'utf8');
    for (const line of content.split('\n')) {
      if (line.trim()) {
        try { existingUrls.add(JSON.parse(line).url); } catch {}
      }
    }
  }

  const newItems = items.filter(item => !existingUrls.has(item.url));
  if (newItems.length === 0) {
    console.log(`  [存储] 无新记录（全部重复）`);
    return { filePath: savePath, newCount: 0 };
  }

  const lines = newItems.map(item => JSON.stringify(item)).join('\n') + '\n';
  fs.appendFileSync(savePath, lines, 'utf8');
  console.log(`  [存储] 追加 ${newItems.length} 条（含 ${items.length - newItems.length} 条重复跳过）`);
  return { filePath: savePath, newCount: newItems.length };
}

function countRecords() {
  if (!fs.existsSync(DATA_DIR)) return 0;
  return fs.readdirSync(DATA_DIR).filter(f => f.endsWith('.jsonl')).reduce((sum, f) => {
    const content = fs.readFileSync(path.join(DATA_DIR, f), 'utf8');
    return sum + content.split('\n').filter(l => l.trim()).length;
  }, 0);
}

// ============================================================
// 命令行入口
// ============================================================

async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--help') || args.includes('-h')) {
    printHelp();
    return;
  }

  const useHttp = args.includes('--http');
  const urlIdx = args.indexOf('--url');
  const noticesIdx = args.indexOf('--notices');
  const siteIdx = args.indexOf('--site');
  const daysIdx = args.indexOf('--days');
  const maxPagesIdx = args.indexOf('--max-pages');
  const outputIdx = args.indexOf('--output');

  // --list-strategies  查看已存储的爬取策略
  if (args.includes('--list-strategies')) {
    const list = listStrategies();
    const drafts = list.filter(s => s.isDraft);
    const confirmed = list.filter(s => !s.isDraft);

    if (list.length === 0) {
      console.log('尚无存储的策略。\n');
    } else {
      if (confirmed.length > 0) {
        console.log('\n已确认的策略:\n');
        for (const s of confirmed) {
          console.log(`  ${s.domain}`);
          console.log(`    名称: ${s.siteName}  |  入口: ${s.entryCount}  |  更新时间: ${s.updated || s.detected}`);
        }
      }
      if (drafts.length > 0) {
        console.log('\n草稿策略（待确认）:\n');
        for (const s of drafts) {
          console.log(`  ${s.domain} [草稿]`);
          console.log(`    名称: ${s.siteName}  |  入口: ${s.entryCount}  |  发现时间: ${s.detected}`);
        }
      }
      console.log('');
    }
    return;
  }

  // --confirm <domain>  确认草稿并开始爬取
  const confirmIdx = args.indexOf('--confirm');
  if (confirmIdx !== -1 && args[confirmIdx + 1]) {
    const domain = args[confirmIdx + 1];
    console.log(`\n== 确认草稿策略: ${domain} ==`);

    const strategy = confirmDraft(domain);
    if (!strategy) {
      console.error('[错误] 草稿确认失败，请检查草稿文件是否存在且格式正确');
      return;
    }

    console.log('[确认] 草稿已转为正式策略，开始爬取...');
    // 使用确认后的策略爬取
    if (strategy.entries && strategy.entries.length > 0) {
      for (const entry of strategy.entries) {
        if (entry.url) {
          console.log(`\n=== 爬取入口: ${entry.name} ===`);
          await crawlNotices(entry.url, {
            maxDays: daysIdx !== -1 && args[daysIdx + 1] ? parseInt(args[daysIdx + 1]) : null,
            maxPages: maxPagesIdx !== -1 && args[maxPagesIdx + 1] ? parseInt(args[maxPagesIdx + 1]) : 5,
          });
        }
      }
    }
    return;
  }

  // --re-discover <domain> [url]  强制重新发现（删除旧策略 + AI探索）
  const rediscoverIdx = args.indexOf('--re-discover');
  if (rediscoverIdx !== -1 && args[rediscoverIdx + 1]) {
    const domain = args[rediscoverIdx + 1];
    const url = args[rediscoverIdx + 2] || `https://${domain}/`;

    console.log(`\n== 强制重新发现 ${domain} ==`);
    deleteStrategy(domain);

    console.log('[探索] 开始探索网站结构...');
    const result = await exploreSiteSimple(url, { forceStrategy: false });
    if (result.hasInProgress) {
      console.log(`\n${result.message}`);
      console.log('如需重新开始，请先删除 in-progress 文件或使用 --remove-strategy');
    } else if (result.success) {
      saveDraft(domain, buildDraftFromResult(result));
      console.log(`\n[探索] 草稿已保存至 data/strategies/${domain}.draft.json`);
      console.log('[探索] 请：');
      console.log('  1. 阅读草稿内容（data/strategies/' + domain + '.draft.json）');
      console.log('  2. 编辑修正');
      console.log('  3. 运行以下命令确认：');
      console.log('     node collector.js --confirm ' + domain);
    } else {
      console.error('[探索] 探索失败: ' + (result.error || '未知错误'));
    }
    return;
  }

  // --remove-strategy <domain>  删除策略
  const removeIdx = args.indexOf('--remove-strategy');
  if (removeIdx !== -1 && args[removeIdx + 1]) {
    const domain = args[removeIdx + 1];
    deleteStrategy(domain);
    return;
  }

  // --force-analyze <URL>  强制重新分析并生成策略
  const forceIdx = args.indexOf('--force-analyze');
  if (forceIdx !== -1 && args[forceIdx + 1]) {
    const url = args[forceIdx + 1];
    const domain = new URL(url).hostname;
    console.log(`\n== 强制重新分析 ${domain} ==`);
    const strategy = await analyzeSite(url);
    if (strategy) {
      saveStrategy(domain, strategy);
      console.log(`\n策略已保存（置信度 ${strategy.trust}%）`);
    } else {
      console.error('分析失败。');
    }
    return;
  }

  // --site <URL>  爬取整个站点（AI优先：先查策略→无则探索→生成草稿）
  if (siteIdx !== -1 && args[siteIdx + 1]) {
    const rootUrl = args[siteIdx + 1];
    const domain = new URL(rootUrl).hostname;
    const maxDays = daysIdx !== -1 && args[daysIdx + 1] ? parseInt(args[daysIdx + 1]) : null;
    const maxPages = maxPagesIdx !== -1 && args[maxPagesIdx + 1] ? parseInt(args[maxPagesIdx + 1]) : 5;
    const outputFile = outputIdx !== -1 && args[outputIdx + 1] ? args[outputIdx + 1] : null;
    const forceStrategy = args.includes('--force-strategy');

    // ---- AI优先策略：有策略则直接爬，无则AI探索生成草稿 ----
    if (!forceStrategy) {
      const existing = getStrategy(domain);
      if (existing) {
        console.log(`\n== 使用已有策略爬取 ${domain} ==`);
        console.log(`  站点: ${existing.meta?.siteName || domain}`);
        console.log(`  入口数: ${existing.entries?.length || 0}`);
        if (existing.entries && existing.entries.length > 0) {
          for (const entry of existing.entries) {
            if (entry.url) {
              console.log(`\n=== 爬取入口: ${entry.name} ===`);
              await crawlNotices(entry.url, { maxDays, maxPages });
            }
          }
        } else {
          // 兼容旧格式策略（无entries）
          await crawlSite(rootUrl, { maxDays, maxPages, outputFile, forceStrategy: true });
        }
        return;
      }

      // 无策略 → 委托 Python Agent 生成策略（--explore-only，不回调爬虫）
      const { spawnSync } = require('child_process');
      const agentScript = process.env.EXPLORER_AGENT_MAIN || path.resolve(__dirname, '..', '..', '..', 'explorer-agent', 'main.py');
      console.log(`\n== 委托 explorer-agent 生成策略: ${domain} ==`);
      const py = spawnSync('python', [agentScript, '--explore-only', rootUrl], {
        encoding: 'utf8',
        timeout: 120000,
        env: { ...process.env, STRATEGIES_DIR: path.resolve(__dirname, '..', '..', 'data', 'strategies') },
      });
      console.log(py.stdout);
      if (py.stderr) console.error('[Agent stderr]', py.stderr);
      // Agent 已写策略文件，重新加载
      const agentStrategy = getStrategy(domain);
      if (agentStrategy) {
        console.log(`\n== 使用 Agent 生成的策略爬取 ${domain} ==`);
        for (const entry of agentStrategy.entries || []) {
          if (entry.url) await crawlNotices(entry.url, { maxDays, maxPages });
        }
        return;
      }
      console.error('[Agent] 未生成策略，回退到启发式');
      await crawlSite(rootUrl, { maxDays, maxPages, outputFile, forceStrategy: true });
      return;
    }

    // --force-strategy: 强制使用启发式
    const result = await crawlSite(rootUrl, { maxDays, maxPages, outputFile, forceStrategy });
    return;
  }

  // --verify <策略JSON路径>  验证策略的每个入口是否为可爬取的通知列表页
  const verifyIdx = args.indexOf('--verify');
  if (verifyIdx !== -1 && args[verifyIdx + 1]) {
    const strategyPath = args[verifyIdx + 1];
    const report = await verifyStrategy(strategyPath);
    console.log(report);
    return;
  }

  // --notices <URL>  爬取通知列表
  if (noticesIdx !== -1 && args[noticesIdx + 1]) {
    const listUrl = args[noticesIdx + 1];
    const maxDays = daysIdx !== -1 && args[daysIdx + 1] ? parseInt(args[daysIdx + 1]) : null;
    const maxPages = maxPagesIdx !== -1 && args[maxPagesIdx + 1] ? parseInt(args[maxPagesIdx + 1]) : 5;
    const outputFile = outputIdx !== -1 && args[outputIdx + 1] ? args[outputIdx + 1] : null;

    const result = await crawlNotices(listUrl, { maxDays, maxPages, outputFile });
    return;
  }

  // --url <URL>  爬取单个页面
  if (urlIdx !== -1 && args[urlIdx + 1]) {
    const data = await crawlOne(args[urlIdx + 1]);
    if (data) saveJSONL(data);
    return;
  }

  // --stats  查看统计
  if (args.includes('--stats')) {
    console.log(`数据目录: ${DATA_DIR}`);
    console.log(`总记录数: ${countRecords()}`);
    return;
  }

  printHelp();
}

function printHelp() {
  console.log(`
蓝鲸U — 智能信息检索爬虫

用法:
  # AI优先探索流程（首次爬取新站点）
  node collector.js --site <网站URL>                AI探索 → 生成草稿 → 退出等待确认
  node collector.js --site https://cs.nju.edu.cn/  首次探索计算机学院
  node collector.js --confirm <domain>              确认草稿 → 转为正式策略 → 开始爬取

  # 后续爬取（已有策略）
  node collector.js --site <网站URL>                直接使用策略爬取，不触发AI

  # 强制重新发现
  node collector.js --re-discover <domain> [url]    删除旧策略，重新AI探索
  node collector.js --re-discover cs.nju.edu.cn    重新探索计算机学院

  # 其他命令
  node collector.js --list-strategies              列出所有已发现的站点策略
  node collector.js --remove-strategy <domain>     删除指定站点的策略
  node collector.js --force-analyze <URL>          强制使用启发式分析（生成正式策略）
  node collector.js --notices <URL>                爬取指定通知列表页
  node collector.js --url <URL>                   爬取单个页面
  node collector.js --stats                        查看数据统计
  node collector.js --help                         显示帮助

参数:
  --days <N>       只爬 N 天内的通知（默认无限制）
  --max-pages <N>  每个列表页最多爬 N 页（默认5）

示例 — 完整流程:
  # Step 1: 首次探索（生成草稿）
  node collector.js --site https://jw.nju.edu.cn/
  # → 生成草稿 data/strategies/jw.nju.edu.cn.draft.json
  # → 退出，等待用户编辑

  # Step 2: 用户编辑草稿（data/strategies/jw.nju.edu.cn.draft.json）

  # Step 3: 确认并爬取
  node collector.js --confirm jw.nju.edu.cn --days 365

示例 — 快速测试:
  # 强制使用启发式分析（不触发AI）
  node collector.js --site https://cs.nju.edu.cn/ --force-strategy

  # 爬取单个通知列表
  node collector.js --notices https://cs.nju.edu.cn/1702/list.htm --days 365

数据输出:
  默认保存到 standalone/data/notices_*.jsonl
  策略存储在 standalone/data/strategies/
`);
}

if (require.main === module) {
  main().catch(e => { console.error(e); process.exit(1); });
}

module.exports = {
  crawlOne, crawlNotices, verifyStrategy,
  httpGet, extractNotices, extractArticle,
  isNotificationListPage,
  buildRecord, saveJSONL, countRecords, DATA_DIR,
};
