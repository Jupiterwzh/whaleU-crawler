# 蓝鲸U — Context Pack

> 本文件由 Claude Code 会话生成，供后续 AI 接手使用。
> 最后更新：2026-08-02

---

## 一、项目概述

**蓝鲸U**是南京大学智能搜索爬虫与Agent构建教学项目。
目标：从南京大学各院系网站自动抓取通知公告，汇总为结构化数据供搜索使用。

### 项目结构

```
D:\PY\lanling-u\
├── standalone/                    # 原版爬虫（保持兼容）
│   └── src/                       # 函数式代码
│       ├── collectors/collector.js
│       ├── explorers/site-explorer.js
│       └── ...
│
└── agent-harness/                 # OOP架构版本（推荐）
    └── src/agents/                # 面向对象Agent
        ├── base-agent.js         # 基础Agent类
        ├── crawler-agent.js      # 爬虫Agent
        ├── explorer-agent.js     # 探索Agent
        └── index.js              # 导出索引
```

### 核心模块

| 模块 | 路径 | 说明 |
|------|------|------|
| **独立爬虫** | `standalone/src/collectors/` | 策略驱动的 HTTP 爬虫 |
| **探索Agent** | `standalone/src/explorers/` | 交互式网站结构探索 |
| **分析器** | `standalone/src/analyzers/` | 启发式 + LLM 混合分析 |
| **策略管理** | `standalone/src/strategies/` | 策略文件 CRUD |
| **OOP Agent** | `agent-harness/src/agents/` | 面向对象Agent（OOP架构） |
| **LLM接口** | `../src/agent/llm.js` | Claude/OpenAI接口 |

---

## 二、目录结构

### standalone/（原版，保持兼容）

```
standalone/
├── src/
│   ├── collectors/               # 爬虫主程序
│   │   └── collector.js          # 主入口（命令行解析 + 调度）
│   ├── explorers/                # 探索Agent
│   │   └── site-explorer.js      # 多轮交互式网站探索
│   ├── analyzers/                # 分析器
│   │   ├── analyzer.js           # 启发式 + LLM降级分析
│   │   └── agent-analyzer.js     # 纯LLM策略分析
│   ├── strategies/               # 策略管理
│   │   └── strategy-manager.js   # 策略CRUD + v2→v3升级
│   └── data/
│       └── sites.js              # 站点URL清单（130+个）
├── browser/                      # 浏览器服务
│   ├── nju-browser-server.js     # Puppeteer服务器
│   ├── nju-browser-start.js      # 服务器启动器
│   ├── nju-query.js              # 查询CLI
│   └── chrome/                   # Chrome for Testing 148
├── data/                         # 数据目录
│   ├── records/                  # 爬取结果
│   ├── strategies/               # 策略文件
│   │   ├── {domain}.json         # 正式策略
│   │   ├── {domain}.draft.json   # 草稿策略
│   │   └── {domain}.in-progress.json  # 探索中状态
│   └── strategies.json           # v2迁移标记（勿删除）
├── scripts/                      # 辅助脚本
│   ├── browser-start.js          # 浏览器启动
│   └── _backup_zip.js            # ZIP备份
├── config/
│   └── .env.example              # 环境配置模板
├── .claude/                      # Claude Code配置
│   ├── settings.json             # Harness权限配置
│   └── CLAUDE.md                 # 项目说明（含OOP约束）
├── .gitignore
├── AGENTS.md                     # AI协作指南
├── AGENT_HARNESS_GUIDE.md        # Agent配置和安全指南
├── README.md                     # 使用说明
├── SPEC.md                       # 项目规格
├── CHECKLIST.md                  # 验收清单
└── context-pack.md               # 本文件
```

### agent-harness/（OOP架构版本）

```
agent-harness/
├── src/
│   └── agents/                   # Agent核心模块（OOP）
│       ├── base-agent.js         # 基础Agent类
│       ├── crawler-agent.js      # 爬虫Agent
│       ├── explorer-agent.js     # 探索Agent
│       └── index.js              # 导出索引
├── data/                         # 数据目录
│   ├── records/                  # 爬取结果
│   └── strategies/               # 策略文件
├── .claude/                      # Claude Code配置
│   ├── settings.json             # Harness配置（含env映射）
│   └── CLAUDE.md                 # 项目说明
├── OOP_GUIDE.md                  # OOP架构指南
├── README.md                     # 使用说明
└── 启动Agent.bat                 # 启动脚本
```

---

## 三、策略系统

### 3.1 设计理念

- **AI + 用户交互**：网站探索Agent先列举入口，用户选择确认后 AI 分析生成策略
- **多轮交互**：AI列举 → 用户选择/补充 → AI重新分析 → 重复直到确认
- **启发式为兜底**：LLM不可用或探索失败时自动回退到启发式分析

