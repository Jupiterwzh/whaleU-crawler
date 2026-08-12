# SPEC.md — query-agent（外层 Agent）设计规格

> 版本 1.0 | 更新：2026-08-12
> 定位：多 Agent 协作系统的**外层 Agent**，管理 RAG 与爬虫，回答用户通知问题。

---

## 1. 问题陈述与职责边界

多 Agent 系统中，策略 Agent（`explorer-agent/`）负责生成/管理爬取策略；**query-agent 是外层 Agent**，直接面向用户，职责是：

1. **管理 RAG**：检索通知知识库，回答用户问题
2. **管理爬虫**：RAG 数据不足时，调用爬虫抓取补充并自动入库 RAG

**职责链**：用户提问 → rag_search 检索 RAG → 不足 → run_crawler 调爬虫 →（爬虫无策略时委托内层策略 Agent 生成策略）→ 数据入库 RAG → 再检索 → 回答。

## 2. 与其它组件的关系

```
用户 (CLI query.py / WebUI webui.py)
   │
   ▼
query-agent (本目录)
   │  rag_search / run_crawler / read_file
   ▼
RAGStore (shared/rag/)  ←→  crawler (crawler/)
                              │ 无策略时
                              ▼
                         explorer-agent (策略 Agent，独立目录)
```

- **RAGStore** 在 `shared/rag/`（公共位置，非任一 Agent 专属）
- **crawler** 是独立执行者，query-agent 通过 `run_crawler` 工具调用
- **策略 Agent** 独立在 `explorer-agent/`，query-agent 不直接调用它——由爬虫无策略时自动委托

## 3. 功能规约

### 3.1 工具集（独立装配，无 explorer 工具）

| 工具 | 用途 | 说明 |
|------|------|------|
| `rag_search` | 检索 RAG | 输入 query/top_k，输出命中条目 |
| `run_crawler` | 调爬虫抓取 + 自动入库 RAG | 输入 url/days/max_pages |
| `read_file` | 读文件 | 辅助（保留但规则约束不代替爬虫） |

**刻意排除**：`fetch_url`/`write_file`/`run_shell`——防止外层 Agent 绕过爬虫手动抓取或写策略。

### 3.2 行为流程

```
问题 → RAGStore.is_stale()? → 陈旧则 refresh()
     → rag_search
     → 命中 → 组织答案（附 URL）
     → 未命中 → run_crawler → 数据 ingest → refresh → 再 rag_search → 回答
```

## 4. 非功能性需求

- 检索 < 200ms（千级文档）
- 无 LLM key 时降级：可跑通 RAG 检索
- 轨迹记录每步决策（traces/）

## 5. B.2 确定性测试设计

- 主循环/工具分发/guardrail 复用自研 harness 内核（`src/` 真复制自 explorer-agent）
- RAGStore 纯 Python，确定性单测
- query 决策用 mock LLM 验证工具分发（rag_search → run_crawler 顺序）

## 6. 待办/未决

- [ ] run_crawler 真实入库验证
- [ ] RAG 检索能力增强（发布时间过滤、archive 检索入口）
