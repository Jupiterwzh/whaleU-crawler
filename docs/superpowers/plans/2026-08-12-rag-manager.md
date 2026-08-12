# RAG 管理 Agent + 检索增强 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> 更新：2026-08-12

**Goal:** 实现独立 RAG 管理 Agent（赋予通知有效时间、管理 RAG 生命周期，入库后自动触发），并为 RAG 检索增加时间/domain/archive 能力。

**Architecture:** 扩展 `shared/rag/ragstore.py`（有效时间字段 + current 过滤 + 检索增强）；新建 `rag-manager/` 独立 Agent（真复制 harness 内核）；query-agent 的 run_crawler 入库后触发 rag_manager。

**Tech Stack:** Python 3.11+、pytest、CherryIN LLM。

## Global Constraints

- RAGStore 在 `shared/rag/`（公共位置），两 Agent 引用
- 有效时间字段：`valid_from` / `valid_until` / `effective_days`（无明确时间戳时 15/30/60/90/180）
- current 索引只含仍有效（`valid_until >= 今天`）文档，过期进 archive
- RAG 管理 Agent 独立 harness（真复制 query-agent/src 内核）
- 有效时间判定逻辑抽纯函数，确定性单测
- 入库（ingest 新增>0）后自动触发 rag_manager

---

### Task 1: shared/rag 扩展——有效时间字段 + current 过滤 + 检索增强

**Files:**
- Modify: `shared/rag/ragstore.py`
- Modify: `shared/rag/__init__.py`（若需导出）
- Test: `query-agent/tests/test_ragstore.py`（已有，扩展）
- Test: `query-agent/tests/test_rag_validity.py`（新建）

**Interfaces:**
- Produces:
  - `search(query, top_k=5, date_from=None, date_to=None, domain=None, scope="current")` —— R1/R2/R3
  - `pending_validity() -> list[dict]` —— 返回缺 valid_until/effective_days 的文档
  - `apply_validity(doc_id, valid_from, valid_until=None, effective_days=None) -> bool` —— 写回有效时间字段
  - `build_index()` 改为按有效时间过滤 current

- [ ] **Step 1: 写失败测试**

创建 `query-agent/tests/test_rag_validity.py`：

```python
import json
import time
from pathlib import Path
from shared.rag.ragstore import RAGStore


def _mkdate(days_ago):
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() - days_ago * 86400))


def test_search_domain_filter(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "a", "content": "x", "url": "u1", "domain": "cs.nju.edu.cn", "date": _mkdate(1)}])
    store.ingest([{"title": "b", "content": "x", "url": "u2", "domain": "jw.nju.edu.cn", "date": _mkdate(1)}])
    store.refresh()
    hits = store.search("x", domain="cs.nju.edu.cn")
    assert len(hits) == 1
    assert hits[0]["domain"] == "cs.nju.edu.cn"


def test_search_date_range(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "旧", "content": "x", "url": "u1", "domain": "d", "date": _mkdate(100)}])
    store.ingest([{"title": "新", "content": "x", "url": "u2", "domain": "d", "date": _mkdate(1)}])
    store.refresh()
    hits = store.search("x", date_from=_mkdate(30))
    assert len(hits) == 1
    assert hits[0]["title"] == "新"


def test_search_archive_scope(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "旧", "content": "x", "url": "u1", "domain": "d", "date": _mkdate(700)}])  # >365天 进 archive
    store.refresh()
    assert store.search("x") == []            # current 无
    assert len(store.search("x", scope="archive")) == 1  # archive 有


def test_pending_validity_and_apply(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "t", "content": "c", "url": "u1", "domain": "d", "date": _mkdate(1)}])
    pending = store.pending_validity()
    assert len(pending) == 1
    did = pending[0]["id"]
    ok = store.apply_validity(did, valid_from=_mkdate(1), valid_until=_mkdate(10))
    assert ok
    assert store.pending_validity() == []


def test_current_excludes_expired(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "过期", "content": "x", "url": "u1", "domain": "d", "date": _mkdate(1)}])
    store.refresh()
    pending = store.pending_validity()
    store.apply_validity(pending[0]["id"], valid_from=_mkdate(1), valid_until=_mkdate(0))  # 今天已过期
    store.refresh()
    assert store.search("x") == []
    assert len(store.search("x", scope="archive")) == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/wangzhiheng/whaleU-crawler/query-agent && python -m pytest tests/test_rag_validity.py -v
```
Expected: FAIL（AttributeError: search 无 domain/date_from 参数等）

