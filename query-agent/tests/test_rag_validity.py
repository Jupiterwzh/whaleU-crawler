import time
from shared.rag.ragstore import RAGStore


def _mkdate(days_ago):
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() - days_ago * 86400))


def test_search_domain_filter(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "a", "content": "x", "url": "u1", "domain": "cs.nju.edu.cn", "date": _mkdate(1)}])
    store.ingest([{"title": "b", "content": "x", "url": "u2", "domain": "jw.nju.edu.cn", "date": _mkdate(1)}])
    store.refresh()
    hits = store.search("x", domain="cs.nju.edu.cn")
    assert len(hits) == 1
    assert hits[0]["domain"] == "cs.nju.edu.cn"


def test_search_date_range(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "旧", "content": "x", "url": "u1", "domain": "d", "date": _mkdate(100)}])
    store.ingest([{"title": "新", "content": "x", "url": "u2", "domain": "d", "date": _mkdate(1)}])
    store.refresh()
    hits = store.search("x", date_from=_mkdate(30))
    assert len(hits) == 1
    assert hits[0]["title"] == "新"


def test_search_archive_scope(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "旧", "content": "x", "url": "u1", "domain": "d", "date": _mkdate(700)}])  # >365天 进 archive
    store.refresh()
    assert store.search("x") == []            # current 无
    assert len(store.search("x", scope="archive")) == 1  # archive 有


def test_pending_validity_and_apply(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "t", "content": "c", "url": "u1", "domain": "d", "date": _mkdate(1)}])
    pending = store.pending_validity()
    assert len(pending) == 1
    did = pending[0]["id"]
    ok = store.apply_validity(did, valid_from=_mkdate(1), valid_until=_mkdate(10))
    assert ok
    assert store.pending_validity() == []


def test_current_excludes_expired(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "过期", "content": "x", "url": "u1", "domain": "d", "date": _mkdate(1)}])
    store.refresh()
    pending = store.pending_validity()
    store.apply_validity(pending[0]["id"], valid_from=_mkdate(1), valid_until=_mkdate(0))  # 今天已过期
    store.refresh()
    assert store.search("x") == []
    assert len(store.search("x", scope="archive")) == 1
