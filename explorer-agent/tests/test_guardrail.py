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


def test_write_inside_strategies_draft_allow():
    g = Guardrail.from_yaml("guardrails/policy.yaml", context=_ctx())
    ok, reason = g.allow({"tool": "write_file", "args": {"path": "/tmp/test-strategies/cs.nju.edu.cn.draft.json", "content": "{}"}})
    assert ok is True
    assert reason == ""


def test_write_file_formal_strategy_denied():
    """write_file 写正式策略 <domain>.json 应被拒绝（只能写 .draft.json 草稿）。"""
    g = Guardrail.from_yaml("guardrails/policy.yaml", context=_ctx())
    ok, reason = g.allow({"tool": "write_file", "args": {"path": "/tmp/test-strategies/cs.nju.edu.cn.json", "content": "{}"}})
    assert ok is False
    assert "草稿" in reason


def test_write_file_draft_allowed():
    """write_file 写草稿 <domain>.draft.json 放行。"""
    g = Guardrail.from_yaml("guardrails/policy.yaml", context=_ctx())
    ok, reason = g.allow({"tool": "write_file", "args": {"path": "/tmp/test-strategies/cs.nju.edu.cn.draft.json", "content": "{}"}})
    assert ok is True


def test_run_shell_cp_denied():
    """run_shell 的 cp（草稿转正等）应被拒绝。"""
    g = Guardrail.from_yaml("guardrails/policy.yaml", context=_ctx())
    ok, _ = g.allow({"tool": "run_shell", "args": {"cmd": "cp /tmp/test-strategies/cs.nju.edu.cn.draft.json /tmp/test-strategies/cs.nju.edu.cn.json"}})
    assert ok is False


def test_run_shell_verify_allowed():
    """run_shell 的 node collector.js --verify 应放行。"""
    g = Guardrail.from_yaml("guardrails/policy.yaml", context=_ctx())
    ok, _ = g.allow({"tool": "run_shell", "args": {"cmd": "node /tmp/collector.js --verify /tmp/test-strategies/cs.nju.edu.cn.draft.json"}})
    assert ok is True
