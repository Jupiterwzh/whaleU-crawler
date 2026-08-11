# PLAN.md — 多 Agent 协作系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> 更新：2026-08-06
> 说明：任务分两部分——**A 组已完成**（explorer-agent/crawler/FileStore，附 commit hash）与 **B 组待实现**（RAG + query-agent + 工程收尾）。

**Goal:** 构建基于 harness 的多 Agent 协作系统：策略 Agent 生成爬取策略 → 爬虫抓取通知 → RAG 存储/检索 → 查询 Agent 用自然语言回答。

**Architecture:** 复用现有 harness 组件（agent_loop/guardrail/tracer），新增 RAGStore 存储层与 query-agent 入口，装配 rag_search/run_crawler 等工具。

**Tech Stack:** Python 3.11+、Node.js 18+、pytest、CherryIN LLM。

## Global Constraints

- 目录结构：`data/rag/docs`（文档库）、`data/rag/index`（current/archive 索引）、`data/rag/meta.json`
- 凭据不硬编码：LLM key 走 `.env`/环境变量，不 commit
- 核心机制可 mock LLM 确定性测试（B.2）
- RAG 刷新间隔可配置（`refresh_interval_min`），不硬编码
- 每个 task 完成即更新本 PLAN 并标 commit hash

---

# A 组：已完成任务（历史实现）

## Task A1: explorer-agent harness 核心（已完成）

**Files:** `explorer-agent/src/{harness,agent_loop,guardrail,tracer}.py`、`src/tools/*`、`src/llm/client.py`、`main.py`
**依赖:** 无
**验证:** 20 测试
**Commits:** `2f1aee5`(init) `7004735`(harness) `3500457`(loop) `983ce0e`(guardrail) `bb542ca`(tracer) `b117192`(main) `e82953d`(fix loop) `4531b41`(refine) `912de11`(adapt tests)
- [x] 完成：主循环/工具分发/guardrail/轨迹/入口全实现，41 测试通过

## Task A2: 交互确认 + 步进可视化（已完成）

**Files:** `explorer-agent/src/agent_loop.py`、`rules/AGENTS.md`
**依赖:** Task A1
**Commits:** `cfb90d4`(交互确认+步数重置) `60701f5`(5次调整+备份) `4c9833a`(步进日志)
- [x] 完成：探索完成后用户确认/反馈、步数重置、暂存/退出、思考→动作→结果可视化

## Task A3: FileStore + 三段式流程（已完成）

**Files:** `explorer-agent/src/{filestore,preflight,postflight}.py`、`main.py`
**依赖:** Task A1
**Commits:** `71732b7`(filestore) `b58838d`(preflight) `3b50800`(postflight) `5021663`(main重构) `00f4ef7`(路径fix) `6b818a5`(DATA_DIR) `8c644bc`(crash) `5d64329`(原子写) `92fc1f6`(y/n强制)
- [x] 完成：策略/备份/暂存/crash 统一管理，前导检查+Agent+后导保存三段式

## Task A4: LLM 重试 + 注入防御 + 交互优化（已完成）

**Files:** `explorer-agent/src/llm/client.py`、`src/agent_loop.py`、`src/preflight.py`、`src/guardrail.py`
**依赖:** Task A1
**Commits:** `566dd80`(重试) `55eeefe`(注入防御) `75f913c`(暂存/退出+规则)
- [x] 完成：429 指数退避、用户反馈注入防护、y/n 强制匹配

---

# B 组：待实现任务（当前进行）

## Task B1: RAGStore 存储层

**Files:**
- Create: `explorer-agent/src/rag/__init__.py`
- Create: `explorer-agent/src/rag/ragstore.py`
- Test: `explorer-agent/tests/test_ragstore.py`

**Interfaces:**
- Produces: `RAGStore(base_dir, refresh_interval_min=30)` with methods:
  - `ingest(records: list[dict])` — 追加到 docs 分片，去重
  - `build_index(slice_filter=None)` — 建/重建倒排索引（current/archive）
  - `search(query: str, top_k: int = 5) -> list[dict]` — 检索
  - `is_stale() -> bool` — 距上次刷新 > interval
  - `refresh()` — 增量索引新分片 + 更新 meta

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ragstore.py
import json
from src.rag.ragstore import RAGStore


def test_ingest_and_search(tmp_path):
    store = RAGStore(str(tmp_path), refresh_interval_min=30)
    store.ingest([{"title": "考试安排通知", "content": "期末考试安排", "url": "u1", "domain": "cs.nju.edu.cn", "date": "2026-03-01"}])
    hits = store.search("考试")
    assert len(hits) >= 1
    assert hits[0]["title"] == "考试安排通知"


