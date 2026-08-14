"""OpenAI 兼容 LLM 客户端。绝不硬编码 key/端点。"""
import json
import os
import time

from openai import OpenAI, RateLimitError, APIConnectionError

from src.keys import get_key, ensure_key


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
