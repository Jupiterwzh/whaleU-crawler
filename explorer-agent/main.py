# main.py
"""explorer-agent 入口。三段式：前导检查→Agent 循环→后导保存。"""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from src.harness import Harness
from src.agent_loop import AgentLoop
from src.llm.client import LLMClient
from src.filestore import FileStore
from src.preflight import preflight
from src.postflight import postflight


def load_env():
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)


def _extract_domain(text: str) -> str:
    for token in text.split():
        if "://" in token:
            return urlparse(token).hostname or token
    return ""


def main():
    load_env()
    args = sys.argv[1:]
    explore_only = "--explore-only" in args

    if explore_only:
        idx = args.index("--explore-only")
        url = args[idx + 1] if idx + 1 < len(args) else ""
        domain = _extract_domain(url)
    else:
        user_text = " ".join(args)
        domain = _extract_domain(user_text)

    data_dir = os.environ.get("DATA_DIR", str(Path(__file__).resolve().parent.parent / "data"))
    store = FileStore(base_dir=data_dir)

    # ---- 前导 ----
    result = preflight(domain, store)
    if result.should_exit:
        return
    if result.crash_mode:
        postflight(domain, store)
        print("崩溃恢复完成")
        return

    # ---- 构造 goal ----
    if explore_only:
        strategies_dir = os.environ.get("STRATEGIES_DIR", "")
        strategy_path = f"{strategies_dir}/{domain}.json" if strategies_dir else "策略目录"
        goal = f"探索 {url} 的通知公告入口，生成爬取策略 JSON，写入 {strategy_path}。不要调用爬虫执行爬取。"
    else:
        user_goal = " ".join(args) or input("🎯 任务: ")
        strategies_dir = os.environ.get("STRATEGIES_DIR", "")
        ctx = result.goal_context
        if strategies_dir:
            suffix = f"策略 JSON 保存到 {strategies_dir}/{domain}.json"
        else:
            suffix = ""
        goal = f"{user_goal}。{suffix}。{ctx}"
    goal = goal.strip("。 ")

    # ---- Agent 循环 ----
    harness = Harness.from_yaml("agent.yaml")
    llm = LLMClient()
    loop = AgentLoop(harness, llm)
    loop.run(goal)

    # ---- 后导 ----
    postflight(domain, store)


if __name__ == "__main__":
    main()
