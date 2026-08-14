# query.py
"""query-agent 入口：管理 RAG 与爬虫，回答通知问题。

职责链：用户问题 → rag_search 检索 RAG → 不足时 run_crawler 调爬虫
→（爬虫无策略时委托内层策略 Agent）→ 数据入库 RAG → 再检索 → 回答。
"""
import os
import sys
from pathlib import Path

# 把项目根加入 sys.path，使 shared/ 可导入（RAGStore 公共位置）
_PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT))

from dotenv import load_dotenv

from src.harness import Harness
from src.agent_loop import AgentLoop
from src.llm.client import LLMClient
from shared.rag.ragstore import RAGStore


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
    return str(_PROJ_ROOT / "data" / "rag")


def answer(question: str, rag_dir: str | None = None) -> str:
    """执行一次查询：RAG 检索 → 不够则爬虫补充 → 返回答案。CLI 与 WebUI 共用。"""
    store = RAGStore(rag_dir or resolve_rag_dir())
    if store.is_stale():
        store.refresh()

    harness = Harness.from_yaml(str(Path(__file__).resolve().parent / "agent.yaml"), rag_store=store)
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
