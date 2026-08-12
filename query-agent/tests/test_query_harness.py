# tests/test_query_harness.py
from pathlib import Path
from shared.rag.ragstore import RAGStore
from src.harness import Harness


def test_query_agent_has_correct_tools(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).parent.parent)
    store = RAGStore(str(tmp_path))
    h = Harness.from_yaml("agent.yaml", rag_store=store)
    names = h.tools.names()
    # query-agent 只用 rag + read_file，无 fetch_url/write_file/run_shell
    assert "rag_search" in names
    assert "run_crawler" in names
    assert "read_file" in names
    assert "fetch_url" not in names
    assert "write_file" not in names
    assert "run_shell" not in names
