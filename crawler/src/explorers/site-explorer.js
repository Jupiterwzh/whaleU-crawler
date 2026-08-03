/**
 * site-explorer.js — 独立网站探索Agent
 *
 * 多轮交互流程：
 * 1. AI抓取网站，列举发现的入口
 * 2. 用户选择/补充/确认/打断
 * 3. AI根据用户输入继续分析
 * 4. 重复直到用户确认或打断
 *
 * 使用方式：
 *   node site-explorer.js --url https://jw.nju.edu.cn/
 *   node site-explorer.js --continue jw.nju.edu.cn
 */

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

// ============================================================
// 项目上下文
// ============================================================

const PROJECT_CONTEXT = `
项目名称：南京大学通知公告智能爬虫
项目目标：自动发现、爬取、汇总南京大学各院系网站的通知公告

策略格式（v3）：
- 正式策略：data/strategies/{domain}.json
- 草稿策略：data/strategies/{domain}.draft.json
- 工作中：data/strategies/{domain}.in-progress.json

信息入口结构：
{
  "name": "栏目名称",
  "url": "完整URL",
  "type": "news_title|link-title|dataList|article_inline|li",
  "paginationType": "listN|query|pathN|none",
  "paginationHint": "分页URL规律"
}
`;

// ============================================================
// Agent System Prompt（用于AI分析）
// ============================================================

const ANALYZE_PROMPT = `你是一个专业的高校网站结构分析助手。

给定一个网站的HTML和导航结构，分析：
1. 识别所有通知公告列表页入口
2. 判断每个入口的CMS类型（news_title/link-title/dataList/article_inline/li）
3. 检测分页URL规律（listN/query/pathN/none）
4. 评估每个入口的可靠性和预计通知数量

请用JSON格式输出：
{
  "siteName": "站点名称",
  "entries": [
    {
      "name": "建议的栏目名称",
      "url": "完整URL",
      "cmsType": "news_title|link-title|dataList|article_inline|li",
      "paginationType": "listN|query|pathN|none",
      "paginationHint": "分页规律描述",
      "estimatedCount": 数字,
      "reasoning": "判断理由"
    }
  ],
  "overallNotes": "整体备注"
}`;

// ============================================================
// HTTP工具
// ============================================================

function fetchHtml(url, timeout = 10000) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const lib = u.protocol === 'https:' ? https : http;
    const opts = {
      hostname: u.hostname,
      path: u.pathname + u.search,
      method: 'GET',
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; NJU-Crawler/1.0)' },
    };
    const req = lib.request(opts, res => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return resolve(fetchHtml(res.headers.location, timeout));
      }
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => resolve(d));
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

function extractSiteName(html, domain) {
  const m = html.match(/<title[^>]*>([^<]+)<\/title>/i);
  if (m) return m[1].trim().split(/[_\-|–—\/]/)[0].replace(/\s+/g, '').trim();
  return domain;
}

// ============================================================
// LLM接口
// ============================================================

function getLLM() {
  try {
    const paths = [
      '../../../src/agent/llm',
      '../../src/agent/llm',
      path.join(__dirname, '../../../src/agent/llm'),
    ];
    for (const p of paths) {
      try {
        return require(p);
      } catch { /* try next */ }
    }
  } catch (e) { /* ignore */ }
  return null;
}

function extractJson(text) {
  let match = text.match(/```json\s*([\s\S]+?)\s*```/);
  if (match) return match[1].trim();
  match = text.match(/```\s*([\s\S]+?)\s*```/);
  if (match) return match[1].trim();
  match = text.match(/(\{[\s\S]+?\})/);
  if (match) return match[1].trim();
  throw new Error('无法从输出中提取JSON');
}

// ============================================================
// 文件路径
// ============================================================

function getDataDir() {
  return path.join(__dirname, '..', '..', 'data');
}

function getStrategiesDir() {
  const d = path.join(getDataDir(), 'strategies');
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
  return d;
}

