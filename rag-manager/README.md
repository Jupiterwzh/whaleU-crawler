# rag-manager — RAG 管理 Agent

> 多 Agent 协作系统中的 RAG 管理组件：为文档分配有效时间并重建索引，保证查询结果新鲜。
> 详细设计见 `SPEC.md`。

---

## 交互模式（重要）

**rag-manager 是确定性批处理 Agent，不支持自然语言交互**——它通过命令行参数（`--ingest`/`--dedupe`/`--rag-dir` 等）执行确定性任务，**不启动 LLM Agent 循环**。

三个 Agent 的交互模式对比：

| Agent | 交互模式 | 入口示例 |
|-------|---------|---------|
| **explorer-agent** | LLM Agent（自然语言 + 工具编排 + 交互确认） | `python main.py "探索 xxx"` |
| **query-agent** | LLM Agent（自然语言 + 分发编排） | `python query.py "最近有什么通知"` |
| **rag-manager** | **确定性批处理**（命令行参数，无自然语言） | `python rag_manager.py --ingest` |

**为什么**：rag-manager 的职责（入库/判有效期/去重/重建索引）是**确定性任务**——有效期判定用纯函数 `judge_validity` 兜底（无 LLM 也能跑），批量处理更可靠，且符合"核心机制无 LLM 可确定性测试"（作业 B.2）。用户**通过 query-agent 分发链间接触发**它（run_crawler 入库后自动触发判有效期）。

---

## 职责

**只做三件事**：
1. 读取 `pending_validity()`（缺有效时间字段的文档）
2. 逐条判定有效时间（`judge_validity` 纯函数兜底，无 LLM 也能跑）
3. `apply_validity` 写回 → `build_index` 重建索引

**边界（绝不越界）**：
- ❌ **不删除文档**——过时内容通过有效期排除，而非物理删除
- ❌ 不抓网页、不 ingest 新数据
- ✅ 只写有效时间字段（valid_from/valid_until/effective_days）与索引

---

## 工作流程

```
新文档入库（ingest）→ 缺有效时间字段 → 成为 pending_validity
   → rag-manager.run():
       pending_validity() → 逐条判定有效期 → apply_validity 写回
       → build_index 重建（current 只含仍有效，过期的进 archive 不参与查询）
```

### 关键概念

| 概念 | 说明 |
|------|------|
| `pending_validity()` | 缺 `valid_until` 且缺 `effective_days` 的文档 |
| `current` 索引 | 只含 `valid` 非 False 且未过期的文档，**查询用它** |
| `archive` 索引 | 含全部文档（含过期），供历史检索（当前无查询入口） |
| `_is_valid()` | 有效期判定：valid_until > 今天；否则 valid_from + effective_days > 今天；无有效时间默认有效 |
| `judge_validity` | 纯函数判定底座（shared/rag/validity.py），确定性可测 |

### 过时通知怎么处理？

不删除，而是**标过期**：
- rag-manager 给通知分配 `valid_until`（或 `effective_days`）
- `build_index` 后，过期的通知**不进入 current 索引**（查询搜不到），但保留在 archive/docs
- 所以"删除过时结果"= 自动从查询结果中排除，不物理删

---

## 用法

### 触发方式

**方式 A（推荐）：入库 + 处理一条命令**

```bash
cd rag-manager
python rag_manager.py --ingest
# 入库 crawler/data 的爬虫产物（notices_*.jsonl，内容去重）
# → 处理待判定文档（判有效时间）→ 重建索引 → 一次性询问是否删除已收录的爬虫产物
```

**方式 B：通过 query-agent 分发链自动触发**

```bash
cd query-agent
python query.py "cs.nju.edu.cn 最近有什么通知"
# run_crawler 自动 ingest 爬虫产物 + 触发 rag-manager 判有效期
```

**方式 C：只处理已入库的 pending**

```bash
cd rag-manager
python rag_manager.py
# 只处理缺有效时间字段的文档 → 重建索引（不 ingest）
```

> 入库是 rag-manager 的职责：`ingest_notices` 工具 / `--ingest` 命令行选项，读取爬虫产物入库（内容去重）。

### 参数

```bash
python rag_manager.py --ingest          # 先入库爬虫产物，再处理 pending
python rag_manager.py --ingest --dedupe # 入库 + 去重
python rag_manager.py --dedupe          # 只去重（删除内容重复文档）
python rag_manager.py --ingest --notices-dir <路径>  # 指定爬虫产物目录
python rag_manager.py --rag-dir <路径>   # 指定 RAG 目录（默认自动推导）
python rag_manager.py --domain <域名>    # 预留，当前整批处理
```

### 去重（dedupe_docs）

`--dedupe` 扫描 RAG，删除**内容重复**的文档（同一内容 key 多份时保留一条，优先含有效时间的），重建索引。用于清理存量重复（如旧版 url+title 去重漏掉的同内容不同 URL 记录）。

### 爬虫产物清理

`rag_manager.py --ingest` 处理完 pending 后，会扫描 `crawler/data/notices_*.jsonl`：
- 收集**全部记录都已入库**的文件，**一次性询问**："以下 N 个爬虫产物已全部收录，是否全部删除？(y=全删/n=全保留)"
- y → 全部删除；n → 全部保留（不逐文件询问）
- 未全部入库的文件**不询问**（可能有未收录记录，删除会丢数据）
- 这是"收录完成 → 清理中间产物"的流程，避免 notices 文件堆积

> 注意：删除的是**爬虫原始输出**（notices jsonl），**不影响 RAG 里的文档**。RAG 文档仍按有效期机制管理，不物理删除。

---

## 常见问题

| 现象 | 说明 |
|------|------|
| `已处理 0 条待判定文档` | 没有 pending——要么无新入库，要么已有有效时间。先 ingest 新数据再跑 |
| 查询搜不到某条通知 | 它可能已过期（valid_until 过了），被 current 索引排除，属预期 |
| 需要删除某条文档 | rag-manager 不支持删除（边界）。如确需清理，手动编辑 docs 分片并重建索引 |
