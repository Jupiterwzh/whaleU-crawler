# src/agent_loop.py
"""Agent 核心循环。LLM 只占一行决策，其余全是工程。"""
import json

from .llm.client import LLMClient


class AgentLoop:
    def __init__(self, harness, llm: LLMClient):
        self.H = harness
        self.llm = llm

    def run(self, goal: str) -> str:
        H = self.H
        # ① 上下文装配
        context = [
            {"role": "system", "content": H.system_prompt},
            {"role": "system", "content": H.rules},
            {"role": "user", "content": goal},
        ]
        max_steps = H.config["agent"].get("max_steps", 30)
        # ② 主循环
        for step in range(1, max_steps + 1):
            tools_schema = H.tools.to_openai_schemas() or None
            resp = self.llm.chat(context, tools=tools_schema)
            text = resp["text"]
            tool_calls = resp.get("tool_calls")
            H.tracer.record(step, text, {"tool_calls": tool_calls})

            if not tool_calls:
                # 无工具调用即停
                H.tracer.flush()
                return text

            # 一次性追加 assistant 消息（含 tool_calls 字段，符合 OpenAI 消息结构）
            context.append({
                "role": "assistant",
                "content": text,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                        },
                    }
                    for tc in tool_calls
                ],
            })
            # 处理每个 tool_call（每个都要有对应的 tool 结果消息）
            for tc in tool_calls:
                action = {"tool": tc["name"], "args": tc["arguments"]}
                # 门控（非交互环境防 EOFError）
                try:
                    ok, reason = H.guardrail.allow(action)
                except EOFError:
                    ok, reason = False, "非交互环境，默认拒绝"
                if not ok:
                    context.append({"role": "tool", "tool_call_id": tc["id"], "content": f"动作被拦截: {reason}"})
                    H.tracer.record(step, "", action, f"GUARDRAIL_DENY: {reason}")
                    continue
                # 执行
                try:
                    result = H.tools.call(tc["name"], tc["arguments"])
                except Exception as e:
                    result = f"工具失败: {e}"
                context.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                H.tracer.record(step, "", action, result)
        # ③ 收尾（步数上限）
        H.tracer.flush()
        return "任务未完成（达到步数上限）"