function getInProgressPath(domain) {
  return path.join(getStrategiesDir(), `${domain}.in-progress.json`);
}

function getDraftPath(domain) {
  return path.join(getStrategiesDir(), `${domain}.draft.json`);
}

function getStrategyPath(domain) {
  return path.join(getStrategiesDir(), `${domain}.json`);
}

function checkInProgress(domain) {
  const p = getInProgressPath(domain);
  if (fs.existsSync(p)) {
    try {
      return JSON.parse(fs.readFileSync(p, 'utf8'));
    } catch { /* invalid file */ }
  }
  return null;
}

// ============================================================
// 核心分析函数（单次分析）
// ============================================================

async function analyzeSiteStructure(siteUrl, userHint) {
  const domain = new URL(siteUrl).hostname;
  const llm = getLLM();

  console.log(`\n[分析] 正在抓取 ${domain}...`);

  // 抓取首页
  let homeHtml;
  try {
    homeHtml = await fetchHtml(siteUrl);
  } catch (e) {
    throw new Error(`无法获取首页: ${e.message}`);
  }

  const siteName = extractSiteName(homeHtml, domain);
  console.log(`[分析] 站点名称: ${siteName}`);

  // 提取导航链接
  const navLinks = new Set();
  const linkRe = /href=["']([^"']+)["']/gi;
  let m;
  while ((m = linkRe.exec(homeHtml)) !== null) {
    const href = makeAbsolute(m[1], siteUrl);
    if (!href) continue;
    try {
      const h = new URL(href);
      if (h.hostname !== domain) continue;
      const p = h.pathname;
      if (p.endsWith('.pdf') || p.endsWith('.doc') || p.endsWith('.docx')) continue;
      if (p.includes('/images/') || p.includes('/css/') || p.includes('/js/')) continue;
      navLinks.add(href);
    } catch { /* skip */ }
  }

  // 抓取候选子页面
  const candidates = [...navLinks].slice(0, 10);
  const subPages = [];
  for (const url of candidates.slice(0, 5)) {
    try {
      const html = await fetchHtml(url);
      subPages.push({ url, html: html.slice(0, 3000) });
    } catch { /* skip */ }
  }

  // 构造上下文
  const userHintSection = userHint ? `\n=== 用户提示 ===\n${userHint}\n` : '';
  const context = `
=== 网站信息 ===
域名: ${domain}
站点名称: ${siteName}
首页: ${siteUrl}
${userHintSection}
=== 首页 HTML（前 3000 字符）===
${homeHtml.slice(0, 3000)}
=== 导航链接 ===
${candidates.slice(0, 15).map(u => '- ' + u).join('\n')}
${subPages.length > 0 ? `\n=== 子页面样本 ===\n` + subPages.map(p => `--- ${p.url} ---\n${p.html.slice(0, 1500)}`).join('\n') : ''}
`;

  // 调用LLM
  if (!llm) {
    throw new Error('LLM接口不可用（请配置 ANTHROPIC_API_KEY 或 OPENAI_API_KEY）');
  }

  const { ask, CONFIG } = llm;
  console.log(`[分析] 调用 ${CONFIG.mode}...`);

  const response = await ask(
    '请分析这个高校网站，找出所有通知公告列表页面入口。',
    ANALYZE_PROMPT + context
  );

  const content = response.content || '';
  let parsed;
  try {
    parsed = JSON.parse(extractJson(content));
  } catch (e) {
    throw new Error(`LLM返回格式错误: ${e.message}\n原始内容: ${content.slice(0, 200)}`);
  }

  console.log(`[分析] 发现 ${parsed.entries?.length || 0} 个入口`);

  return {
    domain,
    siteName: parsed.siteName || siteName,
    entries: (parsed.entries || []).map(e => ({
      name: e.name || '未命名',
      url: e.url,
      cmsType: e.cmsType || 'news_title',
      paginationType: e.paginationType || 'none',
      paginationHint: e.paginationHint || '',
      estimatedCount: e.estimatedCount || 0,
      reasoning: e.reasoning || '',
    })),
    notes: parsed.overallNotes || '',
    analyzedAt: new Date().toISOString(),
  };
}

