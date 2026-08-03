"""OpenAI 兼容 LLM 客户端。绝不硬编码 key/端点。"""
import json
import os

from openai import OpenAI


class LLMClient:
    def __init__(self):
        base_url = os.environ.get("LLM_BASE_URL")
        api_key = os.environ.get("LLM_API_KEY")
        if not api_key:
            raise RuntimeError("LLM_API_KEY 环境变量未设置")
        self.model = os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-flash(free)")
        self._client = OpenAI(base_url=base_url, api_key=api_key)

    def chat(self, messages, tools=None):
        """返回 {"text": str, "tool_calls": list | None}。"""
        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        resp = self._client.chat.completions.create(**kwargs)
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
