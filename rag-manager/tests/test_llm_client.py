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
    import src.llm.client as client_mod
    with patch.object(client_mod, "get_key", return_value=""), \
         patch.object(client_mod, "ensure_key", side_effect=RuntimeError("LLM_API_KEY 环境变量未设置")):
        try:
            client_mod.LLMClient()
            assert False, "应抛错"
        except RuntimeError:
            pass


def test_chat_sanitizes_surrogate():
    """context 含非法 surrogate 时不崩溃（清理后调用）。"""
    client = LLMClient()
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="完成", tool_calls=None))]
    captured = {}
    def fake_create(**kwargs):
        captured["messages"] = kwargs.get("messages")
        return fake_resp
    with patch.object(client._client.chat.completions, "create", side_effect=fake_create):
        result = client.chat([{"role": "user", "content": "含\ud800\udfff代理对的内容"}])
    assert result["text"] == "完成"
    sent = captured["messages"][0]["content"]
    assert not any(0xD800 <= ord(c) <= 0xDFFF for c in sent)
