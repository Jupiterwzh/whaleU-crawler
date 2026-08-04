# main.py
"""explorer-agent 入口。两种模式：--explore-only（爬虫委托）/ 直接目标（Agent 编排）。"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.harness import Harness
from src.agent_loop import AgentLoop
from src.llm.client import LLMClient


def load_env():
    """从 main.py 同目录的 .env 加载环境变量（覆盖已存在的 env 使 .env 始终优先）。"""
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)


def main():
    load_env()
    args = sys.argv[1:]
    explore_only = "--explore-only" in args
    if explore_only:
        idx = args.index("--explore-only")
        url = args[idx + 1] if idx + 1 < len(args) else ""
        strategies_dir = os.environ.get("STRATEGIES_DIR", "")
        domain = url.split("//")[1].split("/")[0] if "//" in url else url
        strategy_path = f"{strategies_dir}/{domain}.json" if strategies_dir else "策略目录"
        goal = f"探索 {url} 的通知公告入口，生成爬取策略 JSON，写入 {strategy_path}。不要调用爬虫执行爬取。"
    else:
        goal = " ".join(args) or input("🎯 任务: ")

    harness = Harness.from_yaml("agent.yaml")
    llm = LLMClient()
    loop = AgentLoop(harness, llm)
    result = loop.run(goal)
    print(f"\n✅ 结果:\n{result}")


if __name__ == "__main__":
    main()
