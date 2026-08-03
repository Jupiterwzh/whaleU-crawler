/**
 * agent-analyzer.js — 基于 LLM 的策略分析器
 *
 * 当启发式分析置信度低于 50% 时自动降级调用。
 * 复用 src/agent/llm.js 的 ask() 接口。
 *
 * 使用方式：
 *   const { analyzeWithLLM } = require('./agent-analyzer');
 *   const strategy = await analyzeWithLLM('https://xxx.nju.edu.cn/', html);
 */

const { ask, CONFIG } = require('../src/agent/llm');

// ============================================================
// Prompt 设计
// ============================================================

const SYSTEM_PROMPT = `你是一个专业的网页结构分析助手，专注于识别中国高校网站的通知列表页结构。

给定一个网页的 HTML 片段，请分析：
1. 这是不是一个通知列表页（还是首页、文章页、导航页等）
2. 通知条目的 HTML 结构是什么（class、标签、属性）
3. 日期、标题、链接的提取模式
4. 分页 URL 的规律

如果该页面不是通知列表页，请明确指出。

请用 JSON 格式输出分析结果：

{
  "isListPage": true或false,
  "cmsType": "news_title|link-title|dataList|article_inline|li_fallback|other",
  "titleSelector": "能提取标题的CSS选择器或正则描述",
  "dateSelector": "能提取日期的CSS选择器或正则描述",
  "hrefSelector": "能提取链接的正则描述",
  "filterKeywords": ["应排除的导航关键词列表"],
  "paginationType": "listN|query|pathN|none",
  "paginationHint": "分页URL规律描述",
  "confidence": 0-100（置信度：0=完全不是列表页，100=极确定）,
  "reasoning": "分析思路简述（1-3句）"
}

如果该页面不是通知列表页，confidence 设为 0，并说明理由。
只输出 JSON，不要其他文字。`;

/**
 * 用 LLM 分析网页片段，生成策略对象
 * @param {string} url - 被分析的页面 URL
 * @param {string} html - HTML 内容（前 10000 字符）
 * @returns {Promise<object>} 策略对象（可直接合并到 strategy）
 */
async function analyzeWithLLM(url, html) {
  const snippet = html.slice(0, 10000);
  const prompt = `请分析这个页面 ${url} 的结构：\n\n${snippet}`;

  console.log(`[LLM分析] 正在调用 ${CONFIG.mode} (${CONFIG.model || 'default'})...`);

  const response = await ask(prompt, SYSTEM_PROMPT);
  const content = response.content || '';

  let parsed;
  try {
    parsed = JSON.parse(extractJson(content));
  } catch (e) {
    throw new Error(`JSON 解析失败: ${e.message}\n原始内容: ${content.slice(0, 200)}`);
  }

  if (!parsed.isListPage || parsed.confidence < 20) {
    throw new Error(`LLM 认为这不是列表页 (confidence=${parsed.confidence})`);
  }

  // 转换为标准策略格式
  return convertToStrategy(parsed);
}

/**
 * 从 LLM 输出中提取 JSON
 */
function extractJson(text) {
  // 尝试 ```json ... ``` 格式
  let match = text.match(/```json\s*([\s\S]+?)\s*```/);
  if (match) return match[1].trim();
  // 尝试 ``` ... ``` 格式
  match = text.match(/```\s*([\s\S]+?)\s*```/);
  if (match) return match[1].trim();
  // 尝试直接是 JSON 对象
  match = text.match(/(\{[\s\S]+\})/);
  if (match) return match[1].trim();
  return '{}';
}

/**
 * 将 LLM 输出转换为标准策略格式
 */
function convertToStrategy(llmResult) {
  const typeMap = {
    'news_title': 'news_title',
    'link-title': 'link-title',
    'dataList': 'dataList',
    'article_inline': 'article_inline',
    'li_fallback': 'li_fallback',
    'other': 'li_fallback',
  };

  return {
    siteName: '',  // 由 analyzer.js 从 <title> 填充
    trust: Math.min(95, Math.max(10, llmResult.confidence || 50)),
    strategySource: 'llm',
    listPage: {
      type: typeMap[llmResult.cmsType] || 'li_fallback',
      titleSelector: llmResult.titleSelector || '',
      dateSelector: llmResult.dateSelector || '',
      hrefSelector: llmResult.hrefSelector || '',
      filterKeywords: llmResult.filterKeywords || [],
    },
    pagination: {
      type: llmResult.paginationType || 'none',
      hint: llmResult.paginationHint || null,
    },
    _llmReasoning: llmResult.reasoning || '',
  };
}

module.exports = { analyzeWithLLM };
