# SPEC.md — 南京大学通知公告多 Agent 协作系统

> 版本 3.0 | 更新：2026-08-06
> 定位：AI4SE 期末大作业 · B 类应用项目（含自研 agent 部分）
> 关联：`AGENTS.md`（协作规则）、`PLAN.md`（实现计划）、`SPEC_PROCESS.md`（过程记录）

---

## 1. 问题陈述

南京大学各院系网站的通知公告分散在几十个站点、数百个页面中，信息查找需逐个站点手动浏览。本项目构建一个**基于 harness 工程的多 Agent 协作系统**：自动探索网站结构、生成爬取策略、抓取通知数据、建立可检索的知识库（RAG），并提供一个查询 Agent 让用户用自然语言获取通知信息。

**目标用户**：需要追踪学院通知的学生/教职工（如查看"最近有哪些通知"、"计算机学院本周考试安排"）。

**为什么值得做**：通知信息时效性强、来源分散、手工汇总成本高；且本项目是 harness 工程方法的完整实践——把"LLM 做决策、工程做可靠性"的分工做到极致。

## 2. 用户故事（INVEST，≥5）

| # | 用户故事 | 验收要点 |
|---|---------|---------|
| U1 | 作为学生，我想用自然语言问"计算机学院最近有什么通知"，系统应返回近期通知摘要 | 查询 Agent 从 RAG 检索并组织答案 |
| U2 | 作为学生，我想问"某条具体通知的完整内容/链接"，系统应给出详情 | RAG 命中，返回标题+URL+正文 |
| U3 | 作为用户，我想知道"某个从未采集过的网站的通知"，系统应能自动去探索并抓取 | 查询 Agent 调爬虫补充数据入库 |
| U4 | 作为用户，我希望看到某条通知的原始出处，以确认可信 | 回答附带来源 URL |
| U5 | 作为管理员，我希望 RAG 数据保持新鲜（可配置刷新频率），不回答过期信息 | `is_stale()` 触发 `refresh()` |
| U6 | 作为开发者，我希望核心机制在无真实 LLM 时也能被确定性测试 | 主循环/工具分发/guardrail 可 mock LLM 单测 |

## 3. 功能规约

### 3.1 query-agent（查询/编排 Agent）

| 项 | 内容 |
|----|------|
| 输入 | CLI 参数问题文本（`python query.py "问题"`） |
| 行为 | 复用 harness 主循环；装配工具 `rag_search`/`run_crawler`/`read_file`/`run_shell`；自主决策"先搜→不够→爬→再搜→回答" |
| 输出 | 自然语言答案（含来源 URL） |
| 边界 | 无法从 RAG 也未能爬取到 → 明确告知"未找到相关信息" |
| 错误处理 | 爬虫失败 → 回退到已有 RAG 结果；LLM 调用失败 → 重试后报错 |

### 3.2 RAGStore（知识库）

| 项 | 内容 |
|----|------|
| 输入 | crawler 输出的通知 JSONL；查询文本 |
| 行为 | 追加式文档库；倒排索引；`is_stale()`/`refresh()`；`search(query, top_k)` |
| 输出 | 检索结果（doc_id、分数、标题、URL、正文片段） |
| 边界 | 空库 → 返回空；同内容去重（dedup_hash） |
| 错误处理 | 索引损坏 → 重建 |

### 3.2b RAG 详细规约（冷启动验证后明确）

以下语义为权威定义，供实现与测试对照：