### 3.2 策略文件格式（v3）

```json
{
  "meta": {
    "domain": "cs.nju.edu.cn",
    "siteName": "计算机学院主页",
    "strategyVersion": 3,
    "created": "...", "updated": "..."
  },
  "entries": [
    {
      "name": "教务通知",
      "url": "https://cs.nju.edu.cn/1702/list.htm",
      "type": "news_title",
      "paginationType": "listN",
      "paginationHint": "/1702/list{page}.htm"
    }
  ],
  "pagination": { "type": "listN", "pattern": "..." },
  "extraction": {
    "filterKeywords": ["学院概览", "师资队伍", "首页", ...]
  }
}
```

### 3.3 探索流程

```
node src/explorers/site-explorer.js --url https://新站点/
  → AI列举发现的入口
  → 用户选择数字 或 自然语言补充
  → AI重新分析
  → 重复直到用户输入"确认"或"打断"
  → 确认 → 保存为正式策略
  → 打断 → 暂存为 .in-progress.json（下次可继续）
```

---

## 四、OOP架构（agent-harness）

### 4.1 Agent类层次

```
BaseAgent
├── 属性：name, type, version, status, envPrefix
├── 方法：getEnv(), getLLMMode(), getAPIKey(), isLLMEnabled()
│        log(), sleep(), generateId()
│
└── TaskAgent
    ├── 额外属性：currentTask, taskHistory
    ├── 额外方法：setTask(), updateTaskStatus()
    │            completeTask(), failTask()
    │
    ├── CrawlerAgent
    │   └── 环境前缀：CRAWLER_*
    │
    └── ExplorerAgent
        └── 环境前缀：EXPLORER_*
```

### 4.2 环境变量前缀

| Agent | 前缀 | 示例 |
|-------|------|------|
| CrawlerAgent | `CRAWLER_` | `CRAWLER_LLM_MODE`, `CRAWLER_ANTHROPIC_API_KEY` |
| ExplorerAgent | `EXPLORER_` | `EXPLORER_LLM_MODE`, `EXPLORER_ANTHROPIC_API_KEY` |

### 4.3 生命周期

```
1. 实例化 → new CrawlerAgent()
2. 初始化 → await agent.init(context)
3. 执行   → await agent.execute(task)
4. 完成   → agent.completeTask(result) 或 agent.failTask(error)
```

---

## 五、Harness 配置

### 5.1 standalone settings.json

```json
{
  "permissions": {
    "allow": [
      {"prompt": "run node commands", "tool": "Bash"},
      {"prompt": "read any file in project", "tool": "Read"},
      {"prompt": "write js/json/md files", "tool": "Write"},
      {"prompt": "edit existing files", "tool": "Edit"}
    ],
    "deny": [
      {"prompt": "read .env file", "tool": "Read"},
      {"prompt": "read *secret* files", "tool": "Read"},
      {"prompt": "read *.local.json", "tool": "Read"}
    ]
  }
}
```

### 5.2 agent-harness settings.json（含env映射）

```json
{
  "permissions": {
    "allow": [...],
    "deny": [
      {"prompt": "read .env file", "tool": "Read"},
      {"prompt": "read *KEY* files", "tool": "Read"},
      {"prompt": "read *PASSWORD* files", "tool": "Read"},
      {"prompt": "read *SECRET* files", "tool": "Read"},
      {"prompt": "read *TOKEN* files", "tool": "Read"}
    ]
  },
  "env": {
    "LLM_MODE": "env:CRAWLER_LLM_MODE",
    "ANTHROPIC_API_KEY": "env:CRAWLER_ANTHROPIC_API_KEY",
    "OPENAI_API_KEY": "env:CRAWLER_OPENAI_API_KEY",
    "LLM_MODEL": "env:CRAWLER_LLM_MODEL"
  }
}
```

### 5.3 API Key 配置

**安全原则**：Key 存放在不会被 AI 读取、不会 git 上传、但可被 Agent 代码使用的文件中。

**Agent专用Key配置（推荐）**：
```bat
@echo off
REM 设置Agent专用环境变量
set CRAWLER_LLM_MODE=claude
set CRAWLER_ANTHROPIC_API_KEY=sk-ant-your-agent-key
set CRAWLER_LLM_MODEL=claude-haiku-4-5-20251001
REM 启动
claude --project .
```

---

## 六、LLM 配置

### 6.1 配置文件位置

`D:\PY\lanling-u\src\agent\llm.js`

### 6.2 配置项

