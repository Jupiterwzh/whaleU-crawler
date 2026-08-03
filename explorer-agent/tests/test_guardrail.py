import os

from src.guardrail import Guardrail


def _ctx():
    return {
        "strategies_dir": os.environ.get("STRATEGIES_DIR", "/tmp/test-strategies"),
        "project_root": os.getcwd(),
    }


def test_deny_rm_rf():
    g = Guardrail.from_yaml("guardrails/policy.yaml", context=_ctx())
    ok, reason = g.allow({"tool": "run_shell", "args": {"cmd": "rm -rf /"}})
    assert ok is False
    assert "递归删除" in reason


def test_allow_fetch_url():
    g = Guardrail.from_yaml("guardrails/policy.yaml", context=_ctx())
    ok, _ = g.allow({"tool": "fetch_url", "args": {"url": "https://x"}})
    assert ok is True


def test_ask_user_write_file(monkeypatch):
    g = Guardrail.from_yaml("guardrails/policy.yaml", context=_ctx())
    monkeypatch.setattr("builtins.input", lambda _: "y")
    ok, reason = g.allow({"tool": "write_file", "args": {"path": "/tmp/x", "content": "{}"}})
    assert ok is True
    assert "确认" in reason


def test_write_inside_strategies_allow():
    g = Guardrail.from_yaml("guardrails/policy.yaml", context=_ctx())
    ok, reason = g.allow({"tool": "write_file", "args": {"path": "/tmp/test-strategies/cs.nju.edu.cn.json", "content": "{}"}})
    assert ok is True
    assert reason == ""