// ============================================================
// 用户交互
// ============================================================

function createReadlineInterface() {
  return readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });
}

function askQuestion(rl, question) {
  return new Promise(resolve => {
    rl.question(question, answer => {
      resolve(answer.trim());
    });
  });
}

function parseUserInput(input, entries) {
  input = input.trim();

  // 确认保存
  if (input === '确认' || input === '确认' || input === 'save' || input === 'yes' || input === 'y') {
    return { action: 'confirm' };
  }

  // 打断暂存
  if (input === '打断' || input === '中断' || input === 'break' || input === 'stop') {
    return { action: 'break' };
  }

  // 帮助
  if (input === '帮助' || input === 'help' || input === '?') {
    return { action: 'help' };
  }

  // 列出所有入口（不选）
  if (input === '列表' || input === 'list') {
    return { action: 'list' };
  }

  // 数字选择（如 "1,2,3" 或 "1 2 3"）
  const numRe = /^[\d\s,]+$/;
  if (numRe.test(input)) {
    const nums = input.split(/[\s,]+/).map(n => parseInt(n.trim())).filter(n => n > 0 && n <= entries.length);
    if (nums.length > 0) {
      return { action: 'select', indices: nums };
    }
  }

  // 自然语言输入（作为补充或纠正）
  return { action: 'natural', text: input };
}

function formatEntries(entries) {
  if (!entries || entries.length === 0) {
    return '（未发现任何入口）';
  }

  let s = '';
  entries.forEach((e, i) => {
    const pagination = e.paginationType !== 'none' ? ` [分页:${e.paginationType}]` : '';
    const count = e.estimatedCount > 0 ? ` (约${e.estimatedCount}条)` : '';
    s += `  [${i + 1}] ${e.url}\n`;
    s += `      名称: ${e.name}${count}${pagination}\n`;
    if (e.reasoning) {
      s += `      说明: ${e.reasoning.slice(0, 50)}${e.reasoning.length > 50 ? '...' : ''}\n`;
    }
  });
  return s;
}

function formatSessionState(state) {
  const confirmedCount = state.selected.length;
  const pendingCount = state.entries.length - confirmedCount;

  let s = `\n========== 当前探索状态 ==========\n`;
  s += `站点: ${state.siteName} (${state.domain})\n`;
  s += `已选入口: ${confirmedCount} 个\n`;
  if (confirmedCount > 0) {
    state.selected.forEach(e => {
      s += `  ✓ ${e.name}: ${e.url}\n`;
    });
  }
  s += `待确认入口: ${pendingCount} 个\n`;
  s += `====================================\n`;
  return s;
}

// ============================================================
// 主流程
// ============================================================

