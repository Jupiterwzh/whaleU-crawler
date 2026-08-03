# tests/test_llm_client.py
from unittest.mock import MagicMock, patch
from src.llm.client import LLMClient

def test_chat_returns_text_when_no_tool_calls():
    client = LLMClient()
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="完成", tool_calls=None))]
    with patch.object(client._client.chat.completions, "create", return_value=fake_resp):
        result = client.chat([{"role": "user", "content": "hi"}])
    assert result["text"] == "完成"
    assert result["tool_calls"] is None

def test_chat_parses_tool_calls():
    client = LLMClient()
    tc = MagicMock()
    tc.function.name = "fetch_url"
    tc.function.arguments = '{"url": "https://x"}'
    tc.id = "call_1"
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="", tool_calls=[tc]))]
    with patch.object(client._client.chat.completions, "create", return_value=fake_resp):
        result = client.chat([{"role": "user", "content": "go"}])
    assert result["tool_calls"] == [{"name": "fetch_url", "arguments": {"url": "https://x"}, "id": "call_1"}]
    assert result["text"] == ""

def test_chat_raises_on_missing_env(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY")
    import importlib
    import src.llm.client
    importlib.reload(src.llm.client)
    try:
        src.llm.client.LLMClient()
        assert False, "应抛错"
    except RuntimeError:
        pass
