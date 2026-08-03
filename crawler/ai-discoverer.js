/**
 * ai-discoverer.js — AI 驱动的网站策略探索器
 *
 * 核心流程：
 *  1. 抓取网站首页 + 主要导航页
 *  2. 将 HTML 结构发送给 LLM
 *  3. LLM 分析并输出网站信息入口列表（草稿 JSON）
 *  4. 用户编辑草稿 JSON
 *  5. 运行 --confirm 确认并开始爬取
 *
 * 依赖：../../src/agent/llm.js（Claude / OpenAI 接口）
 *
 * @deprecated 请使用 site-explorer.js 获取更完整的探索能力
 */

const https = require('https');
const path = require('path');

// ============================================================
// 工具函数
// ============================================================

function fetchHtml(url, timeout = 10000) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const opts = {
      hostname: u.hostname,
      path: u.pathname + u.search,
      method: 'GET',
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; NJU-Crawler/1.0)' },
    };
    const req = https.request(opts, res => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        const loc = new URL(res.headers.location, url).href;
        return resolve(fetchHtml(loc, timeout));
      }
      let d = ''; res.on('data', c => d += c); res.on('end', () => resolve(d));
    });
    req.on('error', reject);
    req.setTimeout(timeout, () => { req.destroy(); reject(new Error('timeout')); });
    req.end();
  });
}

function makeAbsolute(href, base) {
  if (!href) return null;
  try { return new URL(href, base).href; } catch { return null; }
}

function extractLinks(html, baseUrl) {
  const baseDomain = new URL(baseUrl).hostname;
  const links = new Set();
  const re = /href=["']([^"']+)["']/gi;
  let m;
  while ((m = re.exec(html)) !== null) {
    const href = makeAbsolute(m[1], baseUrl);
    if (!href) continue;
    try {
      const h = new URL(href);
      if (h.hostname !== baseDomain) continue; // 只保留同域名
      const p = h.pathname;
      // 过滤明显的非内容页
      if (p.endsWith('.pdf') || p.endsWith('.doc') || p.endsWith('.docx')) continue;
      if (p.includes('/images/') || p.includes('/css/') || p.includes('/js/')) continue;
      links.add(href);
    } catch { /* relative URL, skip */ }
  }
  return [...links];
}

function extractSiteName(html, domain) {
  const m = html.match(/<title[^>]*>([^<]+)<\/title>/i);
  if (m) return m[1].trim().split(/[_\-|–—\/]/)[0].replace(/\s+/g, '').trim();
  return domain;
}

// ============================================================
// LLM Prompt
// ============================================================

const SYSTEM_PROMPT = `你是一个专业的高校网站结构分析助手。

你的任务：分析一个高校子网站的 HTML，判断它的信息组织结构。

请仔细阅读提供的 HTML，分析：
1. 这是什么类型的页面（首页/通知列表/文章页/登录页）
2. 导航中有哪些子栏目
3. 哪些子栏目看起来是"通知公告"类型的列表页
4. 每个通知列表页的分页规律

输出格式（严格 JSON）：
{
  "siteType": "homepage|announcement|article|unknown",
  "siteName": "从页面标题提取的站点名称",
  "navigation": [
    {
      "name": "栏目名称，如'通知公告'",
      "url": "完整 URL",
      "isLikelyAnnouncement": true或false,
      "reason": "为什么你认为这是/不是通知列表"
    }
  ],
  "announcements": [
    {
      "name": "建议的通知集合名称，如'教务通知'",
      "url": "完整 URL",
      "cmsType": "news_title|link-title|dataList|article_inline|li|other",
      "paginationType": "listN|query|pathN|none",
      "paginationHint": "分页 URL 规律描述",
      "estimatedCount": "number（AI 估计的通知条数）",
      "notes": "任何补充说明，如'需要登录'、'有日期筛选'等"
    }
  ],
  "overallNotes": "整体备注"
}

规则：
- isLikelyAnnouncement：根据栏目名称（通知、公告、新闻、动态等）和页面结构判断
- 一个 URL 如果在 HTML 中有对应的列表内容块（新闻列表、公告列表），则 isLikelyAnnouncement=true
- 如果不确定，设为 false 并说明原因
- 只输出 JSON，不要其他文字`;

// ============================================================
// 主探索函数
// ============================================================

