import json
from unittest.mock import MagicMock

from shared.rag.ragstore import RAGStore
from src.tools.rag_tools import make_rag_tools


def test_rag_search_formats_results(tmp_path):
    store = RAGStore(str(tmp_path))
    store.ingest([{"title": "考试通知", "content": "期末安排", "url": "https://cs.nju.edu.cn/u1", "domain": "cs.nju.edu.cn", "date": "2026-03-01"}])
    store.refresh()
    tools = make_rag_tools(store, "node")
    tool = [t for t in tools if t.name == "rag_search"][0]
    out = tool.handler(query="考试")
    assert "考试通知" in out and "cs.nju.edu.cn" in out


def test_rag_search_no_match(tmp_path):
    store = RAGStore(str(tmp_path))
    store.refresh()
    tools = make_rag_tools(store, "node")
    tool = [t for t in tools if t.name == "rag_search"][0]
    assert "无匹配" in tool.handler(query="xyz")


def test_run_crawler_invokes_and_ingests(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from src.tools.rag_tools import make_rag_tools
    store = MagicMock()
    store.ingest.return_value = 1
    tools = make_rag_tools(store, "node")
    tool = [t for t in tools if t.name == "run_crawler"][0]
    monkeypatch.setattr("src.tools.rag_tools.subprocess.run", lambda *a, **kw: MagicMock(stdout="", returncode=0))
    out = tool.handler(url="https://cs.nju.edu.cn/")
    assert "cs.nju.edu.cn" in out


def test_run_crawler_triggers_rag_manager(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, patch
    from shared.rag.ragstore import RAGStore
    from src.tools.rag_tools import make_rag_tools
    store = RAGStore(str(tmp_path))
    tools = make_rag_tools(store, "node")
    tool = [t for t in tools if t.name == "run_crawler"][0]
    with patch("subprocess.run", return_value=MagicMock(stdout="保存到: /tmp/out.jsonl", returncode=0, stderr="")), \
         patch("src.tools.rag_tools.Path.is_file", return_value=True), \
         patch("src.tools.rag_tools.Path.read_text", return_value='{"title":"t","url":"u","publishTime":"2026-03-01"}\n'), \
         patch.object(store, "refresh"), \
         patch("src.tools.rag_tools._trigger_rag_manager") as mock_trigger:
        tool.handler(url="https://cs.nju.edu.cn/")
    mock_trigger.assert_called_once()


def test_run_crawler_archives_output(tmp_path, monkeypatch):
    """L2: run_crawler 入库后把爬虫输出归档到 data/archive/。"""
    from unittest.mock import MagicMock, patch
    from shared.rag.ragstore import RAGStore
    from src.tools.rag_tools import make_rag_tools

    store = RAGStore(str(tmp_path))
    tools = make_rag_tools(store, "node")

    fake_out = tmp_path / "notices_123.jsonl"
    fake_out.write_text('{"title":"t","url":"u","publishTime":"2026-03-01"}\n')

    arch_dir = tmp_path / "archive"
    with patch("subprocess.run", return_value=MagicMock(
            stdout=f"保存到: {fake_out}", returncode=0, stderr="")), \
         patch("src.tools.rag_tools._trigger_rag_manager"):
        tool = [t for t in tools if t.name == "run_crawler"][0]
        tool.handler(url="https://cs.nju.edu.cn/")
    # 归档目录应存在且包含移动后的文件
    assert arch_dir.exists()
    assert list(arch_dir.glob("notices_*.jsonl"))
    assert not fake_out.exists()


def test_check_strategy_finds_and_misses(tmp_path, monkeypatch):
    """L3: check_strategy 返回策略是否存在及路径。"""
    from src.tools.rag_tools import make_rag_tools
    strat_dir = tmp_path / "strategies"
    strat_dir.mkdir()
    (strat_dir / "cs.nju.edu.cn.json").write_text('{"meta":{}}', encoding="utf-8")
    store = MagicMock()
    tools = make_rag_tools(store, "node", strategies_dir=str(strat_dir))
    tool = [t for t in tools if t.name == "check_strategy"][0]
    out_hit = tool.handler(domain="cs.nju.edu.cn")
    assert "存在" in out_hit and "cs.nju.edu.cn.json" in out_hit
    out_miss = tool.handler(domain="software.nju.edu.cn")
    assert "不存在" in out_miss


def test_run_explorer_spawns_and_reports(tmp_path, monkeypatch):
    """L3: run_explorer 唤起 explorer-agent（spawn main.py --explore-only）。"""
    from src.tools.rag_tools import make_rag_tools
    store = MagicMock()
    tools = make_rag_tools(store, "node", strategies_dir=str(tmp_path))
    tool = [t for t in tools if t.name == "run_explorer"][0]
    captured = {}
    def fake_spawn(*a, **kw):
        captured["cmd"] = a
        captured["env"] = kw.get("env", {})
        return MagicMock(stdout="== 策略生成完成 ==\n保存到: x.json", stderr="", returncode=0)
    monkeypatch.setattr("src.tools.rag_tools.subprocess.run", fake_spawn)
    out = tool.handler(url="https://software.nju.edu.cn/")
    assert "software.nju.edu.cn" in out
    assert "策略" in out
    assert "--explore-only" in " ".join(captured["cmd"][0])


def test_list_sites_builds_candidates(tmp_path, monkeypatch):
    """L4: list_sites 从策略目录 meta 构建站点候选清单（siteName + domain）。"""
    from src.tools.rag_tools import make_rag_tools
    strat_dir = tmp_path / "strategies"
    strat_dir.mkdir()
    (strat_dir / "cs.nju.edu.cn.json").write_text(
        json.dumps({"meta": {"domain": "cs.nju.edu.cn", "siteName": "计算机学院"}}), encoding="utf-8")
    (strat_dir / "software.nju.edu.cn.json").write_text(
        json.dumps({"meta": {"domain": "software.nju.edu.cn", "siteName": "软件学院"}}), encoding="utf-8")
    store = MagicMock()
    tools = make_rag_tools(store, "node", strategies_dir=str(strat_dir))
    tool = [t for t in tools if t.name == "list_sites"][0]
    out = tool.handler()
    assert "cs.nju.edu.cn" in out and "计算机学院" in out
    assert "software.nju.edu.cn" in out and "软件学院" in out


def test_list_sites_prefers_sites_json(tmp_path, monkeypatch):
    """L5: 有 sites.json 时 list_sites 返回其站点（含名称+域名）；无则 fallback 策略 meta。"""
    import src.tools.rag_tools as rt
    from src.tools.rag_tools import make_rag_tools

    sites_file = tmp_path / "sites.json"
    sites_file.write_text(json.dumps([
        {"name": "软件学院", "domain": "software.nju.edu.cn", "category": "院系", "source": "官方"},
        {"name": "智能软件与工程学院", "domain": "ise.nju.edu.cn", "category": "院系", "source": "官方"},
    ]), encoding="utf-8")

    # sites.json 存在 → 返回 sites.json 内容
    monkeypatch.setattr(rt, "_SITES_JSON", sites_file)
    store = MagicMock()
    tools = make_rag_tools(store, "node", strategies_dir=str(tmp_path))
    tool = [t for t in tools if t.name == "list_sites"][0]
    out = tool.handler()
    assert "软件学院" in out and "software.nju.edu.cn" in out
    assert "智能软件与工程学院" in out and "ise.nju.edu.cn" in out

    # sites.json 不存在 → fallback 策略 meta
    monkeypatch.setattr(rt, "_SITES_JSON", tmp_path / "nope.json")
    (tmp_path / "cs.nju.edu.cn.json").write_text(
        json.dumps({"meta": {"domain": "cs.nju.edu.cn", "siteName": "计算机学院"}}), encoding="utf-8")
    out2 = tool.handler()
    assert "cs.nju.edu.cn" in out2 and "计算机学院" in out2


def test_rag_search_domain_filter(tmp_path):
    """rag_search 支持 domain 过滤。"""
    from src.tools.rag_tools import make_rag_tools
    store = RAGStore(str(tmp_path))
    store.ingest([
        {"title": "cs 通知", "content": "计算机学院通知正文足够长", "url": "https://cs.nju.edu.cn/1", "domain": "cs.nju.edu.cn", "date": "2026-08-01"},
        {"title": "yzb 通知", "content": "研究生招生通知正文足够长", "url": "https://yzb.nju.edu.cn/1", "domain": "yzb.nju.edu.cn", "date": "2026-08-01"},
    ])
    store.refresh()
    tools = make_rag_tools(store, "node")
    tool = [t for t in tools if t.name == "rag_search"][0]
    out = tool.handler(query="通知", top_k=10, domain="cs.nju.edu.cn")
    assert "cs.nju.edu.cn" in out
    assert "yzb.nju.edu.cn" not in out