async function runInteractiveSession(siteUrl, userHint, existingState) {
  const domain = new URL(siteUrl).hostname;
  const rl = createReadlineInterface();

  let state;
  if (existingState) {
    // 继续之前的探索
    state = existingState;
    console.log(`\n[续谈] 继续上次的探索会话`);
    console.log(formatSessionState(state));
  } else {
    // 新建探索
    console.log(`\n========== 网站探索Agent ==========`);
    console.log(`目标: ${domain}`);
    console.log(`提示: ${userHint || '（无）'}`);
    console.log(`====================================`);

    // 首次分析
    const result = await analyzeSiteStructure(siteUrl, userHint);
    state = {
      domain,
      siteName: result.siteName,
      url: siteUrl,
      entries: result.entries,
      selected: [],
      notes: result.notes,
      userHint: userHint,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
  }

  // 主循环
  while (true) {
    console.log(`\n${formatSessionState(state)}`);
    console.log(`=== 已发现的入口 (${state.entries.length}个) ===`);
    console.log(formatEntries(state.entries));

    console.log(`
操作说明：
  - 输入数字选择入口（如: 1,2,3 或 1 2 3）
  - 输入自然语言补充/纠正（如: "还有通知在/24751/list.htm"）
  - 输入 "确认" 保存策略
  - 输入 "打断" 暂存并退出
  - 输入 "帮助" 查看更多选项
`);

    const input = await askQuestion(rl, '\n请输入: ');
    console.log(''); // 换行

    if (!input || input === '退出' || input === 'exit' || input === 'quit') {
      console.log('[探索] 用户退出（未保存）');
      rl.close();
      return null;
    }

    const parsed = parseUserInput(input, state.entries);

    switch (parsed.action) {
      case 'confirm':
        // 保存策略
        console.log('[探索] 确认保存策略...');
        await saveStrategy(state);
        rl.close();
        return { success: true, state, action: 'saved' };

      case 'break':
        // 暂存并退出
        console.log('[探索] 打断，暂存进度...');
        await saveInProgress(state);
        rl.close();
        return { success: true, state, action: 'in-progress' };

      case 'help':
        console.log(`
=== 帮助 ===
支持的命令：
  数字      - 选择对应入口（如 1,2,3）
  自然语言  - 补充信息或纠正AI的分析
  确认      - 保存当前策略
  打断      - 暂存进度并退出
  列表      - 重新显示入口列表
  帮助      - 显示此帮助
  退出      - 不保存直接退出
`);
        break;

      case 'list':
        // 重新显示列表（已在上面显示）
        break;

      case 'select':
        // 用户选择了一些入口，标记为selected
        const selectedEntries = parsed.indices.map(i => state.entries[i - 1]).filter(Boolean);
        // 合并到selected（去重）
        for (const e of selectedEntries) {
          if (!state.selected.some(s => s.url === e.url)) {
            state.selected.push(e);
          }
        }
        console.log(`[探索] 已选择 ${selectedEntries.length} 个入口`);
        state.updatedAt = new Date().toISOString();
        break;

      case 'natural':
        // 自然语言输入：可能是补充入口、纠正错误、或进一步分析请求
        console.log(`[探索] 分析用户输入: ${parsed.text}`);

        // 检查是否包含URL
        const urlMatch = parsed.text.match(/https?:\/\/[^\s]+/) || parsed.text.match(/\/[^\s]+\.htm/);
        if (urlMatch) {
          // 用户补充了URL，需要重新分析
          console.log('[探索] 检测到URL补充，重新分析...');
          try {
            const newUrl = urlMatch[0].startsWith('http') ? urlMatch[0] : new URL(urlMatch[0], state.url).href;
            const newHtml = await fetchHtml(newUrl);
            const newEntries = detectEntriesFromHtml(newHtml, newUrl, newUrl);

            // 合并新入口
            let added = 0;
            for (const e of newEntries) {
              if (!state.entries.some(existing => existing.url === e.url)) {
                state.entries.push(e);
                added++;
              }
            }
            console.log(`[探索] 添加了 ${added} 个新入口`);
          } catch (e) {
            console.log(`[探索] 抓取补充URL失败: ${e.message}`);
          }
        } else {
          // 用户可能是纠正或提供更多信息，重新分析
          console.log('[探索] 根据用户输入重新分析...');
          try {
            const result = await analyzeSiteStructure(state.url, parsed.text);

            // 合并结果
            let added = 0;
            for (const e of result.entries) {
              if (!state.entries.some(existing => existing.url === e.url)) {
                state.entries.push(e);
                added++;
              }
            }
            console.log(`[探索] 更新完成，新增 ${added} 个入口`);
            state.notes = result.notes;
          } catch (e) {
            console.log(`[探索] 重新分析失败: ${e.message}`);
          }
        }

        state.updatedAt = new Date().toISOString();
        break;
    }
  }
}

// ============================================================
// 辅助分析（无LLM时使用启发式）
// ============================================================

function detectEntriesFromHtml(html, baseUrl, pageTitle) {
  const entries = [];
  const domain = new URL(baseUrl).hostname;

  // 查找list页面
  const listRe = /href=["']([^"']*\/list\d*\.htm[^"']*)["']/gi;
  let m;
  const listUrls = new Set();
  while ((m = listRe.exec(html)) !== null) {
    const url = makeAbsolute(m[1], baseUrl);
    if (url && new URL(url).hostname === domain) {
      listUrls.add(url);
    }
  }

  // 检测每个list页面的CMS类型
  for (const url of listUrls) {
    const pathMatch = url.match(/\/(\d+)\/list/);
    const pageNum = pathMatch ? pathMatch[1] : '';

    entries.push({
      name: `列表页 ${pageNum}`.trim(),
      url: url,
      cmsType: 'news_title', // 默认
      paginationType: 'listN',
      paginationHint: url.replace(/list\d*\.htm/, 'list{page}.htm'),
      estimatedCount: 0,
      reasoning: '从HTML中发现的list链接',
    });
  }

  return entries;
}

async function analyzeWithHeuristics(siteUrl) {
  const domain = new URL(siteUrl).hostname;
  console.log(`[启发式] 正在分析 ${domain}...`);

  const homeHtml = await fetchHtml(siteUrl);
  const siteName = extractSiteName(homeHtml, domain);
  const entries = detectEntriesFromHtml(homeHtml, siteUrl, siteName);

  return {
    domain,
    siteName,
    entries,
    notes: '使用启发式分析（无LLM）',
    analyzedAt: new Date().toISOString(),
  };
}

// ============================================================
// 非交互式探索（供collector.js使用）
// ============================================================

async function exploreSiteSimple(siteUrl, opts = {}) {
  const domain = new URL(siteUrl).hostname;
  const { forceStrategy = false } = opts;

  // 检查in-progress
  const inProgress = checkInProgress(domain);
  if (inProgress) {
    return {
      success: true,
      hasInProgress: true,
      domain,
      message: `发现未完成的探索会话，请使用 node site-explorer.js --continue ${domain} 继续`,
    };
  }

  // 检查LLM
  const llm = getLLM();
  const llmAvailable = llm && llm.CONFIG && llm.CONFIG.mode !== 'local' &&
    ((llm.CONFIG.mode === 'claude' && llm.CONFIG.anthropicKey) ||
     (llm.CONFIG.mode === 'openai' && llm.CONFIG.openaiKey));

  if (forceStrategy || !llmAvailable) {
    // 使用启发式
    console.log(`[探索] 使用启发式分析 ${domain}...`);
    const result = await analyzeWithHeuristics(siteUrl);
    return {
      success: result.entries.length > 0,
      mode: 'heuristic',
      domain,
      siteName: result.siteName,
      entries: result.entries,
      notes: result.notes,
    };
  }

  // 使用LLM分析
  console.log(`[探索] 使用AI探索 ${domain}...`);
  try {
    const result = await analyzeSiteStructure(siteUrl, null);
    return {
      success: result.entries.length > 0,
      mode: 'llm',
      domain: result.domain,
      siteName: result.siteName,
      entries: result.entries,
      notes: result.notes,
    };
  } catch (e) {
    console.error(`[探索] AI探索失败: ${e.message}`);
    console.log(`[探索] 降级到启发式分析...`);
    const result = await analyzeWithHeuristics(siteUrl);
    return {
      success: result.entries.length > 0,
      mode: 'heuristic-fallback',
      domain,
      siteName: result.siteName,
      entries: result.entries,
      notes: result.notes + ' (AI失败后降级)',
      error: e.message,
    };
  }
}

// ============================================================
// 保存文件
// ============================================================

async function saveInProgress(state) {
  const filepath = getInProgressPath(state.domain);
  const data = {
    meta: {
      domain: state.domain,
      siteName: state.siteName,
      status: 'in-progress',
      createdAt: state.createdAt,
      updatedAt: new Date().toISOString(),
      userHint: state.userHint,
    },
    entries: state.entries,
    selected: state.selected,
    notes: state.notes,
    url: state.url,
  };
  fs.writeFileSync(filepath, JSON.stringify(data, null, 2), 'utf8');
  console.log(`[保存] 已暂存到 ${filepath}`);
}

async function saveStrategy(state) {
  const domain = state.domain;
  const now = new Date().toISOString();

  // 合并selected和entries（selected优先）
  const finalEntries = state.selected.length > 0
    ? state.selected
    : state.entries;

  const strategy = {
    meta: {
      domain,
      siteName: state.siteName,
      strategyVersion: 1,
      created: now,
      updated: now,
    },
    entries: finalEntries.map(e => ({
      name: e.name,
      url: e.url,
      type: e.cmsType || 'news_title',
      paginationType: e.paginationType || 'none',
      paginationHint: e.paginationHint || '',
      estimatedCount: e.estimatedCount || 0,
      description: e.reasoning || '',
    })),
    pagination: finalEntries.length > 0 ? {
      type: finalEntries[0].paginationType || 'listN',
      baseUrl: finalEntries[0].url,
      pattern: finalEntries[0].paginationHint || '',
    } : { type: 'none' },
    extraction: {
      filterKeywords: ['学院概览', '学院简介', '师资队伍', '科学研究', '人才培养', '党的建设', '首页', 'English'],
    },
    notes: state.notes,
  };

  // 保存正式策略
  const strategyPath = getStrategyPath(domain);
  fs.writeFileSync(strategyPath, JSON.stringify(strategy, null, 2), 'utf8');
  console.log(`[保存] 策略已保存到 ${strategyPath}`);

  // 删除in-progress文件（如果存在）
  const inProgressPath = getInProgressPath(domain);
  if (fs.existsSync(inProgressPath)) {
    fs.unlinkSync(inProgressPath);
    console.log(`[清理] 已删除暂存文件`);
  }

  return strategy;
}

// ============================================================
// 入口点
// ============================================================

function printHelp() {
  console.log(`
=== site-explorer.js - 网站探索Agent ===

用法：
  node site-explorer.js --url <URL> [选项]
  node site-explorer.js --continue <domain>
  node site-explorer.js --list
  node site-explorer.js --help

选项：
  --url <URL>        要探索的网站URL
  --hint <文本>      用户提供的初始提示（如已知入口）
  --continue <domain> 继续之前的探索会话
  --list             列出所有进行中的探索
  --help             显示此帮助

示例：
  node site-explorer.js --url https://jw.nju.edu.cn/
  node site-explorer.js --url https://jw.nju.edu.cn/ --hint "通知在/24738/list.htm"
  node site-explorer.js --continue jw.nju.edu.cn

交互命令：
  数字              - 选择入口
  自然语言          - 补充或纠正
  确认              - 保存策略
  打断              - 暂存并退出
`);
}

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes('--help')) {
    printHelp();
    return;
  }

  // --list 参数
  if (args.includes('--list')) {
    const dir = getStrategiesDir();
    const files = fs.readdirSync(dir).filter(f => f.endsWith('.in-progress.json'));
    if (files.length === 0) {
      console.log('没有进行中的探索会话');
    } else {
      console.log('进行中的探索会话:');
      files.forEach(f => {
        const data = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
        console.log(`  ${f}`);
        console.log(`    站点: ${data.meta?.siteName || data.domain}`);
        console.log(`    更新: ${data.meta?.updatedAt}`);
        console.log(`    入口: ${data.entries?.length}个`);
      });
    }
    return;
  }

  // --continue 参数
  const continueIdx = args.indexOf('--continue');
  if (continueIdx !== -1 && args[continueIdx + 1]) {
    const domain = args[continueIdx + 1];
    const inProgress = checkInProgress(domain);
    if (!inProgress) {
      console.error(`[错误] 未找到 ${domain} 的进行中探索`);
      console.error(`  请先运行: node site-explorer.js --url https://${domain}/`);
      return;
    }

    const existingState = {
      domain: inProgress.meta.domain,
      siteName: inProgress.meta.siteName,
      url: inProgress.url,
      entries: inProgress.entries,
      selected: inProgress.selected || [],
      notes: inProgress.notes,
      userHint: inProgress.meta.userHint,
      createdAt: inProgress.meta.createdAt,
      updatedAt: inProgress.meta.updatedAt,
    };

    await runInteractiveSession(existingState.url, existingState.userHint, existingState);
    return;
  }

  // --url 参数
  const urlIdx = args.indexOf('--url');
  if (urlIdx === -1 || !args[urlIdx + 1]) {
    console.error('[错误] 请提供 --url 参数');
    console.error('  示例: node site-explorer.js --url https://jw.nju.edu.cn/');
    return;
  }

  const siteUrl = args[urlIdx + 1];
  const hintIdx = args.indexOf('--hint');
  const userHint = hintIdx !== -1 && args[hintIdx + 1] ? args[hintIdx + 1] : null;

  // 检查是否有进行中的探索
  const domain = new URL(siteUrl).hostname;
  const inProgress = checkInProgress(domain);
  if (inProgress) {
    console.log(`[检测] 发现 ${domain} 有未完成的探索会话`);
    const rl = createReadlineInterface();
    const answer = await new Promise(resolve => {
      rl.question('是否继续？(y/n): ', a => { rl.close(); resolve(a.trim().toLowerCase()); });
    });
    if (answer === 'y' || answer === 'yes' || answer === '是') {
      const existingState = {
        domain: inProgress.meta.domain,
        siteName: inProgress.meta.siteName,
        url: inProgress.url,
        entries: inProgress.entries,
        selected: inProgress.selected || [],
        notes: inProgress.notes,
        userHint: inProgress.meta.userHint,
        createdAt: inProgress.meta.createdAt,
        updatedAt: inProgress.meta.updatedAt,
      };
      await runInteractiveSession(existingState.url, existingState.userHint, existingState);
      return;
    }
  }

  // 检查LLM可用性
  const llm = getLLM();
  const llmAvailable = llm && llm.CONFIG && llm.CONFIG.mode !== 'local' &&
    ((llm.CONFIG.mode === 'claude' && llm.CONFIG.anthropicKey) ||
     (llm.CONFIG.mode === 'openai' && llm.CONFIG.openaiKey));

  if (!llmAvailable) {
    console.log('[警告] LLM不可用，使用启发式分析（可能不准确）');
    console.log('[提示] 配置 ANTHROPIC_API_KEY 或 OPENAI_API_KEY 可获得更好的分析');

    // 使用启发式分析
    const result = await analyzeWithHeuristics(siteUrl);
    const state = {
      domain: result.domain,
      siteName: result.siteName,
      url: siteUrl,
      entries: result.entries,
      selected: [],
      notes: result.notes,
      userHint: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    // 直接保存（启发式无交互）
    await saveStrategy(state);
    return;
  }

  // 正常运行
  await runInteractiveSession(siteUrl, userHint, null);
}

// 导出供其他模块使用
module.exports = {
  exploreSite: runInteractiveSession,     // 交互式探索
  exploreSiteSimple,                       // 非交互式探索（供collector.js使用）
  checkInProgress,
  analyzeSiteStructure,
  analyzeWithHeuristics,
};

// 仅在直接运行时执行
if (require.main === module) {
  main().catch(e => {
    console.error('[错误]', e.message);
    process.exit(1);
  });
}