- [ ] **Step 3: 实现 ragstore.py 扩展**

修改 `shared/rag/ragstore.py`：

```python
def search(self, query: str, top_k: int = 5, date_from: str = None,
           date_to: str = None, domain: str = None, scope: str = "current") -> list[dict]:
    index_dir = self._current if scope == "current" else self._archive
    data = self._load_index(index_dir)
    if not data:
        return []
    terms, docs = data["terms"], data["docs"]
    doc_id_to_doc = {d["id"]: d for d in docs}
    n = len(docs)
    if n == 0:
        return []
    query_terms = self._tokenize(query)
    if not query_terms:
        return []
    scores = {}
    for term in set(query_terms):
        postings = terms.get(term)
        if not postings:
            continue
        df = len(postings)
        idf = math.log(n / df)
        for doc_id, tf in postings.items():
            scores[doc_id] = scores.get(doc_id, 0.0) + tf * idf
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    result = []
    for doc_id, score in ranked:
        doc = doc_id_to_doc[doc_id]
        d = doc.get("date", "")
        dom = doc.get("domain", "")
        if domain and dom != domain:
            continue
        if date_from and d < date_from:
            continue
        if date_to and d > date_to:
            continue
        result.append({
            "title": doc.get("title", ""),
            "url": doc.get("url", ""),
            "date": d,
            "content": doc.get("content", ""),
            "domain": dom,
            "score": round(score, 4),
        })
    return result


def _is_valid(self, doc: dict) -> bool:
    """有效时间判定：valid_until >= 今天；无则 valid_from + effective_days >= 今天。"""
    today = time.strftime("%Y-%m-%d", time.gmtime())
    valid_until = doc.get("valid_until") or ""
    if valid_until:
        return valid_until >= today
    valid_from = doc.get("valid_from") or doc.get("date") or ""
    days = doc.get("effective_days")
    if valid_from and days:
        import datetime as _dt
        from datetime import timedelta
        until = (_dt.date.fromisoformat(valid_from) + timedelta(days=int(days))).isoformat()
        return until >= today
    return True  # 无有效时间信息则默认有效


def build_index(self):
    all_docs = self._load_all()
    cutoff = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 365 * 86400))
    current_docs = [d for d in all_docs if d.get("valid", True) and self._is_valid(d)]
    self._write_index(self._current, current_docs)
    self._write_index(self._archive, all_docs)


def pending_validity(self) -> list[dict]:
    """返回缺有效时间字段的文档。"""
    out = []
    for p in self._docs.glob("*.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            doc = json.loads(line)
            if not doc.get("valid_until") and not doc.get("effective_days"):
                out.append(doc)
    return out


def apply_validity(self, doc_id: str, valid_from: str = None,
                   valid_until: str = None, effective_days: int = None) -> bool:
    """按 doc_id 找到文档所在分片，重写该行的有效时间字段。"""
    for p in self._docs.glob("*.jsonl"):
        lines = p.read_text(encoding="utf-8").splitlines()
        found = False
        new_lines = []
        for line in lines:
            if not line.strip():
                new_lines.append(line)
                continue
            doc = json.loads(line)
            if doc.get("id") == doc_id:
                if valid_from:
                    doc["valid_from"] = valid_from
                if valid_until:
                    doc["valid_until"] = valid_until
                if effective_days:
                    doc["effective_days"] = effective_days
                found = True
            new_lines.append(json.dumps(doc, ensure_ascii=False))
        if found:
            p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            return True
    return False
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/wangzhiheng/whaleU-crawler/query-agent && python -m pytest tests/test_rag_validity.py tests/test_ragstore.py -q
```
Expected: 全部通过（含原有 test_ragstore.py 无回归）

