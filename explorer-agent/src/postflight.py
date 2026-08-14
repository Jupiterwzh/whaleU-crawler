"""后导保存：新策略→crash 保护→旧策略备份/替换→清理。"""
import json

from .filestore import FileStore


def postflight(domain: str, store: FileStore, old_data: dict | None = None):
    # 优先读草稿（Agent 写草稿，确认后转正）；无草稿则读正式策略
    new_data = store.strategy_draft_read(domain)
    if new_data is None:
        new_data = store.strategy_read(domain)
    if new_data is None:
        print("未发现新生成策略，后导跳过")
        return

    store.crash_write(domain, new_data)

    # 从草稿读的 → 标记转正（草稿最终会被清理）
    from_draft = store.strategy_draft_exists(domain)

    if old_data is None:
        store.crash_delete(domain)
        store.strategy_draft_delete(domain)
        print(f"策略已保存: {store.strategy_path(domain)}")
        return

    ans = input("已有策略，删除还是备份？（删除/备份）: ")
    if "删除" in ans:
        store.strategy_write(domain, new_data)
        store.crash_delete(domain)
        store.strategy_draft_delete(domain)
        print("已删除旧策略，新策略已保存")
    else:
        if store.backup_count(domain) >= 3:
            _manage_backup_limit(domain, store)
        if store.backup_count(domain) < 3:
            store.backup_write(domain, old_data)
            store.strategy_write(domain, new_data)
            store.crash_delete(domain)
            store.strategy_draft_delete(domain)
            print("旧策略已备份，新策略已保存")
        else:
            store.strategy_write(domain, new_data)
            store.crash_delete(domain)
            store.strategy_draft_delete(domain)
            print("达到备份上限，旧策略未备份，新策略已保存")


def _manage_backup_limit(domain: str, store: FileStore):
    print(f"{domain} 备份已达上限（3 个）：")
    for idx, p in enumerate(store.backup_paths(domain), 1):
        print(f"  {idx}. {p.name} ({p.stat().st_mtime})")
    for round_no in range(5):
        if round_no == 3:
            print("⚠️ 已达 3 轮，上限 5 轮")
        if round_no == 4:
            ans = input("最终确认? (a=保留最后3个放弃备份/b=保留最后2个且备份/c=备份覆盖最旧): ")
        else:
            ans = input("处理建议：[删除 N] [保留最后3个放弃备份] [保留最后2个且备份] [放弃备份]: ")
        if "放弃备份" in ans or "保留3" in ans or (round_no == 4 and ans.lower() == "a"):
            path = store.backup_paths(domain)
            for p in path[:-3]:
                idx = int(p.stem[-1])
                store.backup_delete(domain, idx)
            print("已保留最后 3 个备份，放弃此次备份")
            return
        if "保留2" in ans or (round_no == 4 and ans.lower() == "c"):
            path = store.backup_paths(domain)
            for p in path[:-2]:
                idx = int(p.stem[-1])
                store.backup_delete(domain, idx)
            print("已保留最后 2 个备份，准备备份")
            return
        if round_no == 4 and ans.lower() == "b":
            print("在当前状态下执行备份")
            return
        if "删除" in ans:
            parts = ans.split()
            for part in parts:
                if part.isdigit():
                    idx = int(part)
                    if 1 <= idx <= store.backup_count(domain):
                        store.backup_delete(domain, idx)
                        print(f"  已删除备份 {idx}")