def test_search_no_match(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "考试", "content": "考试安排", "url": "u1", "domain": "d"}])
    assert store.search("奖学金") == []


def test_is_stale_fresh(tmp_path, monkeypatch):
    import time
    store = RAGStore(str(tmp_path), refresh_interval_min=30)
    store.ingest([{"title": "t", "content": "c", "url": "u", "domain": "d", "date": "2026-01-01"}])
    store.refresh()
    assert store.is_stale() is False


def test_dedup(tmp_path):
    store = RAGStore(str(tmp_path))
    rec = {"title": "t", "content": "c", "url": "u1", "domain": "d", "date": "2026-01-01"}
    store.ingest([rec])
    store.ingest([rec])
    assert store._doc_count() == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_ragstore.py -v
```
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 RAGStore**

要点：
- 分词：中文 bigram（2-gram）+ 英文按空格/标点
- 倒排索引：`{term: {doc_id: tf}}`，文档 `{doc_id: {title,url,date,content,domain,valid}}`
- 检索打分：简化 BM25（tf × idf），返回 top_k
- `is_stale()`：`time.time() - meta.last_refresh > refresh_interval_min*60`
- `refresh()`：扫描 `docs/` 未索引分片 → 追加索引 → 更新 meta
- current 索引只含 `valid:true` 且未过期；archive 含全部
- `_doc_count()` 返回 docs 总数（供测试）

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_ragstore.py -v
```
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
cd /home/wangzhiheng/whaleU-crawler && git add explorer-agent/src/rag/ explorer-agent/tests/test_ragstore.py && git commit -m "feat: RAGStore — JSONL doc store + inverted index + stale/refresh"
```

## Task B2: query-agent 工具装配

**Files:**
- Create: `explorer-agent/src/tools/rag_tools.py`
- Modify: `explorer-agent/src/harness.py`（支持多工具工厂）
- Modify: `explorer-agent/agent.yaml`（query 段）
- Test: `explorer-agent/tests/test_rag_tools.py`

**Interfaces:**
- Consumes: `RAGStore`（Task B1）
- Produces: `make_rag_tools(rag_store)` → `[Tool(rag_search), Tool(run_crawler)]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_rag_tools.py
from src.rag.ragstore import RAGStore
from src.tools.rag_tools import make_rag_tools


def test_rag_search_tool(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "通知", "content": "关于考试", "url": "u", "domain": "d", "date": "2026-01-01"}])
    tools = make_rag_tools(store)
    rag_search = [t for t in tools if t.name == "rag_search"][0]
    result = rag_search.handler({"query": "考试", "top_k": 3})
    assert "通知" in result
```

- [ ] **Step 2: 失败 → Step 3: 实现 → Step 4: 通过 → Step 5: 提交**

实现要点：`rag_search` 调 `store.search()`；`run_crawler` 用 `subprocess` 调 `CRAWLER_SCRIPT` 后 ingest 输出 JSONL。

## Task B3: query.py 入口

**Files:**
- Create: `explorer-agent/query.py`
- Modify: `explorer-agent/agent.yaml`
- Test: `explorer-agent/tests/test_query.py`

**依赖:** Task B1, B2
**实现要点:** 复用 AgentLoop/harness；装配 rag/爬虫/文件工具；`RAGStore.is_stale() → refresh()`；输出答案。

## Task B4: 工程收尾

**Files:**
- Create: `Makefile`（`make test` = pytest）
- Create: `.gitlab-ci.yml`（`unit-test` job）
- Create: `pyproject.toml` / `setup.py`（分发）
- Create: `explorer-agent/keys.py`（钥匙串/加密凭据存储）
- Modify: `README.md`、`.env.example`

**依赖:** 全部 B1-B3
**实现要点:** 凭据安全存储（keyring 或加密文件）；分发配置；CI。

## Task B5: 冷启动验证 + 过程文档

**Files:**
- Create: `SPEC_PROCESS.md`
- Create: `REFLECTION.md`
- Modify: `AGENT_LOG.md`（作业格式）

**依赖:** 全部
**实现要点:** 用不同 agent 新 session 仅凭 SPEC+PLAN 实现 B1 部分 task；记录暴露的 spec 缺陷；写反思报告。

---

## 依赖图

```
B1 RAGStore ──► B2 rag_tools ──► B3 query.py
   └───────────────► B4 工程收尾 ◄──────────┘
                       │
                       ▼
                    B5 冷启动+文档
```

- **可并行**：B4 的凭据存储部分可与 B1 并行
- **串行依赖**：B1→B2→B3 严格串行

## 当前进度

- A 组：全部完成（41 测试通过）
- B 组：B1 进行中
