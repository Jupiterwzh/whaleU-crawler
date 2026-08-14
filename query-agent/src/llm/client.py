"""OpenAI 兼容 LLM 客户端。绝不硬编码 key/端点。"""
import json
import os
import re
import time

from openai import OpenAI, RateLimitError, APIConnectionError

from src.keys import get_key, ensure_key

_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")


def _sanitize_text(text: str) -> str:
    """清理非法 surrogate（防止 json 序列化崩溃）。"""
    if not text:
        return text
    return _SURROGATE_RE.sub("\ufffd", text)


def _sanitize_messages(messages: list) -> list:
    """递归清理消息中的 surrogate。"""
    out = []
    for m in messages:
        if not isinstance(m, dict):
            out.append(m)
            continue
        d = dict(m)
        for k, v in list(d.items()):
            if isinstance(v, str):
                d[k] = _sanitize_text(v)
        out.append(d)
    return out


class LLMClient:
    def __init__(self):
        base_url = os.environ.get("LLM_BASE_URL")
        api_key = os.environ.get("LLM_API_KEY") or get_key()
        if not api_key:
            api_key = ensure_key()  # 首启引导录入
        self.model = os.environ.get("LLM_MODEL", "")
        if not self.model:
            raise ValueError("未配置 LLM_MODEL（请在 .env 设置，如 deepseek-v4-flash）")
        self._client = OpenAI(base_url=base_url, api_key=api_key)

    def chat(self, messages, tools=None):
        messages = _sanitize_messages(messages)
        kwargs = {"model": self.model, "messages": messages, "max_tokens": 4096, "temperature": 0.3}
        if tools:
            kwargs["tools"] = tools

        max_retries = 5
        for attempt in range(max_retries):
            try:
                resp = self._client.chat.completions.create(**kwargs)
                break
            except (RateLimitError, APIConnectionError) as e:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** attempt
                print(f"  ⚠️ {type(e).__name__}，{wait}s 后重试 ({attempt + 1}/{max_retries})")
                time.sleep(wait)

        msg = resp.choices[0].message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                {
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                    "id": tc.id,
                }
                for tc in msg.tool_calls
            ]
        return {"text": msg.content or "", "tool_calls": tool_calls}
