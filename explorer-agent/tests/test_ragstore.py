import json
from src.rag.ragstore import RAGStore


def test_ingest_and_search(tmp_path):
    store = RAGStore(str(tmp_path), refresh_interval_min=30)
    store.ingest([{"title": "考试安排通知", "content": "期末考试安排", "url": "u1", "domain": "cs.nju.edu.cn", "date": "2026-03-01"}])
    store.build_index()
    hits = store.search("考试")
    assert len(hits) >= 1
    assert hits[0]["title"] == "考试安排通知"


def test_search_no_match(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "考试", "content": "考试安排", "url": "u1", "domain": "d", "date": "2026-01-01"}])
    store.build_index()
    assert store.search("奖学金") == []


def test_is_stale_fresh(tmp_path):
    store = RAGStore(str(tmp_path), refresh_interval_min=30)
    store.ingest([{"title": "t", "content": "c", "url": "u", "domain": "d", "date": "2026-01-01"}])
    store.refresh()
    assert store.is_stale() is False


def test_dedup(tmp_path):
    store = RAGStore(str(tmp_path))
    rec = {"title": "t", "content": "c", "url": "u1", "domain": "d", "date": "2026-01-01"}
    store.ingest([rec])
    store.ingest([rec])
    assert store._doc_count() == 1
