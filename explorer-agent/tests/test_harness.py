# tests/test_harness.py
import os
from src.harness import Harness

def test_from_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(os.path.dirname(__file__) + "/..")
    h = Harness.from_yaml("agent.yaml")
    assert "explorer-agent" in h.system_prompt or "探索" in h.rules
    assert "fetch_url" in h.tools.names()
    assert "write_file" in h.tools.names()
    assert "run_shell" in h.tools.names()
    assert h.guardrail is not None
    assert h.tracer is not None
    assert h.config["agent"]["name"] == "explorer-agent"
