# tests/test_query_harness.py
from pathlib import Path
from unittest.mock import MagicMock
from shared.rag.ragstore import RAGStore
from src.harness import Harness


def test_query_agent_has_correct_tools(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).parent.parent)
    store = RAGStore(str(tmp_path))
    h = Harness.from_yaml("agent.yaml", rag_store=store)
    names = h.tools.names()
    # query-agent 只用 rag + read_file，无 fetch_url/write_file/run_shell
    assert "rag_search" in names
    assert "run_crawler" in names
    assert "read_file" in names
    assert "fetch_url" not in names
    assert "write_file" not in names
    assert "run_shell" not in names


def test_classify_user_input():
    """L6: 交互输入分类——继续/退出/新站点/反馈。"""
    from src.agent_loop import _classify_input
    assert _classify_input("y") == ("continue", "")
    assert _classify_input("Y") == ("continue", "")
    assert _classify_input("exit") == ("exit", "")
    assert _classify_input("q") == ("exit", "")
    assert _classify_input("http://foo.nju.edu.cn") == ("new_site", "http://foo.nju.edu.cn")
    assert _classify_input("https://bar.nju.edu.cn/") == ("new_site", "https://bar.nju.edu.cn/")
    assert _classify_input("不对，应该是软件学院") == ("feedback", "不对，应该是软件学院")
    assert _classify_input("列出对应") == ("feedback", "列出对应")


def test_dispatch_interaction_new_site_injects_feedback(tmp_path, monkeypatch):
    """L7: 关键工具后交互——用户给新站点，反馈注入下一轮，然后完成。"""
    import os, json
    from unittest.mock import MagicMock
    monkeypatch.chdir(Path(__file__).parent.parent)
    from src.agent_loop import AgentLoop
    from src.harness import Harness
    from src.tools import rag_tools

    store = RAGStore(str(tmp_path))
    h = Harness.from_yaml("agent.yaml", rag_store=store)

    # sites.json 指向临时（含 1 站）
    sites_file = tmp_path / "sites.json"
    sites_file.write_text(json.dumps([{"name": "计算机学院", "domain": "cs.nju.edu.cn"}]), encoding="utf-8")
    monkeypatch.setattr(rag_tools, "_SITES_JSON", sites_file)

    # 交互输入序列：第一次给新站点，第二次 y
    inputs = iter(["http://software.nju.edu.cn", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    llm = MagicMock()
    llm.chat.side_effect = [
        {"text": "先看候选", "tool_calls": [{"name": "list_sites", "arguments": {}, "id": "1"}]},
        {"text": "完成", "tool_calls": None},
    ]
    loop = AgentLoop(h, llm)
    result = loop.run("软件学院的通知")
    assert result == "完成"
    # 第二轮应包含用户反馈（新站点）
    user_msgs = [c["content"] for c in llm.chat.call_args_list[1][0][0] if c["role"] == "user"]
    assert any("software.nju.edu.cn" in m for m in user_msgs)


def test_finalize_appends_full_list(tmp_path, monkeypatch):
    """Agent 精简列表时，最终答案补全完整通知列表。"""
    from src.agent_loop import AgentLoop
    loop = AgentLoop(MagicMock(), MagicMock())
    loop._list_all_result = (
        "cs.nju.edu.cn 共收录 3 条有效通知：\n"
        "1. [2026-08-01] 通知一 (https://cs.nju.edu.cn/1) [有效 60 天]\n"
        "2. [2026-08-02] 通知二 (https://cs.nju.edu.cn/2) [有效 60 天]\n"
        "3. [2026-08-03] 通知三 (https://cs.nju.edu.cn/3) [有效 60 天]\n"
    )
    # Agent 只展示了 1 条
    short = "已检索到 cs.nju.edu.cn 的通知。\n1. 通知一 https://cs.nju.edu.cn/1"
    result = loop._finalize(short)
    assert "完整通知列表" in result
    assert "通知二" in result and "通知三" in result


def test_finalize_keeps_full_agent_output(tmp_path):
    """Agent 已完整展示时，不重复追加。"""
    from src.agent_loop import AgentLoop
    loop = AgentLoop(MagicMock(), MagicMock())
    loop._list_all_result = (
        "cs.nju.edu.cn 共收录 2 条有效通知：\n"
        "1. [2026-08-01] 通知一 (https://cs.nju.edu.cn/1) [有效 60 天]\n"
        "2. [2026-08-02] 通知二 (https://cs.nju.edu.cn/2) [有效 60 天]\n"
    )
    full = "cs.nju.edu.cn 共收录 2 条有效通知：\n1. [2026-08-01] 通知一 (https://cs.nju.edu.cn/1) [有效 60 天]\n2. [2026-08-02] 通知二 (https://cs.nju.edu.cn/2) [有效 60 天]"
    result = loop._finalize(full)
    assert "完整通知列表" not in result
