#!/usr/bin/env python3
"""clean_runtime — 清理 Agent 运行产物（可选），只清理轨迹/备份/暂存，绝不碰 RAG 与策略。

用法（项目根）：
    python tools/clean_runtime.py                  # 交互式：逐项询问是否清理
    python tools/clean_runtime.py --traces         # 只清理轨迹（保留最近 10 个）
    python tools/clean_runtime.py --backups        # 只清理策略备份（保留最近 3 个）
    python tools/clean_runtime.py --checkpoints    # 清理暂存/崩溃文件
    python tools/clean_runtime.py --all            # 全部清理（交互确认）

安全边界：只操作各 Agent 的 traces/、crawler/data/backups/、各 checkpoints/ 目录。
**绝不删除 RAG（data/rag/）与策略（crawler/data/strategies/）**。
"""
import argparse
import sys
from pathlib import Path

_PROJ_ROOT = Path(__file__).resolve().parent.parent

# 各 Agent 轨迹目录
TRACE_DIRS = [
    _PROJ_ROOT / "explorer-agent" / "traces",
    _PROJ_ROOT / "query-agent" / "traces",
    _PROJ_ROOT / "rag-manager" / "traces",
]
# 策略备份目录
BACKUP_DIRS = [_PROJ_ROOT / "crawler" / "data" / "backups"]
# 暂存/崩溃目录
CHECKPOINT_DIRS = [
    _PROJ_ROOT / "crawler" / "data" / "checkpoints",
    _PROJ_ROOT / "data" / "checkpoints",
]

TRACE_KEEP = 10      # 轨迹保留最近 N 个
BACKUP_KEEP = 3      # 备份保留最近 N 个


def _ask(prompt: str) -> bool:
    try:
        return input(f"{prompt} (y/n): ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def clean_traces(keep: int = TRACE_KEEP, interactive: bool = False) -> int:
    """清理各 Agent 轨迹，保留最近 keep 个。返回删除文件数。"""
    deleted = 0
    for d in TRACE_DIRS:
        if not d.is_dir():
            continue
        files = sorted(d.glob("trace-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        to_del = files[keep:]
        if not to_del:
            continue
        if interactive and not _ask(f"清理 {d} 的 {len(to_del)} 个旧轨迹（保留最近 {keep} 个）?"):
            continue
        for p in to_del:
            try:
                p.unlink()
                deleted += 1
            except OSError:
                pass
    return deleted


def clean_backups(keep: int = BACKUP_KEEP, interactive: bool = False) -> int:
    """清理策略备份，保留最近 keep 个。返回删除文件数。"""
    deleted = 0
    for d in BACKUP_DIRS:
        if not d.is_dir():
            continue
        files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        to_del = files[keep:]
        if not to_del:
            continue
        if interactive and not _ask(f"清理 {d} 的 {len(to_del)} 个旧备份（保留最近 {keep} 个）?"):
            continue
        for p in to_del:
            try:
                p.unlink()
                deleted += 1
            except OSError:
                pass
    return deleted


def clean_checkpoints(interactive: bool = False) -> int:
    """清理暂存/崩溃文件。返回删除文件数。"""
    deleted = 0
    for d in CHECKPOINT_DIRS:
        if not d.is_dir():
            continue
        files = list(d.iterdir()) if d.exists() else []
        if not files:
            continue
        if interactive and not _ask(f"清理 {d} 的 {len(files)} 个暂存/崩溃文件?"):
            continue
        for p in files:
            if p.is_file():
                try:
                    p.unlink()
                    deleted += 1
                except OSError:
                    pass
    return deleted


def main():
    parser = argparse.ArgumentParser(description="清理 Agent 运行产物（轨迹/备份/暂存），绝不碰 RAG 与策略")
    parser.add_argument("--traces", action="store_true", help="清理轨迹（保留最近 10 个）")
    parser.add_argument("--backups", action="store_true", help="清理策略备份（保留最近 3 个）")
    parser.add_argument("--checkpoints", action="store_true", help="清理暂存/崩溃文件")
    parser.add_argument("--all", action="store_true", help="全部清理（交互确认）")
    parser.add_argument("--yes", action="store_true", help="不交互，直接清理")
    args = parser.parse_args()

    interactive = not args.yes
    total = 0
    if args.all or args.traces:
        n = clean_traces(interactive=interactive)
        total += n
        if not args.yes:
            print(f"轨迹：删除 {n} 个")
    if args.all or args.backups:
        n = clean_backups(interactive=interactive)
        total += n
        if not args.yes:
            print(f"备份：删除 {n} 个")
    if args.all or args.checkpoints:
        n = clean_checkpoints(interactive=interactive)
        total += n
        if not args.yes:
            print(f"暂存/崩溃：删除 {n} 个")

    if not (args.all or args.traces or args.backups or args.checkpoints):
        parser.print_help()
        return
    print(f"\n共清理 {total} 个文件。RAG 与策略未受影响。")


if __name__ == "__main__":
    main()
