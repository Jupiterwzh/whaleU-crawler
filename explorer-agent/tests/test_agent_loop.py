# tests/test_agent_loop.py
from pathlib import Path
from unittest.mock import MagicMock
from src.agent_loop import AgentLoop

def _make_harness(tmp_path):
    from src.harness import Harness
    return Harness.from_yaml("agent.yaml")

def test_loop_done_immediately(tmp_path, monkeypatch):
    import os
    monkeypatch.chdir(os.path.dirname(__file__) + "/..")
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    h = _make_harness(tmp_path)
    llm = MagicMock()
    llm.chat.return_value = {"text": "已完成", "tool_calls": None}
    loop = AgentLoop(h, llm)
    result = loop.run("测试任务")
    assert result == "已完成"

def test_loop_calls_tool_then_done(tmp_path, monkeypatch):
    import os
    monkeypatch.chdir(os.path.dirname(__file__) + "/..")
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    h = _make_harness(tmp_path)
    llm = MagicMock()
    llm.chat.side_effect = [
        {"text": "抓页面", "tool_calls": [{"name": "fetch_url", "arguments": {"url": "https://x"}, "id": "1"}]},
        {"text": "完成", "tool_calls": None},
    ]
    h.tools.get("fetch_url").handler = MagicMock(return_value="<html>")
    loop = AgentLoop(h, llm)
    result = loop.run("抓 https://x")
    assert result == "完成"
    assert llm.chat.call_count == 2

def test_loop_assistant_msg_has_tool_calls(tmp_path, monkeypatch):
    import os
    monkeypatch.chdir(os.path.dirname(__file__) + "/..")
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
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
    second_call_args = llm.chat.call_args_list[1]
    context = second_call_args.args[0]
    asst_msgs = [m for m in context if m.get("role") == "assistant"]
    assert any("tool_calls" in m for m in asst_msgs), "assistant 消息应含 tool_calls 字段"


def test_loop_asks_experience_confirm(tmp_path, monkeypatch):
    """探索确认后，展示经验草案并人工确认（y 保存经验到 tmp_path，不污染真实库）。"""
    monkeypatch.chdir(Path(__file__).parent.parent)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    from src.agent_loop import AgentLoop
    from src.experience import save_experiences, default_experiences
    exp_path = tmp_path / "experiences.json"
    save_experiences(default_experiences(), str(exp_path))
    h = _make_harness(tmp_path)
    llm = MagicMock()
    llm.chat.return_value = {"text": "完成", "tool_calls": None}
    loop = AgentLoop(h, llm, experience_path=str(exp_path))
    loop.run("测试")
    # 经验确认交互不崩溃，且 tmp 库仍存在
    assert exp_path.exists()

def test_preview_keeps_structure_tree():
    """确认预览应完整保留结构树（前 4000 字符），超长才标注截断。"""
    from src.agent_loop import _preview
    # 正常长度（结构树 ~1000 字符）→ 不截断
    tree = "├── [✅列表页·选中] 院内公告 (/1702/list.htm, 84条/6页)\n" * 30
    assert _preview(tree) == tree
    # 超长 → 保留前 4000 并标注
    long = "x" * 6000
    p = _preview(long)
    assert "x" * 4000 in p
    assert "截断" in p


def test_preview_keeps_only_structure_tree():
    """确认预览应只展示结构树（第一个围栏块），跳过策略 JSON。"""
    from src.agent_loop import _preview
    text = """验证通过。

## 1. 网站结构树

```
cs.nju.edu.cn
├── [✅列表页·选中] 院内公告 (/1702/list.htm)
└── [❌功能页] 学院简介
```

## 2. 策略 JSON

```json
{"meta": {"domain": "cs.nju.edu.cn"}}
```"""
    p = _preview(text)
    assert "cs.nju.edu.cn" in p          # 结构树保留
    assert "院内公告" in p
    assert '"meta"' not in p              # 策略 JSON 内容不展示
    assert "## 2. 策略 JSON" not in p      # JSON 标题段不展示
    assert "（策略 JSON 已保存，确认时不再展示）" in p  # 提示


def test_preview_fallback_when_no_fence():
    """无围栏代码块时回退到长度截断。"""
    from src.agent_loop import _preview
    long = "x" * 6000
    p = _preview(long)
    assert len(p) <= 4100
    assert "截断" in p
