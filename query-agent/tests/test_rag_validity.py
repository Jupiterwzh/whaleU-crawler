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


def test_search_returns_snippet(tmp_path):
    """R4: search 返回命中词附近片段。"""
    store = RAGStore(str(tmp_path))
    long_text = "前文占位。" * 100 + "考试安排通知。正式内容。" + "后文占位。" * 100
    store.ingest([{"title": "考试通知", "content": long_text, "url": "u1", "domain": "d", "date": _mkdate(1)}])
    store.refresh()
    hits = store.search("考试", top_k=1)
    assert len(hits) == 1
    snip = hits[0].get("snippet", "")
    assert "考试" in snip
    assert len(snip) <= 140  # 前后60字 + 命中词


def test_search_snippet_short_content(tmp_path):
    """内容很短时 snippet 返回全文。"""
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "t", "content": "关于考试的简短通知", "url": "u1", "domain": "d", "date": _mkdate(1)}])
    store.refresh()
    hits = store.search("考试", top_k=1)
    assert "考试" in hits[0]["snippet"]
    assert hits[0]["content"] == "关于考试的简短通知"
