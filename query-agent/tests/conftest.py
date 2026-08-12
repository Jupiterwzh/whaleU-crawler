"""pytest 共享 fixture。"""
import os
import sys
from pathlib import Path

import pytest

# 让 src 可导入（query-agent 自身包）
sys.path.insert(0, str(Path(__file__).parent.parent))
# 让 shared 可导入（RAGStore 公共位置，在项目根）
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """每个测试都注入假环境变量，绝不依赖真实 key。"""
    monkeypatch.setenv("LLM_BASE_URL", "https://fake.example.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "fake-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("STRATEGIES_DIR", "/tmp/test-strategies")
    monkeypatch.setenv("CRAWLER_SCRIPT", "/tmp/fake-collector.js")
    monkeypatch.setenv("NJU_BROWSER_DIR", "/tmp/fake-browser")
