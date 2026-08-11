# tests/test_main.py
import sys
from unittest.mock import patch
from pathlib import Path


def test_main_goal_arg(tmp_path, monkeypatch, capsys):
    """模式 B：preflight 通过 → Agent 跑 → postflight 被调用。"""
    monkeypatch.chdir(Path(__file__).parent.parent)
    import main
    with patch.object(main, "preflight", return_value=type("R", (), {
        "should_exit": False, "crash_mode": False, "goal_context": ""})()), \
         patch.object(main, "postflight") as mock_post, \
         patch.object(main, "LLMClient"), \
         patch.object(main, "AgentLoop", autospec=True):
        fake_loop = main.AgentLoop.return_value
        fake_loop.run.return_value = "完成"
        sys.argv = ["main.py", "探索 cs.nju.edu.cn"]
        main.main()
    mock_post.assert_called_once()
    fake_loop.run.assert_called_once()


def test_main_explore_only(tmp_path, monkeypatch, capsys):
    """模式 A：--explore-only 走 preflight → Agent → postflight。"""
    monkeypatch.chdir(Path(__file__).parent.parent)
    import main
    with patch.object(main, "preflight", return_value=type("R", (), {
        "should_exit": False, "crash_mode": False, "goal_context": ""})()), \
         patch.object(main, "postflight") as mock_post, \
         patch.object(main, "LLMClient"), \
         patch.object(main, "AgentLoop", autospec=True):
        fake_loop = main.AgentLoop.return_value
        fake_loop.run.return_value = "已生成策略"
        sys.argv = ["main.py", "--explore-only", "https://cs.nju.edu.cn/"]
        main.main()
    mock_post.assert_called_once()
    fake_loop.run.assert_called_once()


def test_main_preflight_exit(tmp_path, monkeypatch, capsys):
    """用户在前导选择不爬取 → should_exit → 不启动 Agent。"""
    monkeypatch.chdir(Path(__file__).parent.parent)
    import main
    with patch.object(main, "preflight", return_value=type("R", (), {
        "should_exit": True, "crash_mode": False, "goal_context": ""})()), \
         patch.object(main, "postflight") as mock_post, \
         patch.object(main, "AgentLoop") as mock_loop:
        sys.argv = ["main.py", "探索 cs.nju.edu.cn"]
        main.main()
    mock_post.assert_not_called()
    mock_loop.assert_not_called()