- **分片（slice）** = 一个 `docs/<domain>.<date>.jsonl` 文件，slice 标识 = `<domain>.<date>`。`meta.json` 的 `indexed_slices` 元素即此格式。缺 date 的记录统一归入 `docs/<domain>.none.jsonl`。
- **分词**：中文连续字符做 **bigram**（相邻 2 字），单字本身不进索引（仅通过 bigram 出现）；ASCII 单词按 `\w+` 切分并**小写归一**；数字、URL、日期作为整词；无停用词表。示例：`"期末考试安排"` → `{期末,考试,试安,安排}`；`"CS 2026"` → `{cs, 2026}`。
- **打分**：`score = Σ(命中 term 的 tf × idf)`，`tf` 为 term 在 doc 中的频次，`idf = ln(N / df)`，N 为索引文档总数。title 与 content 合并后统一分词计数。按 score 降序取 top_k。
- **索引落盘**：`index/current/index.json` 与 `index/archive/index.json` 各一个文件，结构 `{"terms": {term: {doc_id: tf}}, "docs": [doc, ...]}`。
- **current/archive 流转**：`build_index()` 全量重建两个索引——archive 含全部文档；current 只含 `valid` 非 False 且 `date >= 今天-365天` 的文档。**仅 current 参与 `search()`**；archive 供未来历史检索/统计，本次不暴露查询入口。
- **dedup_hash**：由 RAGStore 在 `ingest()` 内计算，`sha256(url + "|" + title)`。record 自带 dedup_hash 则沿用；重复（全库已存在相同 hash）**丢弃**（不计入返回的 added 数）。
- **crawler→RAG 归一化**：归 `ingest()` 负责。输入即 crawler 原生 schema（`title/url/publishTime|date/content/...`），ingest 内映射为文档 schema：`date` 从 `publishTime` 或 `date` 提取（正则 `\d{4}-\d{2}-\d{2}`）；`domain` 从 url 取 netloc；`content` 缺省时用 `title + " " + url` 兜底。
- **首启行为**：`meta.json` 不存在时 `is_stale()` 返回 **True**（需刷新）；首次 `refresh()` 全量索引所有分片并写 meta。
- **id 生成**：`<domain>.<date>.<序号>`（分片内递增）。`valid` 字段：record 未提供时默认 True。
- **返回 schema**：`search()` 每条返回 `{title, url, date, content, domain, score}`（无 doc_id 字段，doc_id 仅索引内部使用）。

### 3.3 crawler（已有，微调）

| 项 | 内容 |
|----|------|
| 输入 | `--site <url> --days N --max-pages M` |
| 行为 | 按策略爬取通知列表页+详情页，输出 JSONL |
| 输出 | `crawler/data/notices_*.jsonl`（含标题/URL/时间/正文） |
| 边界 | 无策略 → 委托 explorer-agent 生成（模式 A） |
| 错误处理 | 站点不可达 → 报错并跳过 |

### 3.4 explorer-agent（已有，策略 Agent）

按现 SPEC 功能保留：探索网站结构、生成/更新策略 JSON，经 FileStore 管理备份/暂存/崩溃恢复。

## 4. 非功能性需求

| 类别 | 要求 |
|------|------|
| 性能 | RAG 检索 < 200ms（千级文档）；单次查询 Agent 往返 < 60s |
| 可用性 | CLI 交互友好；无 LLM key 时能跑通 RAG 检索（降级） |
| 可观测性 | 轨迹文件记录每步决策；`traces/*.jsonl` |
| 安全 | 见 §7 凭据威胁模型 |

## 5. 系统架构

### 组件图

```
用户 (CLI)
   │  query.py
   ▼
┌─────────────── query-agent ───────────────┐
│  AgentLoop(复用)  Guardrail(复用)  Tracer(复用) │
│  工具: rag_search │ run_crawler │ read_file │ run_shell │
└───────┬──────────────┬───────────────┬─────┘
        │              │               │
   rag_search     run_crawler      read_file/run_shell
        │              │               │
        ▼              ▼               ▼
   ┌────────┐    ┌──────────┐    ┌───────────┐
   │ RAGStore │←─ │ crawler.js│    │ FileStore │
   │ (docs+   │    │ 按策略爬取  │    │ 策略/备份   │
   │  index)  │    │ JSONL输出  │    │ /暂存      │
   └────────┘    └────┬─────┘    └───────────┘
                      │ 无策略时委托
                      ▼
              ┌───────────────┐
              │ explorer-agent │
              │ 生成/更新策略   │
              └───────────────┘
```

### 数据流

1. 用户提问 → query-agent 启动 → `RAGStore.is_stale()` → 陈旧则 `refresh()`
2. Agent 调 `rag_search(query)` → 命中则组织答案（带 URL）返回
3. 未命中 → 调 `run_crawler(site)` → crawler 输出 JSONL → 入库 RAG → 再 `rag_search` → 回答
4. 全过程写入轨迹文件

