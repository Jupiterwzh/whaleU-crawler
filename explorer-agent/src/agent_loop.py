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
        context = [
            {"role": "system", "content": H.system_prompt},
            {"role": "system", "content": H.rules},
            {"role": "user", "content": goal},
        ]
        max_steps = H.config["agent"].get("max_steps", 30)
        max_adjustments = 3
        tracer_step = 0
        round_idx = 0

        print(f"目标: {goal[:100]}...\n")

        while round_idx <= max_adjustments:
            step = 0
            if round_idx > 0:
                context.append({"role": "user", "content": f"用户反馈: {ans}。请根据反馈调整策略。"})
                print(f"\n--- 第 {round_idx + 1} 轮调整（用户反馈后） ---\n")

            while step < max_steps:
                step += 1
                tracer_step += 1
                tools_schema = H.tools.to_openai_schemas() or None
                resp = self.llm.chat(context, tools=tools_schema)
                text = resp["text"]
                tool_calls = resp.get("tool_calls")
                H.tracer.record(tracer_step, text, {"tool_calls": tool_calls})

                print(f"[第{round_idx + 1}轮 Step {step}/{max_steps}]")
                if text:
                    print(f"  思考: {text[:300]}")

                if not tool_calls:
                    print(f"\n=== 第 {round_idx + 1} 轮探索完成 ===")
                    ans = input(f"Agent 输出:\n{text[:500]}\n\n确认此结果? (y/调整建议): ")
                    if ans.lower() == "y":
                        H.tracer.flush()
                        return text
                    round_idx += 1
                    if round_idx > max_adjustments:
                        print("已达最大调整次数，自动完成")
                        H.tracer.flush()
                        return text
                    break  # 跳出内层循环，外层启动新一轮

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

                for tc in tool_calls:
                    target = tc["arguments"].get("url") or tc["arguments"].get("path") or tc["arguments"].get("command", "")[:60]
                    print(f"  动作: {tc['name']}({target[:80]})")
                    action = {"tool": tc["name"], "args": tc["arguments"]}
                    try:
                        ok, reason = H.guardrail.allow(action)
                    except EOFError:
                        ok, reason = False, "非交互环境，默认拒绝"
                    if not ok:
                        context.append({"role": "tool", "tool_call_id": tc["id"], "content": f"动作被拦截: {reason}"})
                        H.tracer.record(tracer_step, "", action, f"GUARDRAIL_DENY: {reason}")
                        print(f"  拦截: {reason}")
                        continue
                    try:
                        result = H.tools.call(tc["name"], tc["arguments"])
                    except Exception as e:
                        result = f"工具失败: {e}"
                    context.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                    H.tracer.record(tracer_step, "", action, result)
                    print(f"  结果: {result[:200]}")

            if step >= max_steps:
                break  # 步数耗尽未完成，退出外层

        H.tracer.flush()
        return "任务未完成（达到步数上限）"