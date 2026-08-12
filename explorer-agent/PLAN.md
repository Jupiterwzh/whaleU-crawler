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

- [x] 完成（commit `8ea830a`）：RAGStore 全实现，4 测试通过

## Task B2: query-agent 工具装配

**Files:**
- Create: `explorer-agent/src/tools/rag_tools.py`
- Test: `explorer-agent/tests/test_rag_tools.py`

**Interfaces:**
- Consumes: `RAGStore`（Task B1）
- Produces: `make_rag_tools(rag_store, crawler_script)` → `[Tool(rag_search), Tool(run_crawler)]`

- [x] 完成（commit `860b674`）：rag_search/run_crawler 工具，3 测试通过

## Task B3: query.py 入口

**Files:**
- Create: `explorer-agent/query.py`
- Modify: `explorer-agent/src/harness.py`（rag_store 可选参数）
- Test: `explorer-agent/tests/test_query.py`

**依赖:** Task B1, B2
**实现要点:** 复用 AgentLoop/harness；装配 rag/爬虫/文件工具；`RAGStore.is_stale() → refresh()`；输出答案。

- [x] 完成（commit `a3ad4a3`）：query.py 入口 + harness rag 支持，4 测试 + 回归通过

## Task B4: 工程收尾

**Files:**
- Create: `Makefile`（`make test` = pytest）
- Create: `.gitlab-ci.yml`（`unit-test` job）
- Create: `Dockerfile` / `.dockerignore`（容器分发）
- Create: `explorer-agent/src/keys.py`（keyring 凭据存储）
- Modify: `README.md`、`.env.example`、`requirements.txt`

**依赖:** 全部 B1-B3
**实现要点:** 凭据安全存储（keyring 钥匙串 + getpass 隐藏录入 + get/set/clear）；Docker 分发（docker build + docker run）；CI（unit-test job）。

- [x] 完成（commit `37d8f9f`）：Makefile/CI/Docker/keyring 全部实现，56 测试通过

## Task B5: 冷启动验证 + 过程文档

**Files:**
- Create: `SPEC_PROCESS.md`
- Create: `REFLECTION.md`
- Modify: `AGENT_LOG.md`（作业格式）

**依赖:** 全部
**实现要点:** 用不同 agent 新 session 仅凭 SPEC+PLAN 实现 B1 部分 task；记录暴露的 spec 缺陷；写反思报告。

- [ ] 待完成

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
- B 组：B1-B4 完成（56 测试通过），B5 进行中