### 外部依赖

- LLM：CherryIN（OpenAI 兼容端点 `https://open.cherryin.cc/v1`）
- 爬虫：Node.js 18+（内置 http，无 npm 依赖）
- Python 3.11+（openai / pyyaml / httpx / pytest / python-dotenv）

## 6. 数据模型

### 通知文档（JSONL 行）

```json
{
  "id": "cs.nju.edu.cn-2026-03-01-exam-notice",
  "title": "关于2026年春季学期考试安排的通知",
  "url": "https://cs.nju.edu.cn/1702/list.htm",
  "date": "2026-03-01",
  "content": "正文全文...",
  "domain": "cs.nju.edu.cn",
  "crawled_at": "2026-08-06T10:00:00Z",
  "dedup_hash": "sha256hex",
  "valid": true
}
```

### RAG 索引

- `docs/<domain>.<date>.jsonl`：追加式原始文档
- `index/current/` + `index/archive/`：倒排索引（term → 倒排表）
- `meta.json`：`{last_refresh, indexed_slices, refresh_interval_min}`

## 7. 凭据与分发设计

### 凭据威胁模型

| 威胁 | 对策 |
|------|------|
| key 硬编码进源码 | 全部通过 env var / `.env` 加载 |
| key 提交进 Git | `.gitignore` 排除 `.env`；提交前自查 |
| key 写入日志/history | 代码不 log secrets；不 `export` 进 shell history |
| .env 明文暴露 | 说明风险：`.env` 为明文、进程环境可见；生产可用钥匙串/加密文件替代 |
| 首个用户配置困难 | 首启引导安全录入（隐藏输入），支持查看/更新/清除（不回显） |

### 分发设计（容器/包）

- **Python 包分发**（首选）：`pip install` 安装，`whalequery` / `whale-crawl` 两个 CLI 命令
- README 写清：获取方式、运行命令、key 在目标机配置（`.env` 或环境变量）、已知限制
- CI：`.gitlab-ci.yml` 含 `unit-test` job

## 8. 技术选型与理由

| 项 | 选择 | 理由 |
|----|------|------|
| 语言 | Python 3.11+ | Agent 生态成熟、测试友好、跨平台 |
| 爬虫 | Node.js 内置 http | 无 npm 依赖、轻量 |
| LLM | CherryIN deepseek | OpenAI 兼容、免费额度、无需翻墙 |
| RAG | 自研 JSONL + 倒排索引 | 确定性可测、无重依赖；语义检索可插拔预留 |
| 测试 | pytest + mock/stub LLM | 核心机制可确定性单测（B.2） |
| 分发 | PyPI 包 | 单命令安装/运行 |

## 9. 验收标准

| # | 验收项 | 判定方法 |
|---|--------|---------|
| 1 | 查询 Agent 能回答"最近通知" | CLI 提问，返回含 URL 的摘要 |
| 2 | 未采集站点能自动补充 | 对未入库站点提问，触发爬取并入库 |
| 3 | RAG 刷新频率可配 | 改配置，验证 is_stale 阈值变化 |
| 4 | 无 LLM 可确定性测试核心机制 | `make test` 全绿，含 mock LLM 测试 |
| 5 | 凭据不泄露 | grep 源码无 key；.env 被 gitignore |
| 6 | 一键安装运行 | 分发命令从零机器可跑通 |

## 10. 风险与未决问题

| 风险 | 对策/状态 |
|------|----------|
| 中文分词质量 | bigram 方案，检索够用即可，不做语义 |
| 网站结构变化 | 策略可更新；爬虫失败回退已有 RAG |
| LLM 速率限制 | 已实现 5 次指数退避重试 |
| 冷启动验证暴露 spec 缺陷 | 用不同 agent 实测后修订（记入 SPEC_PROCESS） |
| 未决：embedding 语义检索 | 预留接口，MVP 不做 |
| 未决：Web 界面 | CLI 优先，接口预留 |
