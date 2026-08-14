"""前导检查：崩溃恢复→暂存→备份→策略检查。"""
import json
import re
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


def _parse_backup_cmd(ans: str) -> tuple[str, list[int]]:
    """解析备份管理命令。

    返回 (动作, 编号列表)。动作：delete/enable/detail/list/exit/unknown。
    支持写法：删除 1 / 删除1 / 1 / 删除 1 2 / 删除12 / 简介 3 / 启用12 等。
    备份编号上限 3，因此多位连写（如 12）按位拆成 [1, 2]；纯编号默认显示简介。
    """
    a = (ans or "").strip()
    low = a.lower()
    if low in ("exit", "done", ""):
        return "exit", []
    if low in ("list", "列表"):
        return "list", []
    # 提取所有数字字符，按位拆（上限 3，多位按位拆）
    digits = re.findall(r"[1-3]", a)
    idxs = [int(d) for d in digits]
    if not idxs:
        return "unknown", []
    if "删除" in a:
        return "delete", idxs
    if "启用" in a:
        return "enable", idxs
    if "简介" in a or "详情" in a:
        return "detail", idxs
    # 纯编号（无动作关键词）→ 默认简介
    return "detail", idxs


def _manage_backups(domain: str, store: FileStore):
    print(f"\n{domain} 共有 {store.backup_count(domain)} 个备份：")
    _list_backups(domain, store)
    print("操作：删除 [N] | 启用 [N] | 简介 [N] | 列表 | exit/done 结束（N 是上方备份列表的编号，如 删除 1）")
    for round_no in range(5):
        if round_no == 3:
            print("⚠️ 已达 3 轮，上限 5 轮")
        ans = input(f"[备份管理 第{round_no+1}/5轮] 操作: ").strip()
        action, idxs = _parse_backup_cmd(ans)
        if action == "exit":
            break
        if action == "list":
            _list_backups(domain, store)
            continue
        if action == "delete":
            for idx in idxs:
                store.backup_delete(domain, idx)
                print(f"  已删除备份 {idx}")
            _list_backups(domain, store)
        elif action == "enable":
            for idx in idxs:
                store.backup_swap(domain, idx)
                print(f"  已将备份 {idx} 和当前策略交换")
        elif action == "detail":
            for idx in idxs:
                _show_backup_detail(domain, store, idx)
        else:
            print("  无法识别。支持：删除 [N] | 启用 [N] | 简介 [N] | 列表 | exit（N 是上方备份编号，如 删除 1）")


def _list_backups(domain: str, store: FileStore):
    if store.backup_count(domain) == 0:
        print("  （无备份）")
        return
    for p in store.backup_paths(domain):
        idx = p.stem[-1]
        data = store.backup_read(domain, int(idx))
        entries = len(data.get("entries", [])) if data else 0
        meta = (data or {}).get("meta", {})
        updated = meta.get("updated", "")
        print(f"  [{idx}] {p.name} — {entries} 个入口，updated={updated}")


def _show_backup_detail(domain: str, store: FileStore, idx: int):
    data = store.backup_read(domain, idx)
    if not data:
        print(f"  备份 {idx} 不存在")
        return
    print(f"  备份 {idx} 详情：")
    for e in data.get("entries", []):
        print(f"    - {e.get('name','?')} | {e.get('url','?')} | 分页:{e.get('paginationType','?')}")
    print(f"    提取规则: {json.dumps(data.get('extraction', {}), ensure_ascii=False)[:120]}")
