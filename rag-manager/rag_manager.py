# rag_manager.py
"""rag-manager 入口：管理 RAG 文档有效时间并重建索引。

职责链：pending_validity 读取待判定文档 → LLM（或纯函数兜底）判定有效时间
→ apply_validity 写回 → build_index 重建索引。Task 4 将在数据库更新后触发本 Agent。
"""
import argparse
import os
import sys
from pathlib import Path

# 把项目根加入 sys.path，使 shared/ 可导入（RAGStore / judge_validity 公共位置）
_PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT))

# 把自身目录加入 sys.path，使 src/ 可导入（harness 内核）
_AGENT_DIR = Path(__file__).resolve().parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from dotenv import load_dotenv

from src.harness import Harness
from shared.rag.ragstore import RAGStore
from shared.rag.validity import judge_validity


def load_env():
    # 先加载项目根 .env（集中配置主源），再加载本 Agent 目录 .env（缺失键继承根，有值覆盖根）
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)
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


class RagManager:
    """RAG 管理 Agent：给待判定文档分配有效时间并重建索引。

    - `_llm_judge` 默认回退到纯函数 `judge_validity`（确定性底座），无 LLM 也能跑。
    - 工具集：read_rag_docs / assign_validity / rebuild_index。
    """

    def __init__(self, rag_store: RAGStore):
        self.rag_store = rag_store

    # ---- 有效性判定（可被 mock，默认纯函数兜底）----
    def _llm_judge(self, doc: dict) -> dict:
        """返回 {doc_id, valid_from, valid_until|effective_days}。纯函数 judge_validity 兜底。"""
        v = judge_validity(doc.get("content", ""), doc.get("date"))
        return {
            "doc_id": doc["id"],
            "valid_from": v.get("valid_from"),
            "valid_until": v.get("valid_until"),
            "effective_days": v.get("effective_days"),
        }

    # ---- 主流程 ----
    def run(self) -> str:
        """批量处理 pending_validity 文档：判定 → 写回 → 重建索引。返回摘要。"""
        pending = self.rag_store.pending_validity()
        assigned = 0
        failed = 0
        for doc in pending:
            try:
                verdict = self._llm_judge(doc)
                if verdict.get("doc_id") != doc["id"]:
                    verdict["doc_id"] = doc["id"]
                ok = self.rag_store.apply_validity(
                    verdict["doc_id"],
                    valid_from=verdict.get("valid_from"),
                    valid_until=verdict.get("valid_until"),
                    effective_days=verdict.get("effective_days"),
                )
                if ok:
                    assigned += 1
                else:
                    failed += 1
            except (KeyError, ValueError):
                failed += 1
        self.rag_store.build_index()
        return (
            f"已处理 {len(pending)} 条待判定文档：成功分配 {assigned} 条，"
            f"失败 {failed} 条，索引已重建。"
        )

    def build_harness(self) -> Harness:
        """装配 Harness：agent.yaml 声明的 3 个 RAG 管理工具 + 规则。

        工具由 agent.yaml 的 builtin 工厂装配，工厂需要 store，故先注入。
        """
        from src.tools.rag_manager_tools import set_rag_store

        set_rag_store(self.rag_store)
        return Harness.from_yaml(str(self._agent_dir() / "agent.yaml"), rag_store=self.rag_store)

    @staticmethod
    def _agent_dir() -> Path:
        return Path(__file__).resolve().parent


def run_batch(rag_dir: str = None) -> str:
    """命令行批处理入口：加载 RAGStore → RagManager.run()。"""
    store = RAGStore(rag_dir or resolve_rag_dir())
    manager = RagManager(store)
    return manager.run()


def main():
    load_env()
    parser = argparse.ArgumentParser(description="RAG 管理 Agent：分配有效时间并重建索引")
    parser.add_argument("--domain", help="只处理指定 domain 的文档（预留，当前整批处理）")
    parser.add_argument("--rag-dir", help="RAG 数据目录，默认由环境变量/推导决定")
    args = parser.parse_args()
    print(run_batch(args.rag_dir))
    if args.domain:
        print(f"（--domain {args.domain}：当前版本为整批处理，忽略过滤）")


if __name__ == "__main__":
    main()
