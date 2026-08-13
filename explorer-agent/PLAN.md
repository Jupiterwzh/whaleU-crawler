# PLAN.md - 多 Agent 协作系统实现计划

> 状态：A/B 核心实现已完成；工程收尾与真实部署仍待用户执行。
> 更新：2026-08-13

## Goal

构建基于自研 harness 的多 Agent 协作系统：策略 Agent 生成策略，爬虫执行抓取，RAG 管理 Agent 赋予有效时间并维护索引，外层 query-agent 检索并在数据不足时调爬虫补充。

## Architecture

```
用户 -> query-agent（外层问答）
          -> shared/rag（检索）
          -> crawler（补充数据）
                -> explorer-agent（无策略时生成策略）
                -> rag-manager（入库后赋有效时间）
```

## Global Constraints

- 两个 Agent 目录独立复制 harness 内核：`explorer-agent/`、`query-agent/`；`rag-manager/` 为独立管理 Agent。
- RAGStore 位于公共目录 `shared/rag/`。
- 凭据不硬编码、不提交；通过环境变量或 keyring 加载。
- 每个实现 task 采用 TDD，先红后绿；完成后记录 commit hash 和验证结果。
- 默认只跑 focused test；全量测试需用户许可，最终交付前由用户确认。

---

## A 组：策略 Agent 与基础设施（已完成）

### Task A1：explorer-agent harness 核心

- 产出：`explorer-agent/src/{harness,agent_loop,guardrail,tracer}.py`、tools、llm、main.py。
- 能力：主循环、工具分发、guardrail、轨迹、策略入口。
- Commit：`2f1aee5`、`7004735`、`3500457`、`983ce0e`、`bb542ca`、`b117192`、`e82953d`、`4531b41`、`912de11`。
- 状态：完成。

### Task A2：策略交互与可视化

- 产出：步进日志、确认/调整、步数重置、暂存/退出、经验草案。
- Commit：`cfb90d4`、`60701f5`、`4c9833a`、`75f913c`、`f09256d`。
- 状态：完成。

### Task A3：策略文件生命周期

- 产出：`filestore.py`、`preflight.py`、`postflight.py`，三段式入口和原子写。
- 能力：已有策略检查、备份、checkpoint/crash 恢复、y/n 重试。
- Commit：`71732b7`、`b58838d`、`3b50800`、`5021663`、`00f4ef7`、`6b818a5`、`8c644bc`、`5d64329`、`92fc1f6`。
- 状态：完成。

### Task A4：策略结构遍历与验证闭环

- 产出：`structure_tools.py`、`--verify`、经验库 `experiences.json`、`keywords.json`。
- 能力：BFS/visited/domain 限制、home/list/info 分类、编号和锚文本、用户选择、策略生成后实测验证。
- Commit：`3c6b862`、`88521ad`、`e021b85`、`b7d60bb`、`fa1239d`、`5bbb735`、`75f913c` 及后续修复。
- 验证：cs/yzb 真实探索；yzb 4/4 入口验证通过。
- 状态：核心完成；批量站点策略仍由用户按 `111.md` 操作。

---

## B 组：多 Agent、RAG 与交付工程（核心完成）

### Task B1：shared RAGStore

- 产出：`shared/rag/ragstore.py`、validity 字段、current/archive、date/domain/scope 检索、snippet。
- Commit：`8ea830a`、`421cd25`。
- 验证：RAG 98 条真实入库，current 9 条，archive 98 条。
- 状态：完成。

### Task B2：query-agent 独立外层 Agent

- 产出：`query-agent/`，独立 harness、`query.py`、`webui.py`、rag_search/run_crawler 工具和规则。
- 说明：不再把 query 逻辑放在 explorer-agent；query-agent 只管理 RAG/爬虫，不生成策略。
- Commit：`a4262aa`、`860b674`、`a3ad4a3`、`bd12617`。
- 状态：完成；query-agent focused tests 26 个通过。

### Task B3：rag-manager 独立 Agent

- 产出：`rag-manager/`，独立 harness、批量有效时间判定、read/assign/rebuild 工具。
- 有效时间：明确时间链、影响档位 15/30/60/90/180、跨通知关联预留。
- Commit：`9dd93e6`、`a1131f9`、`4a8c015`、`e7a69f8`。
- 状态：完成；真实处理 98/98 条，无 LLM 纯函数兜底测试通过。

### Task B4：工程交付基础

- 产出：`Makefile`、`.gitlab-ci.yml`（`unit-test`）、`Dockerfile`、`.dockerignore`、keyring 凭据存储。
- Commit：`37d8f9f`、`566dd80`、`a187eeb`。
- 状态：配置完成；Docker 构建和 CI 实跑仍待用户执行。

### Task B5：大作业过程文档

- 产出：`SPEC.md`、`PLAN.md`、`SPEC_PROCESS.md`、`REFLECTION.md`、README、task 级 AGENT_LOG。
- 冷启动：不同类型 explore agent、新 session、仅 SPEC+PLAN，暴露 8 个 RAG 规约缺陷并修订 SPEC §3.2b。
- 状态：文档完成，历史偏差已如实记录。

### Task B6：WebUI 单页表单

- 产出：`query-agent/webui.py`，标准库 `http.server`，复用 `query.answer()`。
- 验证：GET/POST focused tests 通过。
- 状态：代码完成，部署 URL 待用户执行。

---

## 当前验证状态

- `explorer-agent`：70 tests pass。
- `query-agent`：26 tests pass。
- `rag-manager`：3 tests pass。
- `crawler`：6 Node tests pass。
- 总计：105 tests pass。
- 真实 RAG 链路：98 条入库、98 条有效时间处理、query 检索带来源 URL，已通过。

## 待用户执行

- CI push 并确认最后一次 `unit-test` pass。
- Docker build/run 验证。
- WebUI 部署为可访问地址。
- query-agent 真实查询和 run_crawler 补数链路再次验收。
- 按 `111.md` 批量生成关注站点策略。
- ndwy VPN 由用户处理。
