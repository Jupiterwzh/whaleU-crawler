# tests/test_query.py
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.harness import Harness
from src.rag.ragstore import RAGStore


def test_harness_with_rag_store(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).parent.parent)
    h = Harness.from_yaml("agent.yaml", rag_store=RAGStore(str(tmp_path)))
    assert "rag_search" in h.tools.names()
    assert "run_crawler" in h.tools.names()
    assert "查询 Agent" in h.system_prompt


def test_harness_without_rag_store(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).parent.parent)
    h = Harness.from_yaml("agent.yaml")
    assert "rag_search" not in h.tools.names()
    assert "run_crawler" not in h.tools.names()


def test_query_creates_ragstore(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).parent.parent)
    monkeypatch.setenv("RAG_DIR", str(tmp_path / "rag"))
    monkeypatch.setattr("sys.argv", ["query.py", "期末考试"])
    import query
    fake_store = MagicMock()
    with patch.object(query, "RAGStore", return_value=fake_store) as mock_cls, \
         patch.object(query, "LLMClient") as mock_llm, \
         patch.object(query, "AgentLoop", autospec=True):
        fake_loop = query.AgentLoop.return_value
        fake_loop.run.return_value = "答案"
        query.main()
    mock_cls.assert_called_once_with(str(tmp_path / "rag"))
    fake_store.is_stale.assert_called_once()
    fake_loop.run.assert_called_once()


def test_query_main(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).parent.parent)
    monkeypatch.setenv("RAG_DIR", str(tmp_path / "rag"))
    monkeypatch.setattr("sys.argv", ["query.py", "什么时候考试"])
    import query
    fake_store = MagicMock()
    fake_store.is_stale.return_value = False
    with patch.object(query, "RAGStore", return_value=fake_store), \
         patch.object(query, "LLMClient") as mock_llm, \
         patch.object(query, "AgentLoop", autospec=True):
        fake_loop = query.AgentLoop.return_value
        fake_loop.run.return_value = "6月20日"
        query.main()
    fake_loop.run.assert_called_once()
    goal = fake_loop.run.call_args[0][0]
    assert "用户问题" in goal
    assert "什么时候考试" in goal
