"""前导检查：崩溃恢复→暂存→备份→策略检查。"""
import json
import sys
from dataclasses import dataclass, field

from .filestore import FileStore


def _confirm(prompt: str, default: bool, wrongs: list) -> bool:
    """带重试的 y/n 确认。wrongs[0] 跨问题共享，≥2 则退出。3 次错误后用 default。"""
    if wrongs[0] >= 2:
        print("本场对话已出现多次无效输入，为安全退出。")
        sys.exit(1)
    prefix = prompt.strip()
    for attempt in range(3):
        ans = input(prompt).strip()
        if ans.lower() in ("y", "yes"):
            return True
        if ans.lower() in ("n", "no"):
            return False
        wrongs[0] += 1
        if wrongs[0] >= 2:
            print("本场对话已出现多次无效输入，为安全退出。")
            sys.exit(1)
        remaining = 2 - attempt
        if remaining > 0:
            print(f"  请输入 y 或 n（还剩 {remaining} 次）")
    default_str = "y" if default else "n"
    print(f"  已耗尽重试次数，默认采用: {default_str}")
    return default


@dataclass
class PreflightResult:
    crash_mode: bool = False
    should_exit: bool = False
    goal_context: str = ""


def preflight(domain: str, store: FileStore, auto_confirm: bool = False) -> PreflightResult:
    wrongs = [0]  # mutable session counter

    if store.crash_exists(domain):
        print(f"发现意外退出前的暂存策略（{domain}.crash.json），将进入保存流程")
        return PreflightResult(crash_mode=True)

    mark_read_checkpoint = False
    if store.checkpoint_exists(domain):
        if auto_confirm or _confirm(f"检测到 {domain} 的暂存文件，是否参考？（y/n）: ", True, wrongs):
            mark_read_checkpoint = True
        else:
            store.checkpoint_delete(domain)
            print("已删除暂存文件")

    # A: 备份管理
    if store.backup_count(domain) > 0:
        n = store.backup_count(domain)
        if auto_confirm or _confirm(f"检测到 {domain} 有 {n} 个备份（上限 3），是否管理？（y/n）: ", False, wrongs):
            _manage_backups(domain, store)

    # B: 已有策略
    goal_context = ""
    if store.strategy_exists(domain):
        print(f"域名 {domain} 已有策略。")
        if not (auto_confirm or _confirm("是否仍要爬取？（y/n）: ", False, wrongs)):
            print(f"已取消。如需重新爬取 {domain}，请重新运行。")
            return PreflightResult(should_exit=True)
        if auto_confirm or _confirm("是否参考已有策略加以改进？（y/n）: ", True, wrongs):
            data = store.strategy_read(domain)
            if data:
                summary = json.dumps(data, ensure_ascii=False, indent=2)[:1000]
                goal_context += f"已有策略如下（供参考改进）：\n{summary}\n"
        else:
            if auto_confirm or _confirm("是否删除已有策略？（y/n）: ", False, wrongs):
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
    for p in paths:
        idx = p.stem[-1]  # stem = "cs.nju.edu.cn.bak1", [-1] = "1"
        data = store.backup_read(domain, int(idx))
        entries = len(data.get("entries", [])) if data else 0
        print(f"  [{idx}] {p.name} — {entries} 个入口")
    print("操作：删除 [N] | 启用 [N] | exit/done 结束")
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
                    store.backup_delete(domain, idx)
                    print(f"  已删除备份 {idx}")
                    # re-list after each action
                    for p in store.backup_paths(domain):
                        i = int(p.stem[-1])
                        data = store.backup_read(domain, i)
                        entries = len(data.get("entries", [])) if data else 0
                        print(f"    [{i}] {p.name} — {entries} 个入口")
        elif "启用" in ans and len(parts) >= 2:
            for part in parts:
                if part.isdigit():
                    idx = int(part)
                    store.backup_swap(domain, idx)
                    print(f"  已将备份 {idx} 和当前策略交换")
