import time
from pathlib import Path
from unittest.mock import patch

from shared.rag.ragstore import RAGStore
from rag_manager import RagManager


def _mkdate(days_ago):
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() - days_ago * 86400))


def test_manager_run_assigns_validity(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).parent.parent)
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "考试安排", "content": "考试时间3月1日至3月10日", "url": "u1", "domain": "cs.nju.edu.cn", "date": _mkdate(1)}])
    m = RagManager(store)
    with patch.object(m, "_llm_judge", side_effect=lambda doc: {
        "doc_id": doc["id"], "valid_from": _mkdate(1), "valid_until": _mkdate(10)}):
        m.run()
    assert store.pending_validity() == []


def test_manager_tools_registered(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).parent.parent)
    store = RAGStore(str(tmp_path))
    m = RagManager(store)
    h = m.build_harness()
    names = h.tools.names()
    assert "read_rag_docs" in names
    assert "assign_validity" in names
    assert "rebuild_index" in names
