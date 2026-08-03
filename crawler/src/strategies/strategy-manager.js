/**
 * 站点爬取策略管理器（目录存储版）
 *
 * 存储结构：
 *   data/strategies/{domain}.json        — 正式策略（已确认）
 *   data/strategies/{domain}.draft.json   — 草稿策略（AI探索后待确认）
 *
 * 策略格式（v3 — 兼容旧 v2）：
 * {
 *   "meta": { "domain": "...", "siteName": "...", "created": "...", "updated": "..." },
 *   "entries": [{ "name": "...", "url": "...", "type": "news_title", ... }],
 *   "pagination": { "type": "listN", "pattern": "..." },
 *   "extraction": { "titleMatch": "...", "filterKeywords": [...] }
 * }
 */

const fs = require('fs');
const path = require('path');

const STRATEGIES_DIR = path.join(__dirname, '..', '..', 'data', 'strategies');

// 确保目录存在
function ensureDir() {
  if (!fs.existsSync(STRATEGIES_DIR)) {
    fs.mkdirSync(STRATEGIES_DIR, { recursive: true });
  }
}

// ============================================================
// 基础文件操作
// ============================================================

function strategyPath(domain) {
  return path.join(STRATEGIES_DIR, `${domain}.json`);
}

function draftPath(domain) {
  return path.join(STRATEGIES_DIR, `${domain}.draft.json`);
}

function readJson(filePath) {
  if (!fs.existsSync(filePath)) return null;
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return null;
  }
}

function writeJson(filePath, data) {
  ensureDir();
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
}

// ============================================================
// 正式策略操作
// ============================================================

/**
 * 获取站点的正式策略
 * @param {string} domain
 * @returns {object|null}
 */
function getStrategy(domain) {
  const data = readJson(strategyPath(domain));
  if (!data) return null;

  // v2 → v3 升级：检测是否真正为 v3 格式（v3 有 entries 字段）
  // 或显式 version=2 → 升级
  if (!data.entries || data.version === 2) {
    const upgraded = upgradeV2toV3(domain, data);
    writeJson(strategyPath(domain), upgraded);
    return upgraded;
  }

  return data;
}

/**
 * 将 v2 格式升级为 v3
 */
function upgradeV2toV3(domain, v2) {
  const now = new Date().toISOString();
  const siteName = v2.siteName || domain;

  // 从 pagination 提取入口信息
  const entries = [];
  if (v2.pagination?.baseUrl) {
    entries.push({
      name: siteName + '通知',
      url: v2.pagination.baseUrl,
      type: v2.listPage?.type || 'news_title',
      description: '',
      paginationType: v2.pagination?.type || 'listN',
      paginationHint: v2.pagination?.pattern || '',
      estimatedCount: 0,
    });
  }

  return {
    meta: {
      domain,
      siteName,
      strategyVersion: 3,
      created: v2.detected || now,
      updated: now,
    },
    entries,
    pagination: v2.pagination || { type: 'none' },
    extraction: {
      titleMatch: v2.article?.titleMatch || '',
      dateMatch: v2.article?.timeMatch || '',
      hrefMatch: '',
      filterKeywords: v2.listPage?.filterKeywords || [],
    },
    notes: '',
    _upgradedFrom: 'v2',
  };
}

/**
 * 保存正式策略
 * @param {string} domain
 * @param {object} strategy
 */
function saveStrategy(domain, strategy) {
  const now = new Date().toISOString();
  const existing = getStrategy(domain);

  const updated = {
    ...strategy,
    meta: {
      ...(strategy.meta || {}),
      domain,
      updated: now,
      created: existing?.meta?.created || now,
    },
    version: 3,
  };

  writeJson(strategyPath(domain), updated);
  console.log(`[策略] 已保存 ${domain}（${updated.meta?.siteName || domain}）`);
}

/**
 * 删除站点的正式策略
 * @param {string} domain
 */
function deleteStrategy(domain) {
  const p = strategyPath(domain);
  if (fs.existsSync(p)) {
    fs.unlinkSync(p);
    console.log(`[策略] 已删除 ${domain}`);
  }
  // 同时删除草稿
  deleteDraft(domain);
}

// ============================================================
// 草稿策略操作
// ============================================================

/**
 * 获取站点的草稿策略
 * @param {string} domain
 * @returns {object|null}
 */
function getDraft(domain) {
  return readJson(draftPath(domain));
}

/**
 * 保存草稿策略（AI探索结果）
 * @param {string} domain
 * @param {object} draft
 */
function saveDraft(domain, draft) {
  ensureDir();
  const now = new Date().toISOString();
  const data = {
    ...draft,
    meta: {
      ...(draft.meta || {}),
      domain,
      discoveredAt: now,
      status: 'draft',
    },
  };
  writeJson(draftPath(domain), data);
  console.log(`[草稿] 已保存到 ${draftPath(domain)}`);
}

