# SPEC.md — rag-manager（第 3 个独立 Agent）设计规格

> 版本 1.0 | 更新：2026-08-12
> 定位：多 Agent 协作系统的 **RAG 管理 Agent**，为文档分配有效时间并重建索引，保证查询结果新鲜。

---

## 1. 问题陈述与职责边界

query-agent 查询时依赖 `current` 索引中的"有效文档"。文档入库后若长期未标注有效期（valid_until / effective_days），过期通知会一直出现在查询结果里。**rag-manager 的职责**：

1. 读取 `pending_validity()`（缺有效时间字段的文档）
2. 逐条判定有效时间（LLM 判定，纯函数 `judge_validity` 确定性兜底）
3. `apply_validity` 写回 → `build_index` 重建索引

**边界**：只写有效时间字段与索引，绝不删文档、不改正文、不抓网页。

## 2. 与其它组件的关系

```
数据库更新 (Task 4 触发)
   │
   ▼
rag-manager (本目录)
   │  read_rag_docs / assign_validity / rebuild_index
   ▼
RAGStore (shared/rag/ragstore.py)  ←  pending_validity / apply_validity / build_index
   │
   ▼
judge_validity (shared/rag/validity.py)  ←  纯函数判定底座
```

- **RAGStore** 在 `shared/rag/`（公共位置），Task 1 扩展了有效期字段管理
- **judge_validity** 纯函数（Task 2），确定性判定：时间范围词+日期 → `valid_until`；无时间戳 → 影响词映射 `effective_days`
- harness 内核 `src/` 真复制自 `query-agent/src`（含注释"与 query-agent/src 同步"）

## 3. 功能规约

### 3.1 工具集

| 工具 | 用途 | 说明 |
|------|------|------|
| `read_rag_docs` | 读待判定文档 | 入参 domain/limit，输出标题/日期/正文片段 |
| `assign_validity` | 写回有效时间 | 入参 doc_id + valid_until 或 effective_days |
| `rebuild_index` | 重建索引 | 调 `build_index()`，current + archive 两级 |

**刻意排除**：`fetch_url`/`write_file`/`run_shell`——管理 Agent 不需要网络与文件副作用。

### 3.2 入口与主流程

- 入口：`python rag_manager.py --domain <x>`（--domain 预留，当前整批处理）
- 编程接口：`RagManager(rag_store).run() -> str`（返回处理摘要）
- `RagManager._llm_judge(doc)`：默认回退纯函数 `judge_validity(doc.content, doc.date)`，无 LLM 也可确定性运行

## 4. 非功能性需求

- 批处理：一次 run 处理全部 pending 文档，逐个 try/except，单条失败不中断
- 无 LLM key 降级：`_llm_judge` 纯函数兜底，可完全无 LLM 运行
- 可观测：返回摘要（处理/成功/失败条数），轨迹记录走 harness tracer

## 5. B.2 确定性测试设计

- 主循环/工具分发/guardrail 复用自研 harness 内核（`src/`）
- `test_manager_run_assigns_validity`：mock `_llm_judge`，run() 后 `pending_validity() == []`（不依赖 LLM）
- `test_manager_tools_registered`：`build_harness()` 注册了 3 个工具

## 6. 待办/未决

- [ ] Task 4 接入：数据库更新后自动触发 `run()`
- [ ] --domain 按域名过滤的实际实现（当前整批处理）
- [ ] LLM 判定的真实端到端验证
