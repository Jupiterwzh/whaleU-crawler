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
    store.ingest.return_value = 1
    tools = make_rag_tools(store, "node")
    tool = [t for t in tools if t.name == "run_crawler"][0]
    monkeypatch.setattr("src.tools.rag_tools.subprocess.run", lambda *a, **kw: MagicMock(stdout="", returncode=0))
    out = tool.handler(url="https://cs.nju.edu.cn/")
    assert "cs.nju.edu.cn" in out


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
         patch.object(store, "refresh"), \
         patch("src.tools.rag_tools._trigger_rag_manager") as mock_trigger:
        tool.handler(url="https://cs.nju.edu.cn/")
    mock_trigger.assert_called_once()


def test_run_crawler_archives_output(tmp_path, monkeypatch):
    """L2: run_crawler 入库后把爬虫输出归档到 data/archive/。"""
    from unittest.mock import MagicMock, patch
    from shared.rag.ragstore import RAGStore
    from src.tools.rag_tools import make_rag_tools

    store = RAGStore(str(tmp_path))
    tools = make_rag_tools(store, "node")

    fake_out = tmp_path / "notices_123.jsonl"
    fake_out.write_text('{"title":"t","url":"u","publishTime":"2026-03-01"}\n')

    arch_dir = tmp_path / "archive"
    with patch("subprocess.run", return_value=MagicMock(
            stdout=f"保存到: {fake_out}", returncode=0, stderr="")), \
         patch("src.tools.rag_tools._trigger_rag_manager"):
        tool = [t for t in tools if t.name == "run_crawler"][0]
        tool.handler(url="https://cs.nju.edu.cn/")
    # 归档目录应存在且包含移动后的文件
    assert arch_dir.exists()
    assert list(arch_dir.glob("notices_*.jsonl"))
    assert not fake_out.exists()