- [ ] **Step 5: 提交**

```bash
cd /home/wangzhiheng/whaleU-crawler && git add shared/rag/ragstore.py query-agent/tests/test_rag_validity.py && git commit -m "feat: RAGStore validity fields + current/archive filter + date/domain/scope search"
```

---

### Task 2: 有效时间判定纯函数

**Files:**
- Create: `shared/rag/validity.py`
- Test: `query-agent/tests/test_validity.py`

**Interfaces:**
- Produces: `judge_validity(text, date=None, related=None) -> dict`（返回 `{valid_from, valid_until|effective_days, reason}`）
  - 纯函数，不调 LLM；供 RAG 管理 Agent 的 rules/工具作为确定性底座
  - 无明确时间戳 → 按影响程度关键词映射档位（"改造/工程"→180，"通知/安排"→30 等，可调）

- [ ] **Step 1: 写失败测试**

创建 `query-agent/tests/test_validity.py`：

```python
from shared.rag.validity import judge_validity, extract_dates


def test_extract_dates():
    text = "报名时间：2026-03-01 至 2026-03-15，比赛时间 2026-04-01"
    dates = extract_dates(text)
    assert "2026-03-15" in dates
    assert "2026-04-01" in dates


def test_judge_no_timestamp_maps_impact():
    r = judge_validity("食堂将进行改造施工，工期约两个月")
    assert r["effective_days"] in (15, 30, 60, 90, 180)


def test_judge_explicit_until():
    r = judge_validity("选课时间：3月1日至3月15日，请按时完成选课", date="2026-03-01")
    assert r["valid_until"]
```

- [ ] **Step 2: 失败 → Step 3: 实现 → Step 4: 通过 → Step 5: 提交**

实现要点（`shared/rag/validity.py`）：
- `extract_dates(text)`：正则提取所有日期（`\d{4}[-/年]\d{1,2}[-/月]\d{1,2}`）
- `judge_validity(text, date=None)`：
  - 有"至/截止/结束/期间"等时间范围词 → 取最晚日期为 valid_until
  - 无时间戳 → 按影响程度关键词映射档位（改造/工程→180；搬迁/停用→90；通知/公示→60；活动/安排→30；默认→15）
  - `valid_from` 默认 = 发布日 date
- 纯函数，无 LLM 依赖

---

### Task 3: rag-manager/ 独立 Agent

**Files:**
- Create: `rag-manager/`（复制 query-agent/src 内核：harness/agent_loop/guardrail/tracer/tools/llm/keys）
- Create: `rag-manager/rag_manager.py`（入口）
- Create: `rag-manager/agent.yaml`
- Create: `rag-manager/rules/rag_manager_AGENTS.md`
- Create: `rag-manager/guardrails/policy.yaml`
- Create: `rag-manager/tests/test_rag_manager.py`
- Create: `rag-manager/SPEC.md`
- Create: `rag-manager/requirements.txt`

**Interfaces:**
- Consumes: `shared/rag/ragstore.py`（Task 1 扩展）、`shared/rag/validity.py`（Task 2）
- Produces: `rag_manager.py` 入口：`python rag_manager.py --domain <x>`；`RagManager.run(rag_store) -> str`

**工具集**：
- `read_rag_docs(domain=None, limit=50)` — 读待处理（pending_validity）或指定通知，供分析
- `assign_validity(doc_id, valid_until=None, effective_days=None)` — 调 `apply_validity` 写回
- `rebuild_index()` — 调 `build_index()` 重建
- 纯函数 `judge_validity` 作为 rules 的一部分（确定性底座）

- [ ] **Step 1: 写失败测试**

创建 `rag-manager/tests/test_rag_manager.py`：

