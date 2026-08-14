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
    """收录完成：notices 全部已入库 → 询问后删除（y）。"""
    from rag_manager import cleanup_notices
    store = RAGStore(str(tmp_path / "rag"))
    # 构造 notices 文件（内容已入库）
    notices_dir = tmp_path / "notices"
    notices_dir.mkdir()
    f = notices_dir / "notices_test.jsonl"
    f.write_text('{"title":"通知1","content":"正文内容足够长","url":"https://x/1","publishTime":"2026-08-01"}\n', encoding="utf-8")
    # 先把内容 ingest 进 RAG（dedup 会存在）
    store.ingest([{"title":"通知1","content":"正文内容足够长","url":"https://x/1","domain":"x","date":"2026-08-01"}])
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    deleted = cleanup_notices(store, notices_dir=str(notices_dir))
    assert not f.exists(), "已收录的 notices 应被删除"
    assert deleted == 1


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
