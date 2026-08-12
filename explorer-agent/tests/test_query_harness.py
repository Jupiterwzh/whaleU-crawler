# tests/test_query_harness.py
from pathlib import Path
from src.harness import Harness
from src.rag.ragstore import RAGStore


def test_query_entry_has_rag_tools_no_fetch(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).parent.parent)
    store = RAGStore(str(tmp_path))
    h = Harness.from_yaml("agent.yaml", rag_store=store, entry="query")
    names = h.tools.names()
    assert "rag_search" in names
    assert "run_crawler" in names
    assert "read_file" in names
    assert "fetch_url" not in names
    assert "write_file" not in names
    assert "run_shell" not in names


def test_main_entry_has_explorer_tools(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).parent.parent)
    h = Harness.from_yaml("agent.yaml")
    names = h.tools.names()
    assert "fetch_url" in names
    assert "write_file" in names
    assert "rag_search" not in names
