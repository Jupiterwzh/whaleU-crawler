"""内建工具：RAG 管理三件套（read_rag_docs / assign_validity / rebuild_index）。

供 rag-manager 使用。与 query-agent/src 同步（改动需同步回 query-agent）。
"""
from .registry import Tool

# 模块级默认 store：由 rag_manager.RagManager 在装配前注入（set_rag_store）。
# harness.py 的 from_yaml 以无参方式调用 factory()，故采用注入式而非参数式。
_DEFAULT_STORE = None


def set_rag_store(store):
    global _DEFAULT_STORE
    _DEFAULT_STORE = store


def make_rag_manager_tools() -> list[Tool]:
    """返回 RAG 管理三件套工具。依赖已通过 set_rag_store 注入的 store。"""

    def _store():
        if _DEFAULT_STORE is None:
            raise RuntimeError("未注入 RAGStore：请先调用 set_rag_store(store)")
        return _DEFAULT_STORE

    def read_rag_docs(domain: str = None, limit: int = 50) -> str:
        """读待处理（pending_validity）文档，可选按 domain 过滤，供分析。"""
        docs = _store().pending_validity()
        if domain:
            docs = [d for d in docs if d.get("domain") == domain]
        docs = docs[:limit]
        if not docs:
            return "无待处理有效时间的文档"
        lines = [f"待处理 {len(docs)} 条："]
        for i, d in enumerate(docs, 1):
            lines.append(
                f"{i}. [{d.get('date', '')}] {d.get('title', '')} "
                f"(id={d['id']}, domain={d.get('domain', '')})"
            )
            content = (d.get("content", "") or "").strip()
            if content:
                lines.append(f"   正文: {content[:100]}")
        return "\n".join(lines)

    def assign_validity(doc_id: str, valid_until: str = None, effective_days: int = None) -> str:
        """为指定文档写回有效时间（valid_until 或 effective_days 至少一个）。"""
        if valid_until is None and effective_days is None:
            return "参数错误：valid_until 与 effective_days 至少填一个"
        ok = _store().apply_validity(
            doc_id, valid_until=valid_until, effective_days=effective_days
        )
        if not ok:
            return f"未找到文档: {doc_id}"
        return f"已为 {doc_id} 写入有效时间（valid_until={valid_until}, effective_days={effective_days}）"

    def rebuild_index() -> str:
        """重建 current/archive 两级索引。"""
        _store().build_index()
        return "索引已重建（current + archive）"

    def ingest_notices(notices_dir: str = None) -> str:
        """读取 crawler/data 的爬虫产物（notices_*.jsonl）入库 RAG（内容去重）。"""
        import json as _json
        from pathlib import Path
        from urllib.parse import urlparse

        if not notices_dir:
            _proj = Path(__file__).resolve().parent.parent.parent.parent
            notices_dir = str(_proj / "crawler" / "data")
        ndir = Path(notices_dir)
        records = []
        for p in sorted(ndir.glob("notices_*.jsonl"), key=lambda x: x.stat().st_mtime):
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    raw = _json.loads(line)
                except _json.JSONDecodeError:
                    continue
                url = raw.get("url") or ""
                title = raw.get("title", "")
                records.append({
                    "title": title,
                    "content": raw.get("content") or f"{title} {url}".strip(),
                    "url": url,
                    "domain": urlparse(url).netloc if "://" in url else "",
                    "date": (raw.get("publishTime") or raw.get("date") or "")[:10],
                })
        if not records:
            return f"未找到爬虫产物（{ndir} 下无 notices_*.jsonl）"
        added = _store().ingest(records)
        return f"入库 {len(records)} 条记录，新增 {added} 条（其余去重丢弃）"

    return [
        Tool(
            name="ingest_notices",
            description="读取 crawler/data 的爬虫产物（notices_*.jsonl）入库 RAG，内容去重。返回新增条数。",
            parameters={
                "type": "object",
                "properties": {
                    "notices_dir": {"type": "string", "description": "notices 目录，默认 crawler/data"},
                },
                "required": [],
            },
            handler=ingest_notices,
            require_approval=False,
        ),
        Tool(
            name="read_rag_docs",
            description="读取待判定有效时间的 RAG 文档列表（可指定 domain/limit），供分析。",
            parameters={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "按域名过滤，默认全部"},
                    "limit": {"type": "integer", "description": "最多返回条数，默认 50"},
                },
                "required": [],
            },
            handler=read_rag_docs,
            require_approval=False,
        ),
        Tool(
            name="assign_validity",
            description="为指定文档写回有效时间（valid_until 或 effective_days）。",
            parameters={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "文档 ID"},
                    "valid_until": {"type": "string", "description": "有效期止（yyyy-mm-dd）"},
                    "effective_days": {"type": "integer", "description": "有效天数"},
                },
                "required": ["doc_id"],
            },
            handler=assign_validity,
            require_approval=False,
        ),
        Tool(
            name="rebuild_index",
            description="重建 current/archive 两级索引。",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=rebuild_index,
            require_approval=False,
        ),
    ]
