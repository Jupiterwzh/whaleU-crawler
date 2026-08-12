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


def test_manager_pure_fn_fallback_no_llm(tmp_path, monkeypatch):
    """B.2: 不 mock _llm_judge，走 judge_validity 纯函数兜底（无 LLM 也能赋有效时间）。"""
    monkeypatch.chdir(Path(__file__).parent.parent)
    store = RAGStore(str(tmp_path))
    # 含明确时间范围词的通知
    store.ingest([{"title": "考试安排", "content": "选课时间 2026-03-01 至 2026-03-15，请及时完成",
                   "url": "u1", "domain": "cs.nju.edu.cn", "date": _mkdate(1)}])
    m = RagManager(store)  # 不 patch _llm_judge → 走纯函数
    result = m.run()
    assert "成功分配 1 条" in result
    assert store.pending_validity() == []
    # 验证 valid_until 被赋为 2026-03-15（文本中最晚日期）
    docs = store._load_all()
    assert docs[0].get("valid_until") == "2026-03-15"
