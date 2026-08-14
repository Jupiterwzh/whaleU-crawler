# tests/test_llm_client.py
from unittest.mock import MagicMock, patch
from src.llm.client import LLMClient


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
        msg = {"role": "user", "content": "含\ud800\udfff代理对的内容"}
        result = client.chat([msg])
    assert result["text"] == "完成"
    # 传给 OpenAI 的消息应已清理 surrogate
    sent = captured["messages"][0]["content"]
    assert not any(0xD800 <= ord(c) <= 0xDFFF for c in sent)