/**
 * 探索网站结构，生成草稿策略
 *
 * @param {string} siteUrl - 网站根 URL
 * @returns {Promise<object>} 草稿策略对象
 */
async function discoverSite(siteUrl) {
  const domain = new URL(siteUrl).hostname;
  console.log(`[AI探索] 正在分析 ${domain}...`);

  // Step 1: 抓取首页
  let homeHtml;
  try {
    homeHtml = await fetchHtml(siteUrl);
  } catch (e) {
    throw new Error(`无法获取首页: ${e.message}`);
  }

  // Step 2: 从导航提取子页面 URL（最多取 10 个）
  const candidates = extractLinks(homeHtml, siteUrl).slice(0, 10);

  // Step 3: 抓取候选子页面（前 3 个）
  const subPages = [];
  for (const url of candidates.slice(0, 3)) {
    try {
      const html = await fetchHtml(url);
      subPages.push({ url, html: html.slice(0, 5000) });
      console.log(`[AI探索] 已抓取: ${new URL(url).pathname}`);
    } catch (e) {
      console.log(`[AI探索] 抓取失败 ${url}: ${e.message}`);
    }
  }

  // Step 4: 构造发给 LLM 的上下文
  const siteName = extractSiteName(homeHtml, domain);
  const navSection = homeHtml.match(/<nav[^>]*>[\s\S]{1,5000}<\/nav>/i)?.[0] || homeHtml.slice(0, 3000);
  const context = `
=== 网站信息 ===
域名: ${domain}
站点名称: ${siteName}
首页路径: ${siteUrl}

=== 首页 HTML（前 3000 字符）===
${homeHtml.slice(0, 3000)}

=== 导航区域 HTML ===
${navSection.slice(0, 2000)}

${subPages.length > 0 ? `=== 子页面样本（各前 2000 字符）===\n` + subPages.map(p => `--- ${p.url} ---\n${p.html.slice(0, 2000)}`).join('\n') : ''}
`;

  // Step 5: 调用 LLM
  let llmResult;
  try {
    const { ask, CONFIG } = require('../../src/agent/llm');
    console.log(`[AI探索] 调用 ${CONFIG.mode}...`);

    const response = await ask(
      '请分析这个高校网站的结构，找出所有通知公告列表页面。',
      SYSTEM_PROMPT + '\n\n' + context
    );

    llmResult = JSON.parse(extractJson(response.content || ''));
    console.log(`[AI探索] LLM 返回: 发现 ${llmResult.announcements?.length || 0} 个信息入口`);
  } catch (e) {
    if (e.message.includes('JSON')) throw new Error(`LLM 返回格式错误: ${e.message}`);
    throw new Error(`LLM 调用失败: ${e.message}`);
  }

  // Step 6: 构造草稿
  const draft = buildDraft(domain, siteName, llmResult);
  return draft;
}

/**
 * 从 LLM 输出提取 JSON
 */
function extractJson(text) {
  let match = text.match(/```json\s*([\s\S]+?)\s*```/);
  if (match) return match[1].trim();
  match = text.match(/```\s*([\s\S]+?)\s*```/);
  if (match) return match[1].trim();
  match = text.match(/(\{[\s\S]+?\})/);
  if (match) return match[1].trim();
  throw new Error('无法从 LLM 输出中提取 JSON');
}

/**
 * 构造草稿策略对象
 */
function buildDraft(domain, siteName, llmResult) {
  const now = new Date().toISOString();

  const entries = (llmResult.announcements || []).map(a => ({
    name: a.name || '未命名栏目',
    url: a.url,
    type: a.cmsType || 'other',
    paginationType: a.paginationType || 'none',
    paginationHint: a.paginationHint || '',
    estimatedCount: a.estimatedCount || 0,
    notes: a.notes || '',
  }));

  return {
    meta: {
      domain,
      siteName: llmResult.siteName || siteName,
      discoveredAt: now,
      aiModel: 'claude/openai',
      status: 'draft',  // draft | confirmed
    },
    entries,
    pagination: entries.length > 0 ? {
      type: entries[0].paginationType,
      hint: entries[0].paginationHint,
    } : { type: 'none' },
    notes: llmResult.overallNotes || '',
    _raw: llmResult,
  };
}

module.exports = { discoverSite, fetchHtml, extractLinks };
