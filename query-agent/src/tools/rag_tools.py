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
        snippet = (hit.get("snippet") or hit.get("content") or "").strip()
        if snippet:
            lines.append(f"   正文片段: {snippet[:100]}")
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
        rec = {
            "title": title,
            "content": content,
            "url": url,
            "domain": _domain_of(url) or fallback_domain,
            "date": _norm_date(raw.get("publishTime") or raw.get("date")),
        }
        # 保留附件/多媒体标志（PDF/图片/视频型通知正文在附件里，用户需知道）
        if raw.get("attachments"):
            rec["attachments"] = raw["attachments"]
        if raw.get("hasVideo") or raw.get("hasAudio"):
            rec["hasVideo"] = bool(raw.get("hasVideo"))
            rec["hasAudio"] = bool(raw.get("hasAudio"))
        records.append(rec)
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


def _archive_output(out_path: Path | None):
    """把已入库的爬虫输出移动到 data/archive/，避免下次被重复扫描。"""
    if not out_path or not out_path.exists():
        return
    arch_dir = out_path.parent / "archive"
    arch_dir.mkdir(parents=True, exist_ok=True)
    dest = arch_dir / out_path.name
    try:
        out_path.rename(dest)
    except OSError:
        pass


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


# 站点候选清单（从南京大学院系/官方网页清单解析，见 crawler/data/sites.json）
_SITES_JSON = Path(__file__).resolve().parent.parent.parent.parent / "crawler" / "data" / "sites.json"


def make_rag_tools(rag_store, crawler_script: str, strategies_dir: str = "") -> list[Tool]:
    """装配 query-agent（分发 Agent）的工具：rag_search / run_crawler / check_strategy / run_explorer。"""

    def rag_search(query: str, top_k: int = 5, domain: str = None) -> str:
        """检索 RAG；可指定 domain 过滤（如查某站点全部通知）。"""
        return _format_search_results(rag_store.search(query, top_k, domain=domain))

    def check_strategy(domain: str) -> str:
        """检查 crawler 策略目录里是否存在该域名的策略 JSON。"""
        if not strategies_dir:
            return f"策略目录未配置，无法检查 {domain} 是否存在策略"
        sdir = Path(strategies_dir)
        cand = sdir / f"{domain}.json"
        if cand.is_file():
            return f"策略存在：{cand}"
        # 也检查 .draft.json 草稿
        draft = sdir / f"{domain}.draft.json"
        if draft.is_file():
            return f"策略草稿存在（未确认）：{draft}"
        return f"策略不存在：{domain} 尚无策略文件"

    def list_sites() -> str:
        """列出站点候选（siteName + domain），供对照用户提到的机构。

        优先读取 crawler/data/sites.json（南京大学院系/官方网页清单，112 站点）；
        无该文件时 fallback 到策略目录 meta。
        """
        if _SITES_JSON.exists():
            try:
                sites = json.loads(_SITES_JSON.read_text(encoding="utf-8"))
                lines = ["已知站点候选（sites.json）："]
                for s in sites:
                    name = s.get("name", "")
                    domain = s.get("domain", "")
                    cat = s.get("category", "")
                    if name and domain:
                        lines.append(f"  - {name} ({domain})" + (f" [{cat}]" if cat else ""))
                if len(lines) > 1:
                    return "\n".join(lines)
            except (json.JSONDecodeError, OSError):
                pass
        # fallback：策略目录 meta
        if not strategies_dir:
            return "策略目录未配置，且无 sites.json，无法列出候选站点"
        sdir = Path(strategies_dir)
        lines = ["已知站点候选（策略 meta）："]
        for p in sorted(sdir.glob("*.json")):
            if p.name.endswith(".draft.json") or p.name == "sites.json":
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                meta = data.get("meta", {})
            except (json.JSONDecodeError, OSError):
                continue
            name = meta.get("siteName", "")
            domain = meta.get("domain", p.stem)
            lines.append(f"  - {name} ({domain})")
        if len(lines) == 1:
            return "当前无已知站点候选（sites.json 与策略目录均为空）"
        return "\n".join(lines)

    def run_explorer(url: str, timeout: int = 300) -> str:
        """唤起 explorer-agent 生成/更新该站点的爬取策略（--explore-only）。"""
        import subprocess as sp
        agent_main = Path(__file__).resolve().parent.parent.parent.parent / "explorer-agent" / "main.py"
        try:
            proc = sp.run(
                ["python", str(agent_main), "--explore-only", url],
                capture_output=True, text=True, timeout=timeout,
            )
            tail = (proc.stdout or "").strip()
            if proc.returncode != 0:
                return f"策略 Agent 失败（{url}）: 退出码 {proc.returncode}，{(proc.stderr or '').strip()[:300]}"
            return f"策略 Agent 已为 {url} 运行完毕（exit 0）。输出尾段：\n{tail[-400:]}"
        except (FileNotFoundError, subprocess.SubprocessError, OSError, ValueError) as e:
            return f"策略 Agent 唤起失败: {e}"

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
            _archive_output(out_path)
            return f"已抓取 {len(records)} 条并入库 RAG，来源 {url}"
        except (FileNotFoundError, subprocess.SubprocessError, OSError, ValueError) as e:
            return f"爬虫失败: {e}"

    return [
        Tool(
            name="rag_search",
            description="在已入库的通知 RAG 中检索，返回命中条目的标题/日期/URL/正文片段；可指定 domain 过滤（如 cs.nju.edu.cn）。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词（查某站点全部通知时可用通用词如'通知'）"},
                    "top_k": {"type": "integer", "description": "返回条数，默认 5；问'所有/全部通知'时用 20~50"},
                    "domain": {"type": "string", "description": "按域名过滤（如 cs.nju.edu.cn），可选"},
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
        Tool(
            name="check_strategy",
            description="检查 crawler 策略目录中是否存在指定域名（如 cs.nju.edu.cn）的策略 JSON。返回存在/不存在及路径。",
            parameters={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "域名，如 cs.nju.edu.cn"},
                },
                "required": ["domain"],
            },
            handler=check_strategy,
            require_approval=False,
        ),
        Tool(
            name="list_sites",
            description="列出已知站点候选（siteName + domain），用于把用户提到的机构/学院对照到具体站点。",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=list_sites,
            require_approval=False,
        ),
        Tool(
            name="run_explorer",
            description="唤起策略 Agent（explorer-agent）分析站点结构并生成爬取策略 JSON。用于站点尚无策略时。",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "站点根 URL，如 https://software.nju.edu.cn/"},
                },
                "required": ["url"],
            },
            handler=run_explorer,
            require_approval=True,
        ),
    ]