```python
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from shared.rag.ragstore import RAGStore
from rag_manager import RagManager


def _mkdate(days_ago):
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() - days_ago * 86400))


def test_manager_run_assigns_validity(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).parent.parent)
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "考试安排", "content": "考试时间3月1日至3月10日", "url": "u1", "domain": "cs.nju.edu.cn", "date": _mkdate(1)}])
    # mock LLM：直接调 assign_validity（跳过真实 LLM）
    from rag_manager import RagManager
    m = RagManager(store)
    with patch.object(m, "_llm_judge", side_effect=lambda doc: {
        "doc_id": doc["id"], "valid_from": _mkdate(1), "valid_until": _mkdate(10)}):
        m.run()
    assert store.pending_validity() == []


def test_manager_tools_registered(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).parent.parent)
    store = RAGStore(str(tmp_path))
    from rag_manager import RagManager
    m = RagManager(store)
    h = m.build_harness()
    names = h.tools.names()
    assert "read_rag_docs" in names
    assert "assign_validity" in names
    assert "rebuild_index" in names
```

- [ ] **Step 2: 失败 → Step 3: 实现 → Step 4: 通过 → Step 5: 提交**

实现要点：
- `rag-manager/src/` 复制自 query-agent/src（真复制，含注释"与 query-agent/src 同步"）
- `RagManager.__init__(rag_store)`：装配工具
- `run()`：读 pending → 逐条 LLM 判定（或纯函数 judge_validity）→ assign_validity → rebuild_index
- `_llm_judge(doc)`：调用 LLM 判定有效时间（可被 mock）；默认用 `judge_validity` 纯函数兜底
- agent.yaml 装配 read_rag_docs/assign_validity/rebuild_index 工具

---

### Task 4: 触发链路——query-agent 入库后自动触发

**Files:**
- Modify: `query-agent/src/tools/rag_tools.py`（run_crawler 入库后触发）
- Test: `query-agent/tests/test_rag_tools.py`（扩展）

**依赖:** Task 1-3

- [ ] **Step 1: 写失败测试**

```python
def test_run_crawler_triggers_rag_manager(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, patch
    from shared.rag.ragstore import RAGStore
    from src.tools.rag_tools import make_rag_tools
    store = RAGStore(str(tmp_path))
    tools = make_rag_tools(store, "node")
    tool = [t for t in tools if t.name == "run_crawler"][0]
    with patch("subprocess.run", return_value=MagicMock(stdout="保存到: /tmp/out.jsonl", returncode=0, stderr="")), \
         patch("src.tools.rag_tools.Path.is_file", return_value=True), \
         patch("src.tools.rag_tools.Path.read_text", return_value='{"title":"t","url":"u","publishTime":"2026-03-01"}\n'), \
         patch("src.tools.rag_tools._trigger_rag_manager") as mock_trigger:
        tool.handler(url="https://cs.nju.edu.cn/")
    mock_trigger.assert_called_once()
```

- [ ] **Step 2: 失败 → Step 3: 实现 → Step 4: 通过 → Step 5: 提交**

实现要点：`run_crawler` 的 `rag_store.ingest(records)` 后，若 `added > 0` 则调用 `_trigger_rag_manager(rag_store)`（导入 rag_manager.RagManager 跑一轮）。`_trigger_rag_manager` 作为模块函数便于 mock。

---

### Task 5: 文档同步

- [ ] **Step 1**: 更新 `explorer-agent/SPEC.md` 架构图（补 RAG 管理 Agent 层）
- [ ] **Step 2**: 更新 `README.md`（组件表加 RAG 管理 Agent；目录结构加 rag-manager/）
- [ ] **Step 3**: 更新 `AGENT_LOG.md`（会话十二实现记录 + 摘要表）
- [ ] **Step 4**: 更新 `待办.md`（勾掉已完成的 RAG 管理/检索增强项）
- [ ] **Step 5**: 提交

---

## 依赖图

```
Task 1 (shared/rag 扩展)
   │
   ├──► Task 2 (validity 纯函数)
   │        │
   │        ▼
   │    Task 3 (rag-manager Agent)
   │             │
   │             ▼
   │        Task 4 (触发链路)
   │             │
   ▼             ▼
Task 5 (文档同步，收尾)
```

- **可并行**：Task 2 可与 Task 1 并行（validity 独立）
- **串行依赖**：Task 3 依赖 Task 1+2；Task 4 依赖 Task 1-3

## 当前进度

- Task 1-5：待实现
