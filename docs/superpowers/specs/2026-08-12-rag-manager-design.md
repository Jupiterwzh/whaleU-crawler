# 设计：RAG 管理 Agent（有效时间赋予 + RAG 生命周期管理）

> 日期：2026-08-12
> 状态：已批准（架构定案）
> 关联：query-agent/、shared/rag/、crawler/

---

## 1. 背景与动机

爬虫入库的通知只有原始字段（title/content/url/date），**没有"有效时间"**。用户查询"最近有什么通知"时，current 索引按 `date >= 今天-365天`（我此前的假设）粗过滤，无法反映通知的真实有效期（如"比赛颁奖结束"或"选课截止"后即失效）。

**有效时间定义**（用户明确）：**从信息发布到全流程结束、后续影响消除的整段时期。**

赋予有效时间是**语义理解任务**（解析时间戳链、跨通知关联、按影响程度推断），需要 LLM 决策——因此构建独立 RAG 管理 Agent。

## 2. 有效时间规则

| 类型 | 例子 | 有效时间 |
|------|------|---------|
| 明确时间戳链 | 比赛 | 发布 → 报名 → 赛程 → 公示 → 颁奖路演结束 |
| 无明确时间戳 | 食堂改造 | 按影响程度赋 15/30/60/90/180 天 |
| 部分明确 | 选课通知 | 发布 → 选课结束 |
| 跨通知关联 | 选课名额增加 | 发布 → 选课结束（从选课通知取） |

**存储字段**（写入 RAG 文档）：
- `valid_from`: 生效时间（通常 = 发布时间）
- `valid_until`: 失效时间（ISO 日期）
- `effective_days`: 无明确时间戳时的推断有效期天数（15/30/60/90/180）

**current 索引过滤**：只含 `valid_until >= 今天`（或 `valid_until` 为空时 `valid_from + effective_days >= 今天`）的文档；过期自动从 current 排除（进 archive）。

## 3. 架构与职责

```
爬虫爬完 → JSONL → RAGStore.ingest()
                      │
                      ▼ 触发（每次数据库更新）
              RAG 管理 Agent（独立 harness）
                      │ read_rag_docs（批量读新增+库内相关通知）
                      │ assign_validity（分析语义→写 valid_from/until/days）
                      │ rebuild_index（按有效时间重建 current）
                      ▼
              shared/rag/（current 只含仍有效）
                      │
query-agent（最外层）→ rag_search → 检索已赋有效期的文档 → 回答
```

- **RAG 管理 Agent** 独立 harness（真复制内核），工具：
  - `read_rag_docs`（读新增通知 + 库内同域名/同主题相关通知，支持跨通知关联）
  - `assign_validity`（把有效时间字段写回文档）
  - `rebuild_index`（重建 current，按有效时间过滤）
- **触发**：每次数据库更新（ingest 后）自动调用，非 query-agent 调用时
- **query-agent 最外层**：可直接/间接调用所有工具（含 RAG 管理）

## 4. 触发链路设计

关键点：入库后自动触发 RAG 管理，而非等 query。实现方式：

- `RAGStore.ingest()` 返回新增数；新增 > 0 时触发 `rag_manager.run()`（在 query-agent 的 run_crawler 工具内部，或独立调度）
- 也可提供独立入口 `python -m rag_manager --domain <x>` 供定时/手动触发

## 5. 批量处理与跨通知关联

- 每次处理**一批新增通知**（同域名优先）
- `read_rag_docs` 除新增外，允许读库内相关通知（同域名 / 标题关键词相关），供"选课名额增加→从选课通知取时间"类关联
- 输出格式：对每条通知给出 `{doc_id, valid_from, valid_until | effective_days, reason}`

## 6. B.2 确定性测试设计

- RAG 管理 Agent 的 harness 是自研（真复制内核），可 mock LLM
- 有效时间**判定逻辑**（时间戳链解析、effective_days 档位）抽成纯函数，确定性单测
- mock LLM 返回固定 validity 判定，验证工具分发（read_rag_docs → assign_validity → rebuild_index 顺序）
- current 索引过滤正确性（过期文档被排除）单测

## 7. 受影响文件

| 文件 | 改动 |
|------|------|
| `rag-manager/`（新目录） | 独立 Agent：src(复制内核)/rag_manager.py/agent.yaml/rules/tests/SPEC.md |
| `shared/rag/ragstore.py` | 增加有效时间字段支持、current 过滤逻辑、`pending_validity()` 查询待处理通知 |
| `query-agent/src/tools/rag_tools.py` | run_crawler 入库后触发 rag_manager |
| `explorer-agent/SPEC.md` | 架构图补 RAG 管理 Agent |
| `README.md` / `AGENT_LOG.md` | 同步 |

## 8. 未决问题

- RAG 管理 Agent 的 rules 提示词：如何准确解析各类时间戳？需实例调优
- 触发具体实现：run_crawler 内部同步触发 vs 独立调度器？
- archive 是否保留"已过期但 5 年内"的完整归档（是，archive 含全部）
