"""前导检查：崩溃恢复→暂存→备份→策略检查。"""
import json
from dataclasses import dataclass, field

from .filestore import FileStore


@dataclass
class PreflightResult:
    crash_mode: bool = False
    should_exit: bool = False
    goal_context: str = ""


def preflight(domain: str, store: FileStore, auto_confirm: bool = False) -> PreflightResult:
    prompt = (lambda msg: "y" if auto_confirm else input(msg))

    if store.crash_exists(domain):
        print(f"发现意外退出前的暂存策略（{domain}.crash.json），将进入保存流程")
        return PreflightResult(crash_mode=True)

    mark_read_checkpoint = False
    if store.checkpoint_exists(domain):
        ans = input("检测到上次暂存文件，是否参考？（y/否）: ")
        if ans.lower() == "y":
            mark_read_checkpoint = True
        else:
            store.checkpoint_delete(domain)
            print("已删除暂存文件")

    # A: 备份管理
    if store.backup_count(domain) > 0:
        n = store.backup_count(domain)
        ans = input(f"检测到 {n} 个策略备份（上限 3 个），是否需要管理备份文件？（y/否）: ")
        if ans.lower() == "y":
            _manage_backups(domain, store)

    # B: 已有策略
    goal_context = ""
    if store.strategy_exists(domain):
        ans = input(f"域名 {domain} 已有策略，是否仍要爬取？（y/否）: ")
        if ans.lower() != "y":
            print(f"已取消。如需重新爬取 {domain}，请重新运行。")
            return PreflightResult(should_exit=True)
        ans = input("是否参考已有策略？（y/否）: ")
        if ans.lower() == "y":
            data = store.strategy_read(domain)
            if data:
                summary = json.dumps(data, ensure_ascii=False, indent=2)[:1000]
                goal_context += f"已有策略如下（供参考改进）：\n{summary}\n"
        else:
            ans = input("是否删除已有策略？（y/否）: ")
            if ans.lower() == "y":
                store.strategy_delete(domain)

    # C: 暂存
    if mark_read_checkpoint:
        data = store.checkpoint_read(domain)
        if data:
            goal_context += f"上次暂存策略（供参考）：\n{json.dumps(data, ensure_ascii=False, indent=2)[:1000]}\n"

    return PreflightResult(goal_context=goal_context)


def _manage_backups(domain: str, store: FileStore):
    paths = store.backup_paths(domain)
    print(f"\n{domain} 共有 {len(paths)} 个备份：")
    for idx, p in enumerate(paths, 1):
        data = store.backup_read(domain, idx)
        entries = len(data.get("entries", [])) if data else 0
        print(f"  {idx}. {p.name} — {entries} 个入口")
    print("交互管理（最多 5 轮反馈）：")
    print("  删除备份：删除备份 1")
    print("  交换启用：启用备份 2（与当前策略交换）")
    print("  输入 exit 或 done 结束管理\n")
    for round_no in range(5):
        if round_no == 3:
            print("⚠️ 已达 3 轮，上限 5 轮")
        ans = input(f"[备份管理 第{round_no+1}/5轮] 操作: ")
        if ans.lower() in ("exit", "done", ""):
            break
        parts = ans.split()
        if "删除" in ans and len(parts) >= 2:
            for part in parts:
                if part.isdigit():
                    idx = int(part)
                    if 1 <= idx <= store.backup_count(domain):
                        store.backup_delete(domain, idx)
                        print(f"  已删除备份 {idx}")
        elif "启用" in ans and len(parts) >= 2:
            for part in parts:
                if part.isdigit():
                    idx = int(part)
                    if 1 <= idx <= store.backup_count(domain):
                        store.backup_swap(domain, idx)
                        print(f"  已将备份 {idx} 和当前策略交换")
