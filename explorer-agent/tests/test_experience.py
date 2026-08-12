"""经验库读写测试。"""
import json
import sys
from pathlib import Path
from unittest.mock import patch
from src.experience import load_experiences, save_experiences, to_context, default_experiences


def test_default_structure(tmp_path):
    data = default_experiences()
    assert "cmsPatterns" in data
    assert "pitfalls" in data
    assert "deptTypes" in data


def test_save_and_load(tmp_path):
    path = tmp_path / "experiences.json"
    data = default_experiences()
    data["pitfalls"].append({"desc": "测试踩坑", "action": "测试动作"})
    assert save_experiences(data, str(path)) is True
    loaded = load_experiences(str(path))
    assert loaded["pitfalls"][0]["desc"] == "测试踩坑"


def test_load_missing_returns_default(tmp_path):
    data = load_experiences(str(tmp_path / "nope.json"))
    assert "cmsPatterns" in data


def test_to_context_contains_patterns(tmp_path):
    path = tmp_path / "experiences.json"
    data = default_experiences()
    data["cmsPatterns"].append({"cms": "苏迪CMS", "signature": "news_title+news_meta"})
    save_experiences(data, str(path))
    ctx = to_context(load_experiences(str(path)))
    assert "苏迪CMS" in ctx
    assert "news_title" in ctx


def test_main_injects_experience_context(tmp_path, monkeypatch, capsys):
    """main.py 探索时注入经验库文本到 goal。"""
    monkeypatch.chdir(Path(__file__).parent.parent)
    import main
    with patch.object(main, "preflight", return_value=type("R", (), {
        "should_exit": False, "crash_mode": False, "goal_context": ""})()), \
         patch.object(main, "postflight"), \
         patch.object(main, "LLMClient"), \
         patch.object(main, "AgentLoop", autospec=True) as mock_loop:
        fake = mock_loop.return_value
        fake.run.return_value = "ok"
        sys.argv = ["main.py", "探索 https://yzb.nju.edu.cn/ 的通知公告入口"]
        main.main()
    goal = fake.run.call_args[0][0]
    assert "苏迪CMS" in goal or "通用规律" in goal
