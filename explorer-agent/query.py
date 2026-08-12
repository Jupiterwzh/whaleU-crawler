# query.py
"""query-agent 入口：装配 RAG 工具，复用 harness 主循环回答通知问题。"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.harness import Harness
from src.agent_loop import AgentLoop
from src.llm.client import LLMClient
from src.rag.ragstore import RAGStore


def load_env():
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)


def resolve_rag_dir() -> str:
    """RAG_DIR 环境变量优先，否则从 STRATEGIES_DIR 父级推导，兜底 ../data/rag。"""
    rag_dir = os.environ.get("RAG_DIR", "")
    if rag_dir:
        return rag_dir
    strategies_dir = os.environ.get("STRATEGIES_DIR", "")
    if strategies_dir:
        return str(Path(strategies_dir).resolve().parent / "rag")
    return str(Path(__file__).resolve().parent.parent / "data" / "rag")


def answer(question: str, rag_dir: str | None = None) -> str:
    """执行一次查询：RAG 检索 → 不够则爬虫补充 → 返回答案。CLI 与 WebUI 共用。"""
    store = RAGStore(rag_dir or resolve_rag_dir())
    if store.is_stale():
        store.refresh()

    harness = Harness.from_yaml("agent.yaml", rag_store=store)
    llm = LLMClient()
    loop = AgentLoop(harness, llm)
    return loop.run(f"用户问题: {question}\n请先从 RAG 检索，检索不到再考虑调用 run_crawler 补充。")


def main():
    load_env()
    args = sys.argv[1:]
    question = " ".join(args) or input("❓ 问题: ")
    result = answer(question)
    print(f"\n✅ 答案:\n{result}")


if __name__ == "__main__":
    main()