/**
 * 删除草稿策略
 * @param {string} domain
 */
function deleteDraft(domain) {
  const p = draftPath(domain);
  if (fs.existsSync(p)) {
    fs.unlinkSync(p);
  }
}

/**
 * 确认草稿：验证草稿格式，将草稿转为正式策略
 * @param {string} domain
 * @returns {object} 转换后的策略对象，失败则返回 null
 */
function confirmDraft(domain) {
  const draft = getDraft(domain);
  if (!draft) {
    console.error(`[确认] 找不到草稿: ${domain}`);
    return null;
  }

  // 验证草稿必需字段
  if (!draft.entries || !Array.isArray(draft.entries) || draft.entries.length === 0) {
    console.error(`[确认] 草稿格式错误: entries 字段缺失或为空`);
    return null;
  }

  // 转换草稿为正式策略格式
  const now = new Date().toISOString();
  const strategy = {
    meta: {
      domain,
      siteName: draft.meta?.siteName || draft.siteName || domain,
      strategyVersion: 1,
      created: now,
      updated: now,
    },
    entries: draft.entries.map(e => ({
      name: e.name || '未命名栏目',
      url: e.url || '',
      type: e.type || e.cmsType || 'news_title',
      description: e.description || e.notes || '',
      paginationType: e.paginationType || 'none',
      paginationHint: e.paginationHint || '',
      estimatedCount: e.estimatedCount || 0,
    })),
    pagination: draft.pagination || { type: 'none' },
    extraction: {
      titleMatch: draft.titleMatch || '',
      dateMatch: draft.dateMatch || '',
      hrefMatch: draft.hrefMatch || '',
      filterKeywords: draft.filterKeywords || [],
    },
    notes: draft.notes || '',
    _draftMeta: draft.meta,
  };

  // 保存为正式策略
  saveStrategy(domain, strategy);

  // 删除草稿
  deleteDraft(domain);

  console.log(`[确认] 草稿已转为正式策略，共 ${strategy.entries.length} 个信息入口`);
  return strategy;
}

// ============================================================
// 列表与统计
// ============================================================

/**
 * 列出所有策略（正式+草稿）
 * @returns {Array}
 */
function listStrategies() {
  ensureDir();
  const files = fs.readdirSync(STRATEGIES_DIR);
  const result = [];

  for (const f of files) {
    if (!f.endsWith('.json')) continue;
    const fullPath = path.join(STRATEGIES_DIR, f);
    const data = readJson(fullPath);
    if (!data) continue;

    const isDraft = f.endsWith('.draft.json');
    const domain = isDraft ? f.replace('.draft.json', '') : f.replace('.json', '');
    const meta = data.meta || {};

    result.push({
      domain,
      isDraft,
      siteName: meta.siteName || data.siteName || domain,
      entryCount: data.entries?.length || 0,
      detected: meta.discoveredAt || meta.detected || null,
      updated: meta.updated || null,
      file: f,
    });
  }

  return result;
}

/**
 * 获取所有正式策略（不含草稿）
 * @returns {object} { domain: strategy, ... }
 */
function getAllStrategies() {
  ensureDir();
  const files = fs.readdirSync(STRATEGIES_DIR);
  const result = {};
  for (const f of files) {
    if (!f.endsWith('.json') || f.endsWith('.draft.json')) continue;
    const domain = f.replace('.json', '');
    result[domain] = readJson(path.join(STRATEGIES_DIR, f));
  }
  return result;
}

// ============================================================
// 迁移旧数据（从 v2 单文件升级）
// ============================================================

function migrateFromV2() {
  const v2File = path.join(__dirname, '..', '..', 'data', 'strategies.json');
  if (!fs.existsSync(v2File)) return;

  console.log('[迁移] 检测到旧版 strategies.json，开始迁移...');
  try {
    const old = JSON.parse(fs.readFileSync(v2File, 'utf8'));
    ensureDir();

    for (const [domain, strategy] of Object.entries(old)) {
      if (domain === '_migrationDone') continue;
      const p = strategyPath(domain);
      if (!fs.existsSync(p)) {
        writeJson(p, strategy);
        console.log(`  迁移: ${domain}`);
      }
    }

    // 标记迁移完成
    fs.writeFileSync(v2File, JSON.stringify({ _migrationDone: true }), 'utf8');
    console.log('[迁移] 完成');
  } catch (e) {
    console.error('[迁移] 失败:', e.message);
  }
}

// 启动时自动迁移
migrateFromV2();

module.exports = {
  getStrategy,
  saveStrategy,
  deleteStrategy,
  getDraft,
  saveDraft,
  deleteDraft,
  confirmDraft,
  listStrategies,
  getAllStrategies,
  STRATEGIES_DIR,
};
