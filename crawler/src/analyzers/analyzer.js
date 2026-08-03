/**
 * 网页结构分析器 —— 启发式 + LLM 降级混合
 *
 * 工作流程:
 *  1. HTTP 抓取首页 + 若干子页面
 *  2. 检测 SPA（JS渲染）特征 → 有则标记需浏览器模式
 *  3. 检测 CMS 类型（news_title / link-title / dataList / article_inline 等）
 *  4. 多模式竞争提取，统计结果数量
 *  5. 结构有效性抽样质检 → 修正置信度
 *  6. 从 <title> 提取真实站点名
 *  7. 置信度 < 50 且配置了 LLM API 时，降级调用 agent-analyzer.js
 */

const https = require('https');
const path = require('path');

// ============================================================
// HTTP 工具
// ============================================================

function fetchHtml(url, timeout = 8000) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const opts = { hostname: u.hostname, path: u.pathname + u.search, method: 'GET', headers: { 'User-Agent': 'Mozilla/5.0' } };
    const req = https.request(opts, res => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return resolve(fetchHtml(res.headers.location, timeout));
      }
      let d = ''; res.on('data', c => d += c); res.on('end', () => resolve(d));
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    req.setTimeout(timeout, () => { req.destroy(); reject(new Error('timeout')); });
    req.end();
  });
}

// ============================================================
// SPA 检测
// ============================================================