```bash
LLM_MODE=local|claude|openai    # 默认local
ANTHROPIC_API_KEY=sk-ant-...    # Claude Key
OPENAI_API_KEY=sk-...           # OpenAI Key
LLM_MODEL=claude-sonnet-4-20250514  # 可选模型
```

### 6.3 模式说明

| 模式 | AI探索可用 | 需要 |
|------|-----------|------|
| `local` | ❌ | 无 |
| `claude` | ✅ | ANTHROPIC_API_KEY |
| `openai` | ✅ | OPENAI_API_KEY |

### 6.4 推荐模型

| 用途 | Claude |
|------|--------|
| 快速测试 | `claude-haiku-4-5-20251001` |
| 平衡 | `claude-sonnet-4-20250514`（默认） |
| 最佳 | `claude-opus-4-7` |

---

## 七、核心模块详解

### 7.1 src/collectors/collector.js — 主爬虫（standalone）

- 命令行参数：`--site`, `--url`, `--notices`, `--confirm`, `--re-discover`, `--days`, `--max-pages`, `--force-strategy`, `--list-strategies`
- 核心函数：`crawlOne()`, `crawlNotices()`, `crawlSite()`
- 导出接口：`{ crawlOne, crawlNotices, httpGet, extractNotices, extractArticle, buildRecord, saveJSONL, countRecords, DATA_DIR }`

### 7.2 src/explorers/site-explorer.js — 探索Agent（standalone）

- 命令：`--url`, `--continue`, `--list`, `--help`, `--hint`
- 交互命令：数字选择入口、自然语言补充、"确认"保存、"打断"暂存
- 导出接口：`{ exploreSite, exploreSiteSimple, checkInProgress }`

### 7.3 src/agents/*.js — OOP Agent（agent-harness）

**base-agent.js**：
- 类：`BaseAgent`, `TaskAgent`
- 枚举：`AgentType`, `AgentStatus`
- 工厂函数：`createAgent(type, config)`

**crawler-agent.js**：
- 类：`CrawlerAgent`
- 方法：`execute()`, `crawlSite()`, `crawlNotices()`, `crawlPage()`
- 环境前缀：`CRAWLER_*`

**explorer-agent.js**：
- 类：`ExplorerAgent`
- 方法：`execute()`, `exploreSite()`, `continueExploration()`, `saveDraft()`, `confirmDraft()`
- 环境前缀：`EXPLORER_*`

### 7.4 src/strategies/strategy-manager.js — 策略管理

- 存储：`data/strategies/{domain}.json`（目录模式）
- 核心函数：`getStrategy`, `saveStrategy`, `confirmDraft`, `listStrategies`
- v2→v3自动升级

---

## 八、已验证站点

| 站点 | URL | 策略版本 | 入口数 | 状态 |
|------|-----|----------|--------|------|
| 计算机学院 | cs.nju.edu.cn | ✅ v3 | 1 | 已验证 |
| 本科生院 | jw.nju.edu.cn | ✅ v1 | 44 | 已验证 |

---

## 九、CMS类型检测

| 类型 | 特征 | 说明 |
|------|------|------|
| `news_title` | `.news_title` + `.news_date` | 标准新闻列表 |
| `link-title` | `.link-title` | 历史风格 |
| `dataList` | `dataList=[{...}]` | SPA页面 |
| `article_inline` | `<a>标题<span>日期</span>` | 行内式 |
| `li_fallback` | `<li>` + 日期 | 兜底方案 |

---

## 十、已废弃文件

| 文件 | 废弃原因 |
|------|----------|
| `ai-discoverer.js` | 被 `src/explorers/site-explorer.js` 取代 |
| `browser/nju-search.js` | 旧版搜索工具 |
| `browser/nju-aisearch.js` | 旧版API工具 |

---

## 十一、给接手AI的提示

### 必须遵循

1. **OOP架构**：新增Agent必须继承`BaseAgent`或`TaskAgent`
2. **环境变量前缀**：使用`CRAWLER_*`/`EXPLORER_*`前缀
3. **API Key安全**：不读取`.env`文件，只通过`process.env`访问
4. **不要删除`data/strategies.json`**：v2迁移标记

### 参考文档

| 文档 | 说明 |
|------|------|
| `AGENTS.md` | AI协作指南 |
| `AGENT_HARNESS_GUIDE.md` | Agent配置和安全指南 |
| `agent-harness/OOP_GUIDE.md` | OOP架构和编码规范 |
| `CHECKLIST.md` | 验收清单 |

### 验证命令

```bash
# standalone验证
node src/collectors/collector.js --list-strategies
node src/collectors/collector.js --site https://cs.nju.edu.cn/ --max-pages 1

# agent-harness验证
node --check src/agents/base-agent.js
node -e "const agents = require('./src/agents'); console.log(Object.keys(agents));"
```
