# tests/test_agent_loop.py
from unittest.mock import MagicMock
from src.agent_loop import AgentLoop

def _make_harness(tmp_path):
    from src.harness import Harness
    return Harness.from_yaml("agent.yaml")

def test_loop_done_immediately(tmp_path, monkeypatch):
    import os
    monkeypatch.chdir(os.path.dirname(__file__) + "/..")
    h = _make_harness(tmp_path)
    llm = MagicMock()
    # 第一次：无 tool_calls → done
    llm.chat.return_value = {"text": "已完成", "tool_calls": None}
    loop = AgentLoop(h, llm)
    result = loop.run("测试任务")
    assert result == "已完成"

def test_loop_calls_tool_then_done(tmp_path, monkeypatch):
    import os
    monkeypatch.chdir(os.path.dirname(__file__) + "/..")
    h = _make_harness(tmp_path)
    llm = MagicMock()
    llm.chat.side_effect = [
        {"text": "抓页面", "tool_calls": [{"name": "fetch_url", "arguments": {"url": "https://x"}, "id": "1"}]},
        {"text": "完成", "tool_calls": None},
    ]
    # mock fetch_url 工具
    h.tools.get("fetch_url").handler = MagicMock(return_value="<html>")
    loop = AgentLoop(h, llm)
    result = loop.run("抓 https://x")
    assert result == "完成"
    assert llm.chat.call_count == 2

def test_loop_assistant_msg_has_tool_calls(tmp_path, monkeypatch):
    import os
    monkeypatch.chdir(os.path.dirname(__file__) + "/..")
    from src.harness import Harness
    h = Harness.from_yaml("agent.yaml")
    llm = MagicMock()
    llm.chat.side_effect = [
        {"text": "抓", "tool_calls": [{"name": "fetch_url", "arguments": {"url": "https://x"}, "id": "1"}]},
        {"text": "完成", "tool_calls": None},
    ]
    h.tools.get("fetch_url").handler = MagicMock(return_value="<html>")
    loop = AgentLoop(h, llm)
    loop.run("抓")
    # 检查第二次 chat 调用时 context 里有带 tool_calls 的 assistant 消息
    second_call_args = llm.chat.call_args_list[1]
    context = second_call_args.args[0]
    asst_msgs = [m for m in context if m.get("role") == "assistant"]
    assert any("tool_calls" in m for m in asst_msgs), "assistant 消息应含 tool_calls 字段"
