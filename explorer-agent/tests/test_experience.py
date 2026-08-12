"""经验库读写测试。"""
import json
from pathlib import Path
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