const SPA_INDICATORS = [
  /dataList\s*=\s*\[/i,
  /window\.__NUXT__/i,
  /window\.__INITIAL_STATE__/i,
  /window\.nuxt\s*=/i,
  /<script[^>]+type="module"/i,
];

function detectSPA(html) {
  return SPA_INDICATORS.some(r => r.test(html));
}

// ============================================================
// CMS 类型检测
// ============================================================

function detectCMSType(html) {
  const results = [];

  const nt = (html.match(/class=["']news_title["']/gi) || []).length;
  const nm = (html.match(/class=["']news_meta["']/gi) || []).length;
  const nl = (html.match(/class=["']news_date["']/gi) || []).length;
  if (nt > 0) results.push({ type: 'news_title', score: nt * (nm > 0 ? 2 : 0.5) + nl, data: { nt, nm, nl } });

  const lt = (html.match(/class=["']link-title["']/gi) || []).length;
  const lm = (html.match(/class=["'][^"']*(?:link-date|time|date)[^"']*["']/gi) || []).length;
  if (lt > 0) results.push({ type: 'link-title', score: lt * (lm > 0 ? 2 : 0.3), data: { lt, lm } });

  const dl = (html.match(/dataList\s*=\s*\[/gi) || []).length;
  const inf = (html.match(/infolist\s*:/gi) || []).length;
  if (dl > 0) results.push({ type: 'dataList', score: dl * 50 + inf * 30, data: { dl, inf } });

  const aiRe = /<a[^>]+href=["'][^"']+["'][^>]*>\s*[^<\s][^<]{4,50}?\s*<span[^>]*>\d{4}/gi;
  const ai = (html.match(aiRe) || []).length;
  if (ai > 0) results.push({ type: 'article_inline', score: ai * 3, data: { ai } });

  const nda = (html.match(/class=["'][^"']*news_date[^"']*["']/gi) || []).length;
  const nti = (html.match(/class=["'][^"']*news_arti[^"']*["']/gi) || []).length;
  if (nda > 0 && nti > 0) results.push({ type: 'news_date_arti', score: Math.min(nda, nti) * 10, data: { nda, nti } });

  const liRe = /<li[^>]*>[\s\S]{1,200}?href=["'][^"']+["'][^>]*>[\s\S]{1,200}?(?:\d{4}[-\/]\d{2}[-\/]\d{2}|\d{2}[-\/]\d{2}[-\/]\d{4})/gi;
  const li = (html.match(liRe) || []).length;
  if (li > 0) results.push({ type: 'li_fallback', score: li, data: { li } });

  results.sort((a, b) => b.score - a.score);
  return results.length > 0 ? results[0] : null;
}

// ============================================================
// 提取工具
// ============================================================

function makeAbsolute(href, base) {
  if (!href) return null;
  try { return new URL(href, base).href; } catch { return null; }
}

function extractByType(html, baseUrl, type) {
  const baseDomain = new URL(baseUrl).hostname;
  const results = [];

  if (type === 'news_title' || type === 'news_date_arti') {
    const titleRe = /<(?:span|div)[^>]*class=["']news_title["'][^>]*>\s*<a[^>]+href=["']([^"']+)["'][^>]*(?:title=["']([^"']+)["'])?[^>]*>([^<]+)<\/a>/gi;
    let m;
    while ((m = titleRe.exec(html)) !== null) {
      const href = makeAbsolute(m[1], baseUrl);
      const title = (m[2] || m[3] || '').replace(/<[^>]+>/g, '').trim();
      if (href && title) results.push({ href, title, date: null });
    }
    if (results.length > 0) return results;

    const altRe = /<div[^>]+class=["'][^"']*news_date[^"']*["'][^>]*>([^<]+)<\/div>[\s\S]{0,200}?<div[^>]+class=["'][^"']*news_arti[^"']*["'][^>]*>[\s\S]{0,50}?<(?:span|div)[^>]+class=["']news_title["'][^>]*>([^<]+)<\/(?:span|div)>/gi;
    while ((m = altRe.exec(html)) !== null) {
      const title = m[2].replace(/<[^>]+>/g, '').trim();
      if (title && title.length >= 4) results.push({ href: null, title, date: m[1].trim() });
    }
  }

  if (type === 'link-title') {
    const re = /<span[^>]+class=["']link-title["'][^>]*>\s*<a[^>]+href=["']([^"']+)["'][^>]*>([^<]+)<\/a>/gi;
    while ((m = re.exec(html)) !== null) {
      const href = makeAbsolute(m[1], baseUrl);
      const title = (m[2] || '').replace(/<[^>]+>/g, '').trim();
      if (!href || !title || title.length < 4) continue;
      try { if (new URL(href).hostname !== baseDomain) continue; } catch { /* ok */ }
      const extKw = ['研究中心', '研究所', '研究院', '委员会', '编辑部', '基地', '实验室', '学会', '协会', '办公室'];
      if (extKw.some(k => title.includes(k)) && title.length < 15) continue;
      results.push({ href, title, date: null });
    }
  }

  if (type === 'article_inline') {
    const re = /<a[^>]+href=["']([^"']+)["'][^>]*>\s*([^<\s][^<]{4,50}?)\s*(?:<span[^>]*>([^<\s][^<]{4,20})?<\/span>)?/gi;
    while ((m = re.exec(html)) !== null) {
      const href = makeAbsolute(m[1], baseUrl);
      if (!href || href.includes('list.htm') || href.includes('javascript:')) continue;
      const title = m[2].replace(/<[^>]+>/g, '').trim();
      if (!title || title.length < 6) continue;
      results.push({ href, title, date: m[3] ? m[3].replace(/<[^>]+>/g, '').trim() : null });
    }
  }

  if (type === 'li_fallback') {
    const re = /<li[^>]*>([\s\S]{1,300}?href=["']([^"']+)["'][^>]*>)[\s\S]{1,200}?(?:(\d{4}[-\/]\d{2}[-\/]\d{2}|\d{2}[-\/]\d{2}[-\/]\d{4}))/gi;
    while ((m = re.exec(html)) !== null) {
      const href = makeAbsolute(m[2], baseUrl);
      if (!href || href.includes('list.htm') || href.includes('javascript:')) continue;
      const ctx = m[1];
      const tm = ctx.match(/>([^<]{4,60}?)<\/a>/);
      const title = tm ? tm[1].replace(/<[^>]+>/g, '').trim() : '';
      if (title && title.length >= 4) results.push({ href, title, date: null });
    }
  }

  if (type === 'dataList') {
    const dlRe = /dataList\s*=\s*(\[[\s\S]+?\]\s*)/gi;
    while ((m = dlRe.exec(html)) !== null) {
      const raw = m[1];
      const objRe = /\{[^}]*(?:listtitle|title|href|datetime|infolist)[^}]*\}/gi;
      let om;
      while ((om = objRe.exec(raw)) !== null) {
        const obj = om[0];
        const hrefMatch = obj.match(/href\s*:\s*["']([^"']+)["']/);
        const titleMatch = obj.match(/(?:listtitle|title)\s*:\s*["']([^"']+)["']/);
        const href = hrefMatch ? makeAbsolute(hrefMatch[1], baseUrl) : null;
        const title = titleMatch ? titleMatch[1] : '';
        if (href && title) results.push({ href, title, date: null });
      }
    }
  }

  return results;
}

// ============================================================
// 站点名称提取
// ============================================================

function extractSiteName(html, defaultName) {
  // 从 <title> 提取
  const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
  if (titleMatch) {
    const raw = titleMatch[1].trim();
    // 取第一个分隔符前的部分，去掉常见后缀
    const cleaned = raw.split(/[_\-|–—]/)[0].replace(/\s*[-_]\s*.+$/, '').trim();
    if (cleaned && cleaned.length >= 2 && cleaned.length <= 30) return cleaned;
  }
  // 从 meta description 提取
  const descMatch = html.match(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)["']/i) ||
                    html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+name=["']description["']/i);
  if (descMatch) {
    const d = descMatch[1].trim();
    if (d.length >= 2 && d.length <= 30) return d;
  }
  return defaultName;
}

// ============================================================
// 分页检测
// ============================================================

function detectPagination(html, baseUrl) {
  const listN = html.match(/href=["']([^"']*\/list)(\d+)?\.htm["']/gi) || [];
  const nums = listN.map(m => { const r = m.match(/\d+/); return r ? parseInt(r[0]) : 1; }).filter(n => n > 1);
  if (nums.length > 0) {
    const base = listN[0].match(/href=["']([^"']+)["']/)[1].replace(/\d+\.htm$/, '');
    return { type: 'listN', baseUrl: makeAbsolute(base, baseUrl), pattern: base + '{page}.htm' };
  }

  const pageN = html.match(/href=["'][^"']*page[_\.]?(\d+)[^"']*["']/gi) || [];
  if (pageN.length > 2) {
    const sample = pageN[0].match(/href=["']([^"']+)["']/)[1];
    return { type: 'query', baseUrl: baseUrl, pattern: sample.replace(/\d+/, '{page}') };
  }

  const pathN = html.match(/href=["'](\/\d+\/list\.htm)["']/gi) || [];
  if (pathN.length > 2) {
    return { type: 'pathN', baseUrl: baseUrl, pattern: '{page}/list.htm' };
  }

  return { type: 'none', baseUrl: baseUrl, pattern: null };
}

// ============================================================
// 置信度质量分
// ============================================================

function calculateQualityScore(results) {
  if (results.length === 0) return 0;
  const sample = results.slice(0, 5);
  let score = 0;
  let total = 0;
  for (const r of sample) {
    total += 3;
    if (r.date) score += 1;
    if (r.title && r.title.length >= 6) score += 1;
    if (r.href && r.href.includes('.htm')) score += 1;
  }
  return Math.round((score / total) * 20);
}

// ============================================================
// 主分析函数
// ============================================================

async function analyzeSite(rootUrl, opts = {}) {
  const domain = new URL(rootUrl).hostname;
  const { forceBrowser = false } = opts;

  console.log(`\n[分析] 正在分析 ${domain}...`);

  let homeHtml;
  try {
    homeHtml = await fetchHtml(rootUrl);
  } catch (e) {
    console.error(`[分析] 首页获取失败: ${e.message}`);
    return null;
  }

  // ---- SPA 检测 ----
  const isSPA = detectSPA(homeHtml);
  if (isSPA) {
    console.log(`[分析] 检测到 SPA 特征（JS渲染），需要浏览器模式`);
    console.log(`[分析] 建议使用 --http 配合浏览器服务，或手动分析`);
  }

  // ---- 从 <title> 提取站点名 ----
  const siteName = extractSiteName(homeHtml, domain);
  console.log(`[分析] 站点名称: ${siteName}`);

  // ---- 收集页面 ----
  const pages = [{ url: rootUrl, html: homeHtml, cmsType: detectCMSType(homeHtml) }];
  console.log(`[分析] CMS 类型: ${pages[0].cmsType?.type || 'unknown'} (score=${pages[0].cmsType?.score?.toFixed(0)})`);

  const listPageLinks = [];
  const navRe = /href=["']([^"']*\/list\d*\.htm[^"']*)["']/gi;
  let m;
  while ((m = navRe.exec(homeHtml)) !== null) {
    const url = makeAbsolute(m[1], rootUrl);
    if (url && !listPageLinks.includes(url)) listPageLinks.push(url);
  }
  const subPages = listPageLinks.slice(0, 3);
  for (const url of subPages) {
    try {
      const html = await fetchHtml(url);
      const cms = detectCMSType(html);
      pages.push({ url, html, cmsType: cms });
    } catch { /* 忽略 */ }
  }

  // ---- 确定最终 CMS 类型 ----
  const typeCount = {};
  for (const p of pages) {
    if (p.cmsType) typeCount[p.cmsType.type] = (typeCount[p.cmsType.type] || 0) + p.cmsType.score;
  }
  const bestType = Object.entries(typeCount).sort((a, b) => b[1] - a[1])[0];
  const finalType = bestType ? bestType[0] : 'unknown';
  console.log(`[分析] 最终类型: ${finalType}`);

  // ---- 多模式竞争提取 ----
  let bestPage = null;
  let bestResults = [];
  for (const p of pages) {
    const results = extractByType(p.html, p.url, finalType);
    if (results.length > bestResults.length) {
      bestResults = results;
      bestPage = p;
    }
  }
  console.log(`[分析] 最优提取: ${bestResults.length} 条（来自 ${bestPage?.url}）`);

  // ---- 分页检测 ----
  const pagination = bestPage ? detectPagination(bestPage.html, bestPage.url) : { type: 'none' };
  console.log(`[分析] 分页类型: ${pagination.type}`);

  // ---- 置信度计算 ----
  let trust = 30;
  if (bestResults.length >= 5) trust += 20;
  if (bestResults.length >= 20) trust += 20;
  if (finalType !== 'unknown') trust += 15;
  if (bestPage && bestPage.url !== rootUrl) trust += 10;

  // 质量分（抽样检查提取结果的结构有效性）
  const qualityBonus = calculateQualityScore(bestResults);
  trust += qualityBonus;

  trust = Math.min(95, trust);
  console.log(`[分析] 基础置信度: ${trust - qualityBonus}% + 质量分 ${qualityBonus}% = 总计 ${trust}%`);

  const strategy = {
    version: 1,
    siteName,
    trust,
    strategySource: 'heuristic',
    isSPA,
    listPage: {
      type: finalType,
      filterKeywords: ['学院概览', '学院简介', '师资队伍', '科学研究', '人才培养', '党的建设', '首页', 'English']
    },
    article: {
      titleMatch: 'title|.article-title|h1',
      contentMatch: 'article|.article-content|.content|#articleContent',
      timeMatch: 'time|.news-date|.date',
      attachmentPattern: '/_upload/article/files/'
    },
    pagination
  };

  // ---- LLM 降级：当置信度 < 50 且有 API 时 ----
  if (trust < 50) {
    try {
      const { analyzeWithLLM } = require('./agent-analyzer');
      const { CONFIG } = require('../../../src/agent/llm');
      if (CONFIG.mode !== 'local' && (CONFIG.mode === 'claude' && CONFIG.anthropicKey || CONFIG.mode === 'openai' && CONFIG.openaiKey)) {
        console.log(`[分析] 启发式置信度 ${trust}% < 50%，降级到 LLM 分析...`);
        const llmStrategy = await analyzeWithLLM(rootUrl, homeHtml);
        if (llmStrategy && llmStrategy.confidence > trust) {
          console.log(`[分析] LLM 置信度 ${llmStrategy.confidence}% > 当前 ${trust}%，采纳 LLM 结果`);
          Object.assign(strategy, llmStrategy, { strategySource: 'llm' });
          strategy.trust = Math.min(95, llmStrategy.confidence || trust);
        }
      }
    } catch (e) {
      console.log(`[分析] LLM 降级跳过: ${e.message}`);
    }
  }

  console.log(`[分析] 最终置信度: ${strategy.trust}% (来源: ${strategy.strategySource})`);
  return strategy;
}

module.exports = { analyzeSite, fetchHtml, detectCMSType, detectSPA };
