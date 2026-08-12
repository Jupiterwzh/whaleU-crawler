from unittest.mock import MagicMock

from shared.rag.ragstore import RAGStore
from src.tools.rag_tools import make_rag_tools


def test_rag_search_formats_results(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "考试通知", "content": "期末安排", "url": "https://cs.nju.edu.cn/u1", "domain": "cs.nju.edu.cn", "date": "2026-03-01"}])
    store.refresh()
    tools = make_rag_tools(store, "node")
    tool = [t for t in tools if t.name == "rag_search"][0]
    out = tool.handler(query="考试")
    assert "考试通知" in out and "cs.nju.edu.cn" in out


def test_rag_search_no_match(tmp_path):
    store = RAGStore(str(tmp_path))
    store.refresh()
    tools = make_rag_tools(store, "node")
    tool = [t for t in tools if t.name == "rag_search"][0]
    assert "无匹配" in tool.handler(query="xyz")


def test_run_crawler_invokes_and_ingests(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from src.tools.rag_tools import make_rag_tools
    store = MagicMock()
    tools = make_rag_tools(store, "node")
    tool = [t for t in tools if t.name == "run_crawler"][0]
    monkeypatch.setattr("src.tools.rag_tools.subprocess.run", lambda *a, **kw: MagicMock(stdout="", returncode=0))
    out = tool.handler(url="https://cs.nju.edu.cn/")
    assert "cs.nju.edu.cn" in out
