# 蓝鲸U — 独立爬虫

> 南京大学通知公告智能爬虫 — 自动爬取各院系通知公告，输出结构化 JSONL 数据。
> 不含 Agent 筛选匹配逻辑，纯爬虫模块。

---

## 目录

- [快速开始](#快速开始)
- [环境配置](#环境配置)
- [目录结构](#目录结构)
- [命令参考](#命令参考)
- [策略系统](#策略系统)
- [数据格式](#数据格式)
- [常见问题](#常见问题)

---

## 快速开始

### 首次爬取新网站（AI探索流程）

```bash
# Step 1: 触发AI探索，生成草稿
node collector.js --site https://jw.nju.edu.cn/
# → 生成草稿 data/strategies/jw.nju.edu.cn.draft.json
# → 程序退出，等待编辑

# Step 2: 编辑草稿（见"策略系统"章节）
# 用文本编辑器打开草稿JSON，修正URL、删除错误入口

# Step 3: 确认草稿，开始爬取
node collector.js --confirm jw.nju.edu.cn --days 365
```

### 后续爬取（已有策略）

```bash
# 直接使用已保存策略，不触发AI
node collector.js --site https://jw.nju.edu.cn/ --days 365 --max-pages 10
```

### 快速测试（无需配置AI）

```bash
# 强制使用启发式分析，无需API Key
node collector.js --site https://cs.nju.edu.cn/ --force-strategy --days 365 --max-pages 2
```

---

## 环境配置

### 必需环境

- **Node.js 18+**
- 运行目录：`D:\PY\lanling-u\standalone\`

### LLM配置（可选）

AI探索功能需要配置以下环境变量。**配置方式：直接在命令行设置，不要创建 .env 文件**。

```bash
# 方式一：命令行临时设置（推荐）
set LLM_MODE=claude
set ANTHROPIC_API_KEY=sk-ant-your-key-here
node collector.js --site https://xxx/

# 方式二：永久设置（Windows系统环境变量）
# 控制面板 → 系统 → 高级系统设置 → 环境变量 → 新建系统变量
```

| 变量 | 值 | 说明 |
|------|-----|------|
| `LLM_MODE` | `local`（默认）/ `claude` / `openai` | AI模式 |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Claude API Key（claude模式需要） |
| `OPENAI_API_KEY` | `sk-...` | OpenAI API Key（openai模式需要） |

**重要**：
- 不创建、不读取 `.env` 文件（AI不应读取凭证文件）
- 不将 API Key 写入代码或配置文件
- local模式AI功能不可用，但爬取功能完全正常

### 浏览器模式（可选）

部分JS渲染站点需要浏览器模式。浏览器服务优先使用 `CHROME_PATH` 环境变量指定的 Chrome，未设置则回退 Microsoft Edge 默认安装路径。

```powershell
# Windows PowerShell：指定 Chrome for Testing 路径（按实际安装位置填）
$env:CHROME_PATH = "C:\<你的Chrome缓存路径>\chrome.exe"
```

启动浏览器服务后，使用 `--browser` 标志：

```bash
# 启动浏览器（单独命令行窗口）
node browser-start.js

# 爬取时启用浏览器模式
node collector.js --site https://xxx/ --browser
```

---

## 目录结构

```
standalone/
├── collector.js              # 主入口（命令行解析 + 爬取调度）
├── analyzer.js               # 启发式分析器（HTTP抓取、CMS检测、SPA检测）
├── ai-discoverer.js          # AI探索器（调用LLM生成草稿JSON）
├── agent-analyzer.js         # 纯LLM策略分析器（置信度<50%时降级）
├── strategy-manager.js       # 策略管理器（目录存储模式）
├── sites.js                  # 站点URL配置
├── browser-start.js          # Puppeteer浏览器启动器
├── browser/                  # 浏览器相关文件
│   ├── chrome/               # Chrome for Testing 148（28MB，已验证可用）
│   └── ...
├── data/
│   ├── strategies/           # 策略文件目录（每域名一文件）
│   │   ├── {domain}.json             # 正式策略（已确认）
│   │   └── {domain}.draft.json       # 草稿策略（AI探索结果，待确认）
│   ├── strategies.json       # 旧版v2格式（自动迁移，勿删除）
│   └── all_records.jsonl    # 爬取数据汇总
├── 启动浏览器.bat
├── 启动爬虫.bat
└── README.md
```

### standalone 是否可以作为完整工作目录？

**是**。`standalone/` 是一个自包含的工作目录：

- ✅ 所有核心代码在 `standalone/` 内
- ✅ 依赖 `node_modules`（通过 `../nju-crawler/` 引用 LLM接口）
- ✅ 策略和数据存储在 `data/` 子目录
- ✅ 双击 BAT 文件即可运行
- ⚠️ `browser/chrome/` 含 28MB Chromium，如需精简可排除

---

## 命令参考

### AI探索流程

| 命令 | 说明 |
|------|------|
| `node collector.js --site <URL>` | 有策略直接爬；无策略AI探索生成草稿后退出 |
| `node collector.js --confirm <domain>` | 确认草稿 → 转为正式策略 → 立即开始爬取 |
| `node collector.js --re-discover <domain>` | 删除旧策略，重新AI探索 |

### 策略管理

| 命令 | 说明 |
|------|------|
| `node collector.js --list-strategies` | 列出所有策略（含草稿状态） |
| `node collector.js --remove-strategy <domain>` | 删除指定站点的策略 |
| `node collector.js --force-analyze <URL>` | 强制使用启发式分析生成正式策略 |

### 直接爬取

| 命令 | 说明 |
|------|------|
| `node collector.js --site <URL>` | 自动发现并爬取全部通知列表 |
| `node collector.js --notices <列表页URL>` | 爬取指定通知列表页 |
| `node collector.js --url <URL>` | 爬取单个页面正文 |

### 全局参数

| 参数 | 说明 |
|------|------|
| `--days <N>` | 只爬N天内的通知（默认无限制） |
| `--max-pages <N>` | 每个列表页最多爬N页（默认5） |
| `--output <file>` | 指定输出文件名 |
| `--force-strategy` | 跳过已有策略，强制用启发式检测 |

### 示例

```bash
# 完整AI探索流程
node collector.js --site https://jw.nju.edu.cn/
node collector.js --confirm jw.nju.edu.cn --days 180

# 后续爬取（已有策略）
node collector.js --site https://jw.nju.edu.cn/ --days 365 --max-pages 10

# 强制重新发现
node collector.js --re-discover cs.nju.edu.cn

# 快速测试（启发式）
node collector.js --site https://cs.nju.edu.cn/ --force-strategy --max-pages 2

# 爬取单个列表页
node collector.js --notices https://cs.nju.edu.cn/1702/list.htm --days 30 --max-pages 3

# 查看统计
node collector.js --stats
node collector.js --help
```

---

## 策略系统

### 核心概念

| 概念 | 说明 |
|------|------|
| **草稿策略** | AI探索生成，待用户编辑确认，文件以 `.draft.json` 结尾 |
| **正式策略** | 用户确认后的策略，以 `.json` 结尾，直接用于爬取 |
| **信息入口** | 一个URL对应一个通知列表页，一个站点可有多个入口 |

### 为什么需要用户编辑草稿？

AI 的 HTML 结构分析能力强，但**不了解业务语义**：
- AI 可能把"首页"或"人才招聘"当成通知列表
- AI 可能遗漏需要登录的页面
- AI 可能遗漏分页规律

用户编辑草稿 = 注入业务知识，AI 负责技术实现。

### 策略文件结构（v3）

**正式策略** `data/strategies/{domain}.json`：

```json
{
  "meta": {
    "domain": "cs.nju.edu.cn",
    "siteName": "计算机学院主页",
    "strategyVersion": 1,
    "created": "2026-08-02T12:00:00.000Z",
    "updated": "2026-08-02T12:00:00.000Z"
  },
  "entries": [
    {
      "name": "教务通知",
      "url": "https://cs.nju.edu.cn/1702/list.htm",
      "type": "news_title",
      "description": "各类教务通知公告",
      "paginationType": "listN",
      "paginationHint": "/1702/list{page}.htm",
      "estimatedCount": 0
    }
  ],
  "pagination": {
    "type": "listN",
    "baseUrl": "https://cs.nju.edu.cn/1702/list.htm",
    "pattern": "/1702/list{page}.htm"
  },
  "extraction": {
    "titleMatch": "",
    "dateMatch": "",
    "hrefMatch": "",
    "filterKeywords": ["学院概览", "学院简介", "师资队伍", "科学研究", "人才培养", "党的建设", "首页", "English"]
  }
}
```

**草稿策略** `data/strategies/{domain}.draft.json`：

```json
{
  "meta": {
    "domain": "cs.nju.edu.cn",
    "siteName": "计算机学院主页",
    "discoveredAt": "2026-08-02T12:00:00.000Z",
    "status": "draft"
  },
  "entries": [
    {
      "name": "教务通知",
      "url": "https://cs.nju.edu.cn/1702/list.htm",
      "type": "news_title",
      "paginationType": "listN",
      "paginationHint": "/1702/list{page}.htm",
      "estimatedCount": 50,
      "notes": "需要登录"
    }
  ],
  "pagination": {
    "type": "listN",
    "hint": "/1702/list{page}.htm"
  },
  "notes": "整体备注"
}
```

### 如何修改策略文件

#### 修改草稿（推荐首次使用）

1. 打开 `data/strategies/{domain}.draft.json`
2. 编辑 `entries` 数组：
   - `name`：给栏目起个名字（如"教务通知"、"科研动态"）
   - `url`：修正为正确的列表页URL
   - `type`：CMS类型，`news_title` / `link-title` / `dataList` / `article_inline` / `other`
   - `paginationType`：分页类型，`listN` / `query` / `pathN` / `none`
   - `paginationHint`：分页URL规律，如 `/1702/list{page}.htm`
   - `estimatedCount`：AI估计的通知数量，可不改
   - `notes`：备注，如"需要登录"
3. 删除不需要的 entries
4. 保存文件
5. 运行 `node collector.js --confirm {domain}`

#### 修改正式策略

直接编辑 `data/strategies/{domain}.json` 的对应字段。

#### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `entries[].name` | 是 | 栏目名称（用户自定义） |
| `entries[].url` | 是 | 列表页完整URL |
| `entries[].type` | 是 | CMS类型，影响提取正则 |
| `entries[].paginationType` | 是 | 分页规律 |
| `pagination` | 否 | 全站分页配置 |
| `extraction.filterKeywords` | 否 | 提取时排除的关键词 |

### 支持的 CMS 类型

| type | 说明 | 典型网站 |
|------|------|---------|
| `news_title` | `news_title` + `news_date` 结构 | cs.nju.edu.cn, ai.nju.edu.cn |
| `link-title` | `link-title` + 日期 | history.nju.edu.cn |
| `dataList` | JS变量嵌入JSON（SPA） | software.nju.edu.cn |
| `article_inline` | 行内式 `<a>标题<span>日期</span>` | 部分站点 |
| `li_fallback` | `<li>` 兜底（置信度低） | 通用 |

### 置信度（仅供参考）

策略中的 `trust` 字段已不再用于决策，仅供参考。AI探索失败时会自动降级到启发式分析，无需人工判断置信度。

---

## 数据格式

### 爬取记录（JSONL）

`data/all_records.jsonl`，每行一个JSON对象：

```json
{"title":"标题","url":"https://...","content":"正文内容...","publishTime":"2026-08-01","attachments":["https://...pdf"],"hasVideo":false,"hasAudio":false,"source":{"author":"","department":"计算机学院","siteName":"cs.nju.edu.cn"},"tags":["通知公告"],"crawler":"nju-crawler","crawlTime":"2026-08-02T10:00:00.000Z"}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 文章标题 |
| `url` | string | 文章URL |
| `content` | string | 正文（前20000字符） |
| `publishTime` | string | 发布时间（格式 `YYYY-MM-DD`），可能为null |
| `attachments` | array | 附件URL列表 |
| `hasVideo` | boolean | 是否含视频 |
| `hasAudio` | boolean | 是否含音频 |
| `source.department` | string | 来源部门（推断） |
| `source.siteName` | string | 来源站点 |
| `tags` | array | 自动推断的标签 |
| `crawler` | string | 爬虫标识 `"nju-crawler"` |
| `crawlTime` | string | 爬取时间（ISO格式） |

---

## 常见问题

**Q: 提示"无法提取JSON"或探索失败？**
A: local模式下AI功能不可用，这是预期行为。添加 `--force-strategy` 使用启发式分析：
```bash
node collector.js --site https://xxx/ --force-strategy
```

**Q: 草稿需要编辑什么？**
A: 主要检查 `entries` 中的 `url` 是否正确（AI可能分析出错误的URL），删除不需要的栏目入口。

**Q: 如何完全从头开始（删除所有策略）？**
```bash
# 删除所有策略文件
rm data/strategies/*.json data/strategies/*.draft.json
# 重新探索
node collector.js --site https://xxx/
```

**Q: 院系通知漏爬？**
A: 部分院系使用SPA（JS渲染）。尝试浏览器模式，或手动指定列表页：
```bash
node collector.js --notices https://xxx/list.htm --days 365
```

**Q: 浏览器启动失败？**
A: 检查 `browser-start.js` 中的 `CHROME_PATHS`，确保Chrome路径正确。

**Q: 如何查看已发现的站点？**
```bash
node collector.js --list-strategies
```

---

## 相关文档

| 文档 | 说明 |
|------|------|
| `SPEC.md` | 项目规格说明书（目标、约束、阶段划分） |
| `CHECKLIST.md` | 验收清单（逐条可验证） |
| `AGENTS.md` | AI协作指南（给后续AI阅读） |
| `context-pack.md` | 会话上下文总结 |
