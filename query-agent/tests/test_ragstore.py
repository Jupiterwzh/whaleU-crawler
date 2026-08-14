import json
from shared.rag.ragstore import RAGStore


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


def test_similar_content_dedup(tmp_path):
    """URL 不同但内容完全相同 → 判重（内容去重）。"""
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "计算机学院关于2026年暑期工作的通知", "content": "这是一段足够长的通知正文内容，用于测试内容去重是否会正确判断相同内容为重复记录", "url": "https://x/u1", "domain": "cs.nju.edu.cn", "date": "2026-08-01"}])
    # URL 不同，标题不同，但内容完全相同 → 判重
    store.ingest([{"title": "暑期工作通知(转载)", "content": "这是一段足够长的通知正文内容，用于测试内容去重是否会正确判断相同内容为重复记录", "url": "https://x/u2", "domain": "cs.nju.edu.cn", "date": "2026-08-01"}])
    assert store._doc_count() == 1, "内容相同应判重"


def test_different_content_not_dedup(tmp_path):
    """内容明显不同 → 不算重复。"""
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "计算机学院暑期工作通知", "content": "关于暑期工作的第一段很长的正文内容，包括具体安排和时间地点等详细信息说明", "url": "https://x/u1", "domain": "cs.nju.edu.cn", "date": "2026-08-01"}])
    store.ingest([{"title": "研究生招生面试通知", "content": "关于研究生招生面试的另一段完全不同的正文内容，涉及面试流程和材料准备等", "url": "https://x/u2", "domain": "cs.nju.edu.cn", "date": "2026-08-01"}])
    assert store._doc_count() == 2


def test_content_based_dedup(tmp_path):
    """内容相同（URL/标题不同）→ 判重；内容不同 → 不入重。"""
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "通知A", "content": "这是一段足够长的相同内容正文用于去重测试验证", "url": "https://x/u1", "domain": "cs.nju.edu.cn", "date": "2026-08-01"}])
    # URL/标题不同，但内容完全相同 → 判重
    store.ingest([{"title": "通知B", "content": "这是一段足够长的相同内容正文用于去重测试验证", "url": "https://x/u2", "domain": "cs.nju.edu.cn", "date": "2026-08-01"}])
    assert store._doc_count() == 1, "内容相同应判重"
    # 内容不同 → 不入重
    store.ingest([{"title": "通知C", "content": "这是另一段完全不同的足够长正文内容用于测试", "url": "https://x/u3", "domain": "cs.nju.edu.cn", "date": "2026-08-01"}])
    assert store._doc_count() == 2


def test_empty_content_falls_back_title(tmp_path):
    """content 空时退回标题去重。"""
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "同一标题", "content": "", "url": "https://x/u1", "domain": "cs.nju.edu.cn", "date": "2026-08-01"}])
    # content 空，标题相同 → 判重（退回首标题）
    store.ingest([{"title": "同一标题", "content": "", "url": "https://x/u2", "domain": "cs.nju.edu.cn", "date": "2026-08-01"}])
    assert store._doc_count() == 1


def test_list_by_domain_valid_only_with_validity(tmp_path):
    """list_by_domain 只返回有效期内文档，且每条含 valid_until 字段。"""
    store = RAGStore(str(tmp_path))
    # 一条有效（未来过期）、一条已过期
    store.ingest([{"title": "有效通知", "content": "有效正文足够长", "url": "https://cs/u1", "domain": "cs.nju.edu.cn", "date": "2026-08-01"}])
    store.ingest([{"title": "过期通知", "content": "过期正文足够长", "url": "https://cs/u2", "domain": "cs.nju.edu.cn", "date": "2025-01-01"}])
    # 给过期那条标过期
    store.apply_validity("cs.nju.edu.cn.2025-01-01.1", valid_until="2025-06-01")
    store.build_index()
    hits = store.list_by_domain("cs.nju.edu.cn", 50)
    titles = [h["title"] for h in hits]
    assert "有效通知" in titles
    assert "过期通知" not in titles, "已过期通知不应列出"
    assert "valid_until" in hits[0], "每条应含 valid_until 字段"


def test_search_returns_validity(tmp_path):
    """search 返回含 valid_until 字段。"""
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "考试通知", "content": "考试安排正文足够长", "url": "https://cs/u1", "domain": "cs.nju.edu.cn", "date": "2026-08-01"}])
    store.apply_validity("cs.nju.edu.cn.2026-08-01.1", valid_until="2026-12-31")
    store.build_index()
    hits = store.search("考试", top_k=5)
    assert len(hits) == 1
    assert hits[0]["valid_until"] == "2026-12-31"
