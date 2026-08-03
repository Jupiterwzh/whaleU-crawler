# tests/test_main.py
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

def test_main_explore_only(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(Path(__file__).parent.parent)
    with patch("src.agent_loop.AgentLoop.run", return_value="已生成策略"):
        sys.argv = ["main.py", "--explore-only", "https://cs.nju.edu.cn/"]
        import main
        main.main()
    out = capsys.readouterr().out
    assert "已生成策略" in out

def test_main_goal_arg(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(Path(__file__).parent.parent)
    with patch("src.agent_loop.AgentLoop.run", return_value="完成"):
        sys.argv = ["main.py", "探索 cs.nju.edu.cn"]
        import main
        main.main()
    out = capsys.readouterr().out
    assert "完成" in out
