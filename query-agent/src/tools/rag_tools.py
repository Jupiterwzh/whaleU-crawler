"""内建工具：RAG 检索 + 调爬虫入库（供 query-agent 使用）。"""
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from .registry import Tool

_SAVE_RE = re.compile(r"保存到:\s*(\S+)")
_NOTICES_RE = re.compile(r"(\S*notices_\d+\.jsonl)")
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _domain_of(url: str) -> str:
    return urlparse(url).netloc


def _norm_date(value: str) -> str:
    m = _DATE_RE.search(value or "")
    return m.group(1) if m else (value or "")


def _format_search_results(hits: list[dict]) -> str:
    if not hits:
        return "RAG 无匹配结果"
    lines = [f"命中 {len(hits)} 条："]
    for i, hit in enumerate(hits, 1):
        lines.append(f"{i}. [{hit.get('date', '')}] {hit.get('title', '')} ({hit.get('url', '')})")
        content = (hit.get("content", "") or "").strip()
        if content:
            lines.append(f"   正文片段: {content[:100]}")
    return "\n".join(lines)


def _to_ingest_records(jsonl_path: Path, fallback_domain: str) -> list[dict]:
    records = []
    for line in jsonl_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        url = raw.get("url") or raw.get("href") or ""
        title = raw.get("title", "")
        content = raw.get("content") or f"{title} {url}".strip()
        records.append({
            "title": title,
            "content": content,
            "url": url,
            "domain": _domain_of(url) or fallback_domain,
            "date": _norm_date(raw.get("publishTime") or raw.get("date")),
        })
    return records


def _find_output_file(stdout: str, crawler_script: str) -> Path | None:
    for m in [_SAVE_RE.search(stdout), _NOTICES_RE.search(stdout)]:
        if m:
            p = Path(m.group(1))
            if p.is_absolute():
                return p
            return Path(crawler_script).resolve().parent.parent.parent / p
    data_dir = Path(crawler_script).resolve().parent.parent.parent / "data"
    candidates = sorted(data_dir.glob("notices_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _trigger_rag_manager(rag_store):
    """入库后触发 rag-manager 跑一轮：分配有效时间并重建索引。"""
    _add_rag_manager_path()
    from rag_manager import RagManager

    RagManager(rag_store).run()


def _add_rag_manager_path() -> None:
    """把 rag-manager/ 目录加入 sys.path，使 rag_manager 包可导入。"""
    _RAG_MANAGER_DIR = Path(__file__).resolve().parent.parent.parent.parent / "rag-manager"
    if str(_RAG_MANAGER_DIR) not in sys.path:
        sys.path.insert(0, str(_RAG_MANAGER_DIR))


def make_rag_tools(rag_store, crawler_script: str) -> list[Tool]:
    """装配 query-agent 的两个工具：rag_search 与 run_crawler。"""

    def rag_search(query: str, top_k: int = 5) -> str:
        return _format_search_results(rag_store.search(query, top_k))

    def run_crawler(url: str, days: int = 30, max_pages: int = 5) -> str:
        try:
            proc = subprocess.run(
                ["node", crawler_script, "--site", url, "--days", str(days),
                 "--max-pages", str(max_pages)],
                capture_output=True, text=True, timeout=600,
            )
            if proc.returncode != 0:
                return f"爬虫失败: 退出码 {proc.returncode}，{proc.stderr.strip()[:200]}"
            out_path = _find_output_file(proc.stdout, crawler_script)
            records = _to_ingest_records(out_path, fallback_domain=_domain_of(url)) if out_path else []
            added = rag_store.ingest(records)
            if added > 0:
                _trigger_rag_manager(rag_store)
            rag_store.refresh()
            return f"已抓取 {len(records)} 条并入库 RAG，来源 {url}"
        except (FileNotFoundError, subprocess.SubprocessError, OSError, ValueError) as e:
            return f"爬虫失败: {e}"

    return [
        Tool(
            name="rag_search",
            description="在已入库的通知 RAG 中检索，返回命中条目的标题/日期/URL/正文片段。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词"},
                    "top_k": {"type": "integer", "description": "返回条数，默认 5"},
                },
                "required": ["query"],
            },
            handler=rag_search,
            require_approval=False,
        ),
        Tool(
            name="run_crawler",
            description="调用 JS 爬虫抓取指定站点通知，解析结果并入库 RAG（会自动刷新索引）。",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要抓取的站点 URL"},
                    "days": {"type": "integer", "description": "只保留最近 N 天的通知，默认 30"},
                    "max_pages": {"type": "integer", "description": "最多翻页数，默认 5"},
                },
                "required": ["url"],
            },
            handler=run_crawler,
            require_approval=True,
        ),
    ]
