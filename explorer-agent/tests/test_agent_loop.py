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


def test_extract_list_candidates_from_structure_result():
    """从 crawl_structure 返回提取全部 list 候选（供确认界面展示完整清单）。"""
    from src.agent_loop import _extract_list_candidates
    import json
    tree = {
        "domain": "cs.nju.edu.cn",
        "nodes": [
            {"index": 1, "url": "https://cs.nju.edu.cn/", "type": "home", "title": "首页"},
            {"index": 2, "url": "https://cs.nju.edu.cn/1650/list.htm", "type": "list", "title": "学院简介"},
            {"index": 3, "url": "https://cs.nju.edu.cn/1702/list.htm", "type": "list", "title": "院内公告"},
            {"index": 4, "url": "https://cs.nju.edu.cn/intro.htm", "type": "info", "title": "概览"},
            {"index": 5, "url": "https://cs.nju.edu.cn/1703/list.htm", "type": "list", "title": "研究生公告栏"},
        ],
    }
    cands = _extract_list_candidates(json.dumps(tree))
    # 只取 list 类型，保留 index/url/title
    assert len(cands) == 3
    assert cands[0]["url"] == "https://cs.nju.edu.cn/1650/list.htm"
    assert all(c["type"] == "list" for c in cands)


def test_extract_list_candidates_non_json():
    """非 crawl_structure 结果返回空列表。"""
    from src.agent_loop import _extract_list_candidates
    assert _extract_list_candidates("普通文本结果") == []
    assert _extract_list_candidates("") == []


def test_format_list_candidates():
    """完整 list 候选清单格式化（像最初弹窗那样）。"""
    from src.agent_loop import _format_list_candidates
    cands = [
        {"index": 2, "url": "https://cs.nju.edu.cn/1650/list.htm", "title": "学院简介"},
        {"index": 3, "url": "https://cs.nju.edu.cn/1702/list.htm", "title": "院内公告"},
    ]
    out = _format_list_candidates(cands)
    assert "[ 2]" in out and "学院简介" in out and "1650/list.htm" in out
    assert "[ 3]" in out and "院内公告" in out


def test_format_list_candidates_empty():
    from src.agent_loop import _format_list_candidates
    assert _format_list_candidates([]) == ""


def test_confirm_preview_includes_all_candidates(tmp_path, monkeypatch):
    """确认预览包含完整 list 候选清单（不止 Agent 选中的）。"""
    import os, json
    monkeypatch.chdir(Path(__file__).parent.parent)
    from src.agent_loop import AgentLoop
    from src.harness import Harness
    h = Harness.from_yaml("agent.yaml")
    llm = MagicMock()
    # 第一轮：调 crawl_structure（返回 3 个 list 候选）；第二轮：完成
    llm.chat.side_effect = [
        {"text": "先遍历", "tool_calls": [{"name": "crawl_structure", "arguments": {"url": "https://x/"}, "id": "1"}]},
        {"text": "完成\n\n## 1. 网站结构树\n\n```\n树\n```", "tool_calls": None},
    ]
    tree_json = json.dumps({
        "domain": "x", "nodes": [
            {"index": 1, "url": "https://x/", "type": "home", "title": "首页"},
            {"index": 2, "url": "https://x/1702/list.htm", "type": "list", "title": "院内公告"},
            {"index": 3, "url": "https://x/1650/list.htm", "type": "list", "title": "学院简介"},
            {"index": 4, "url": "https://x/1703/list.htm", "type": "list", "title": "研究生公告栏"},
        ]})
    h.tools.get("crawl_structure").handler = MagicMock(return_value=tree_json)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    loop = AgentLoop(h, llm)
    loop.run("探索")
    preview = loop._confirm_preview("完成\n\n## 1. 网站结构树\n\n```\n树\n```")
    assert "1702/list.htm" in preview
    assert "1650/list.htm" in preview
    assert "1703/list.htm" in preview


def test_build_marked_tree():
    """程序生成带标记的完整结构树：所有节点 + ✅选中/⚠️未选/❌功能页/详情/外链 标记。"""
    from src.agent_loop import _build_marked_tree
    nodes = [
        {"index": 1, "url": "https://cs.nju.edu.cn/", "title": "首页", "type": "home", "depth": 0},
        {"index": 2, "url": "https://cs.nju.edu.cn/1650/list.htm", "title": "学院简介", "type": "list", "depth": 1},
        {"index": 3, "url": "https://cs.nju.edu.cn/1702/list.htm", "title": "院内公告", "type": "list", "depth": 1},
        {"index": 4, "url": "https://cs.nju.edu.cn/intro.htm", "title": "概览", "type": "info", "depth": 1},
        {"index": 5, "url": "https://cs.nju.edu.cn/1702a/page.htm", "title": "具体通知", "type": "detail", "depth": 2},
    ]
    selected = {"https://cs.nju.edu.cn/1702/list.htm"}  # 院内公告被选中
    tree = _build_marked_tree(nodes, selected)
    # 所有节点都在（全站点合并）
    assert "学院简介" in tree and "院内公告" in tree and "具体通知" in tree and "概览" in tree
    # 标记正确
    assert "✅选中" in tree and "1702/list.htm" in tree.split("✅选中")[1]
    assert "⚠️未选" in tree and "1650/list.htm" in tree.split("⚠️未选")[1]
    assert "❌info" in tree or "❌信息" in tree
    assert "❌详情" in tree


def test_build_marked_tree_shows_user_added_urls():
    """用户指定的入口（不在 crawl_structure 节点里）标记为 ⚠️不在结构树，提示直接改 JSON。"""
    from src.agent_loop import _build_marked_tree
    nodes = [
        {"index": 1, "url": "https://cs.nju.edu.cn/", "title": "首页", "type": "home", "depth": 0},
        {"index": 2, "url": "https://cs.nju.edu.cn/1702/list.htm", "title": "院内公告", "type": "list", "depth": 1},
    ]
    selected = {"https://cs.nju.edu.cn/1702/list.htm", "https://cs.nju.edu.cn/9999/list.htm"}
    tree = _build_marked_tree(nodes, selected)
    assert "9999/list.htm" in tree
    assert "⚠️不在结构树" in tree
    assert "直接修改策略 JSON" in tree


def test_confirm_preview_warns_truncated():
    """crawl_structure 返回 truncated 时，确认预览提示遍历可能不完整。"""
    from src.agent_loop import AgentLoop, _build_marked_tree
    from unittest.mock import MagicMock
    loop = AgentLoop(MagicMock(), MagicMock())
    loop._structure_nodes = [
        {"index": 1, "url": "https://cs.nju.edu.cn/", "title": "首页", "type": "home", "depth": 0},
    ]
    loop._structure_truncated = True
    preview = loop._confirm_preview("")
    assert "⚠️" in preview and "遍历可能不完整" in preview
