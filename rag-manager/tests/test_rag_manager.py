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


def test_cleanup_notices_all_ingested_deletes(tmp_path, monkeypatch):
    """收录完成：全部已入库的 notices 一次性询问（y 全删 / n 全不删）。"""
    from rag_manager import cleanup_notices
    store = RAGStore(str(tmp_path / "rag"))
    # 构造 2 个 notices 文件（内容已入库）
    notices_dir = tmp_path / "notices"
    notices_dir.mkdir()
    f1 = notices_dir / "notices_a.jsonl"
    f1.write_text('{"title":"通知1","content":"正文内容足够长","url":"https://x/1","publishTime":"2026-08-01"}\n', encoding="utf-8")
    f2 = notices_dir / "notices_b.jsonl"
    f2.write_text('{"title":"通知2","content":"另一段足够长的正文","url":"https://x/2","publishTime":"2026-08-01"}\n', encoding="utf-8")
    # 先把内容 ingest 进 RAG
    store.ingest([
        {"title": "通知1", "content": "正文内容足够长", "url": "https://x/1", "domain": "x", "date": "2026-08-01"},
        {"title": "通知2", "content": "另一段足够长的正文", "url": "https://x/2", "domain": "x", "date": "2026-08-01"},
    ])
    calls = []
    monkeypatch.setattr("builtins.input", lambda prompt="": (calls.append(prompt), "y")[1])
    deleted = cleanup_notices(store, notices_dir=str(notices_dir))
    assert deleted == 2, "应删除 2 个已收录文件"
    assert not f1.exists() and not f2.exists()
    assert len(calls) == 1, "应只询问一次"


def test_cleanup_notices_all_ingested_none(tmp_path, monkeypatch):
    """全部已入库但用户 n → 全不删，只询问一次。"""
    from rag_manager import cleanup_notices
    store = RAGStore(str(tmp_path / "rag"))
    notices_dir = tmp_path / "notices"
    notices_dir.mkdir()
    f1 = notices_dir / "notices_a.jsonl"
    f1.write_text('{"title":"通知1","content":"正文内容足够长","url":"https://x/1","publishTime":"2026-08-01"}\n', encoding="utf-8")
    store.ingest([{"title": "通知1", "content": "正文内容足够长", "url": "https://x/1", "domain": "x", "date": "2026-08-01"}])
    calls = []
    monkeypatch.setattr("builtins.input", lambda prompt="": (calls.append(prompt), "n")[1])
    deleted = cleanup_notices(store, notices_dir=str(notices_dir))
    assert deleted == 0
    assert f1.exists(), "n 应保留全部"
    assert len(calls) == 1, "应只询问一次"


def test_cleanup_notices_not_ingested_keeps(tmp_path, monkeypatch):
    """未入库的 notices 不删（询问时用户拒绝或内容未收录）。"""
    from rag_manager import cleanup_notices
    store = RAGStore(str(tmp_path / "rag"))
    notices_dir = tmp_path / "notices"
    notices_dir.mkdir()
    f = notices_dir / "notices_test2.jsonl"
    f.write_text('{"title":"未入库通知","content":"未收录的正文内容","url":"https://x/9","publishTime":"2026-08-01"}\n', encoding="utf-8")
    # 不 ingest → 用户拒绝删除
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    deleted = cleanup_notices(store, notices_dir=str(notices_dir))
    assert f.exists(), "未收录的 notices 不应删除"
    assert deleted == 0


def test_ingest_notices_tool(tmp_path, monkeypatch):
    """ingest_notices 工具：读 notices 产物入库。"""
    monkeypatch.chdir(Path(__file__).parent.parent)
    from src.tools.rag_manager_tools import make_rag_manager_tools, set_rag_store
    store = RAGStore(str(tmp_path / "rag"))
    set_rag_store(store)
    # 构造 notices 文件
    notices_dir = tmp_path / "notices"
    notices_dir.mkdir()
    (notices_dir / "notices_test.jsonl").write_text(
        '{"title":"通知A","content":"这是一段足够长的正文内容用于入库测试验证","url":"https://cs.nju.edu.cn/1","publishTime":"2026-08-01"}\n',
        encoding="utf-8")
    tools = make_rag_manager_tools()
    tool = [t for t in tools if t.name == "ingest_notices"][0]
    out = tool.handler(notices_dir=str(notices_dir))
    assert "新增 1" in out
    assert store._doc_count() == 1


def test_dedupe_docs_removes_duplicates(tmp_path, monkeypatch):
    """dedupe_docs：内容相同的重复文档只保留一条（优先含有效时间的）。"""
    monkeypatch.chdir(Path(__file__).parent.parent)
    from src.tools.rag_manager_tools import make_rag_manager_tools, set_rag_store
    store = RAGStore(str(tmp_path / "rag"))
    set_rag_store(store)
    # 直接写分片模拟旧重复数据（绕过 ingest 去重）：两条内容相同、URL 不同
    content = "这是一段足够长的完全相同正文内容用于去重测试"
    doc1 = {"id": "d.2026-08-01.1", "title": "通知A", "content": content, "url": "https://x/1",
            "domain": "d", "date": "2026-08-01", "dedup_hash": "x"}
    doc2 = {"id": "d.2026-08-01.2", "title": "通知B", "content": content, "url": "https://x/2",
            "domain": "d", "date": "2026-08-01", "dedup_hash": "y", "valid_until": "2026-12-31"}
    import json as _json
    slice_path = store._docs / "d.2026-08-01.jsonl"
    slice_path.write_text(_json.dumps(doc1, ensure_ascii=False) + "\n" + _json.dumps(doc2, ensure_ascii=False) + "\n", encoding="utf-8")
    assert store._doc_count() == 2
    tools = make_rag_manager_tools()
    tool = [t for t in tools if t.name == "dedupe_docs"][0]
    out = tool.handler()
    assert "删除 1" in out
    assert store._doc_count() == 1
    # 保留的是含有效时间的 doc2
    remain = store._load_all()
    assert remain[0]["id"] == "d.2026-08-01.2", "应保留含有效时间的文档"
