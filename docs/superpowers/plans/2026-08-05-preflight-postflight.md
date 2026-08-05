# 前导检查 + 后导保存 + 文件存储层 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前"输入域名→Agent 跑→结束"升级为三段式：前导检查(崩溃/暂存/备份/策略)→Agent 工作→后导保存(备份/替换/崩溃清理)，所有文件操作通过新 FileStore 模块统一管理。

**Architecture:** 新增 `src/filestore.py`(文件层)、`src/preflight.py`(前导)、`src/postflight.py`(后导)，重构 `main.py` 为三段式入口。FileStore 被 preflight/postflight 共享；preflight 返回 `PreflightResult`(crash_mode/should_exit/goal_context)；postflight 独立完成保存流程。Agent 循环不改。

**Tech Stack:** Python 3.13、pytest、json、pathlib、datetime、dataclasses。

## Global Constraints

- 目录结构：`data/strategies/`(策略)、`data/backups/`(备份≤3)、`data/checkpoints/`(暂存+crash)
- crash 和 checkpoint 文件操作不经过 Guardrail 确认，直接写/删
- 备份、策略、暂存的读/写/删需通过 preflight/postflight 的 `input()` 交互确认
- 所有文件路径通过 `FileStore` 的 path 方法推导，禁止硬编码路径字面量

---

### Task 1: `src/filestore.py` — 文件存储层

**Files:**
- Create: `explorer-agent/src/filestore.py`
- Create: `explorer-agent/tests/test_filestore.py`

**Interfaces:**
- Produces: `FileStore(base_dir)` class with methods: `strategy_path/read/write/delete/exists`, `backup_paths/count/read/write/delete/swap`, `checkpoint_path/read/write/delete/exists`, `crash_path/read/write/delete/exists`

- [ ] **Step 1: 写失败测试**

创建 `explorer-agent/tests/test_filestore.py`：

```python
"""FileStore 单元测试。"""
import json
import tempfile
from pathlib import Path
from src.filestore import FileStore


def test_strategy_path(tmp_path):
    store = FileStore(str(tmp_path))
    assert store.strategy_path("cs.nju.edu.cn") == tmp_path / "strategies" / "cs.nju.edu.cn.json"


def test_strategy_write_read_delete(tmp_path):
    store = FileStore(str(tmp_path))
    data = {"meta": {"domain": "cs.nju.edu.cn"}}
    store.strategy_write("cs.nju.edu.cn", data)
    assert store.strategy_exists("cs.nju.edu.cn")
    assert store.strategy_read("cs.nju.edu.cn")["meta"]["domain"] == "cs.nju.edu.cn"
    store.strategy_delete("cs.nju.edu.cn")
    assert not store.strategy_exists("cs.nju.edu.cn")


def test_strategy_exists_missing(tmp_path):
    store = FileStore(str(tmp_path))
    assert not store.strategy_exists("nonexistent.example.com")


def test_strategy_read_missing(tmp_path):
    store = FileStore(str(tmp_path))
    assert store.strategy_read("nonexistent.example.com") is None


def test_backup_paths_ordered_by_time(tmp_path):
    store = FileStore(str(tmp_path))
    store.backup_write("cs.nju.edu.cn", {"_backup_at": "2026-01-01T00:00:00"})
    store.backup_write("cs.nju.edu.cn", {"_backup_at": "2026-01-02T00:00:00"})
    paths = store.backup_paths("cs.nju.edu.cn")
    assert len(paths) == 2
    assert "bak1" in str(paths[0])
    assert "bak2" in str(paths[1])


def test_backup_count_max_three_overwrite_oldest(tmp_path):
    store = FileStore(str(tmp_path))
    for i in range(4):
        store.backup_write("cs.nju.edu.cn", {"seq": i})
    assert store.backup_count("cs.nju.edu.cn") == 3
    nums = [b["seq"] for b in [store.backup_read("cs.nju.edu.cn", 1), store.backup_read("cs.nju.edu.cn", 2), store.backup_read("cs.nju.edu.cn", 3)]]
    assert nums == [1, 2, 3]  # 覆盖了 seq=0 的旧备份


def test_backup_swap(tmp_path):
    store = FileStore(str(tmp_path))
    store.strategy_write("cs.nju.edu.cn", {"meta": {"domain": "cs.nju.edu.cn"}, "version": "strategy"})
    store.backup_write("cs.nju.edu.cn", {"meta": {"domain": "cs.nju.edu.cn"}, "version": "backup1"})
    store.backup_swap("cs.nju.edu.cn", 1)
    assert store.strategy_read("cs.nju.edu.cn")["version"] == "backup1"
    assert store.backup_read("cs.nju.edu.cn", 1)["version"] == "strategy"


def test_checkpoint_write_read_delete(tmp_path):
    store = FileStore(str(tmp_path))
    store.checkpoint_write("cs.nju.edu.cn", {"data": "checkpoint"})
    assert store.checkpoint_exists("cs.nju.edu.cn")
    assert store.checkpoint_read("cs.nju.edu.cn")["data"] == "checkpoint"
    store.checkpoint_delete("cs.nju.edu.cn")
    assert not store.checkpoint_exists("cs.nju.edu.cn")


def test_crash_write_read_delete(tmp_path):
    store = FileStore(str(tmp_path))
    store.crash_write("cs.nju.edu.cn", {"data": "crash"})
    assert store.crash_exists("cs.nju.edu.cn")
    assert store.crash_read("cs.nju.edu.cn")["data"] == "crash"
    store.crash_delete("cs.nju.edu.cn")
    assert not store.crash_exists("cs.nju.edu.cn")
```

- [ ] **Step 2: 运行测试确认失败（红）**

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_filestore.py -v 2>&1 | tail -15
```
Expected: all 8 FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: 实现 FileStore**

创建 `explorer-agent/src/filestore.py`：

```python
"""统一文件存储层：策略/备份/暂存/crash 文件的路径和 CRUD。"""
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


class FileStore:
    def __init__(self, base_dir: str):
        self._base = Path(base_dir)
        self._strategies = self._base / "strategies"
        self._backups = self._base / "backups"
        self._checkpoints = self._base / "checkpoints"
        for d in [self._strategies, self._backups, self._checkpoints]:
            d.mkdir(parents=True, exist_ok=True)

    # ---- 策略 ----
    def strategy_path(self, domain: str) -> Path:
        return self._strategies / f"{domain}.json"

    def strategy_exists(self, domain: str) -> bool:
        return self.strategy_path(domain).exists()

    def strategy_read(self, domain: str) -> dict | None:
        p = self.strategy_path(domain)
        if not p.exists():
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def strategy_write(self, domain: str, data: dict) -> Path:
        p = self.strategy_path(domain)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return p

    def strategy_delete(self, domain: str):
        p = self.strategy_path(domain)
        if p.exists():
            p.unlink()

    # ---- 备份 (每域名 ≤3) ----
    def _backup_path(self, domain: str, index: int) -> Path:
        return self._backups / f"{domain}.bak{index}.json"

    def backup_paths(self, domain: str) -> list[Path]:
        paths = [self._backup_path(domain, i) for i in [1, 2, 3] if self._backup_path(domain, i).exists()]
        paths.sort(key=lambda p: p.stat().st_mtime)
        return paths

    def backup_count(self, domain: str) -> int:
        return len(self.backup_paths(domain))

    def backup_write(self, domain: str, data: dict) -> int:
        existing = [self._backup_path(domain, i) for i in [1, 2, 3] if self._backup_path(domain, i).exists()]
        path = None
        for i in [1, 2, 3]:
            p = self._backup_path(domain, i)
            if not p.exists():
                path = p
                break
        if path is None and existing:
            existing.sort(key=lambda p: p.stat().st_mtime)
            path = existing[0]
        assert path is not None
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return int(path.stem[-1])

    def backup_read(self, domain: str, index: int) -> dict:
        with open(self._backup_path(domain, index), encoding="utf-8") as f:
            return json.load(f)

    def backup_delete(self, domain: str, index: int):
        p = self._backup_path(domain, index)
        if p.exists():
            p.unlink()

    def backup_swap(self, domain: str, index: int):
        strat = self.strategy_read(domain)
        bak = self.backup_read(domain, index)
        if strat is None or bak is None:
            return
        self.strategy_write(domain, bak)
        self.backup_write(domain, strat)
        bak_path = self._backup_path(domain, index)
        bak_path.unlink()
        self._backup_path(domain, index).write_text(json.dumps(strat, ensure_ascii=False, indent=2))

    # ---- 暂存 (0/1) ----
    def checkpoint_path(self, domain: str) -> Path:
        return self._checkpoints / f"{domain}.checkpoint.json"

    def checkpoint_exists(self, domain: str) -> bool:
        return self.checkpoint_path(domain).exists()

    def checkpoint_write(self, domain: str, data: dict):
        with open(self.checkpoint_path(domain), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def checkpoint_read(self, domain: str) -> dict:
        with open(self.checkpoint_path(domain), encoding="utf-8") as f:
            return json.load(f)

    def checkpoint_delete(self, domain: str):
        p = self.checkpoint_path(domain)
        if p.exists():
            p.unlink()

    # ---- 特殊暂存/crash (0/1) ----
    def crash_path(self, domain: str) -> Path:
        return self._checkpoints / f"{domain}.crash.json"

    def crash_exists(self, domain: str) -> bool:
        return self.crash_path(domain).exists()

    def crash_write(self, domain: str, data: dict):
        with open(self.crash_path(domain), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def crash_read(self, domain: str) -> dict:
        with open(self.crash_path(domain), encoding="utf-8") as f:
            return json.load(f)

    def crash_delete(self, domain: str):
        p = self.crash_path(domain)
        if p.exists():
            p.unlink()
```

- [ ] **Step 4: 运行测试确认通过（绿）**

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_filestore.py -v 2>&1 | tail -15
```
Expected: 8 passed

- [ ] **Step 5: 提交**

```bash
cd /home/wangzhiheng/whaleU-crawler && git add explorer-agent/src/filestore.py explorer-agent/tests/test_filestore.py && git commit -m "feat: FileStore — unified file layer for strategies/backups/checkpoints/crash"
```

---

### Task 2: `src/preflight.py` — 前导检查

**Files:**
- Create: `explorer-agent/src/preflight.py`
- Create: `explorer-agent/tests/test_preflight.py`

**Interfaces:**
- Consumes: `FileStore` from Task 1
- Produces: `PreflightResult(crash_mode: bool, should_exit: bool, goal_context: str)`, `preflight(domain, store) -> PreflightResult`

- [ ] **Step 1: 写失败测试**

创建 `explorer-agent/tests/test_preflight.py`：

```python
"""preflight 单元测试。"""
from src.filestore import FileStore
from src.preflight import PreflightResult, preflight


def test_no_files_continue(tmp_path):
    store = FileStore(str(tmp_path))
    result = preflight("cs.nju.edu.cn", store, auto_confirm=True)
    assert result.crash_mode is False
    assert result.should_exit is False
    assert result.goal_context == ""


def test_crash_detected(tmp_path):
    store = FileStore(str(tmp_path))
    store.crash_write("cs.nju.edu.cn", {"meta": {"domain": "cs.nju.edu.cn"}})
    result = preflight("cs.nju.edu.cn", store, auto_confirm=True)
    assert result.crash_mode is True


def test_checkpoint_exists_prompt_yes(tmp_path, monkeypatch):
    store = FileStore(str(tmp_path))
    store.checkpoint_write("cs.nju.edu.cn", {"meta": {"domain": "cs.nju.edu.cn"}})
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    result = preflight("cs.nju.edu.cn", store)
    assert result.goal_context != ""
    assert store.checkpoint_exists("cs.nju.edu.cn")  # 不删


def test_checkpoint_exists_prompt_no(tmp_path, monkeypatch):
    store = FileStore(str(tmp_path))
    store.checkpoint_write("cs.nju.edu.cn", {"meta": {"domain": "cs.nju.edu.cn"}})
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    result = preflight("cs.nju.edu.cn", store)
    assert not store.checkpoint_exists("cs.nju.edu.cn")  # 删除


def test_strategy_exists_skip_exit(tmp_path, monkeypatch):
    store = FileStore(str(tmp_path))
    store.strategy_write("cs.nju.edu.cn", {"meta": {"domain": "cs.nju.edu.cn"}})
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    result = preflight("cs.nju.edu.cn", store)
    assert result.should_exit is True


def test_strategy_exists_continue_with_ref(tmp_path, monkeypatch):
    store = FileStore(str(tmp_path))
    store.strategy_write("cs.nju.edu.cn", {"meta": {"domain": "cs.nju.edu.cn"}})
    answers = iter(["y", "y"])  # 仍要爬取? y, 参考? y
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    result = preflight("cs.nju.edu.cn", store)
    assert result.goal_context != ""
    assert "已有策略" in result.goal_context
```

`auto_confirm=True` 参数使前两个测试跳过 `input()`：所有非关键交互默认"否"，直接进入正常流程。

- [ ] **Step 2: 运行测试确认失败（红）**

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_preflight.py -v 2>&1 | tail -10
```
Expected: 6 FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: 实现 preflight**

创建 `explorer-agent/src/preflight.py`：

```python
"""前导检查：崩溃恢复→暂存→备份→策略检查。"""
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
```

- [ ] **Step 4: 运行测试确认通过（绿）**

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_preflight.py -v 2>&1 | tail -10
```
Expected: 6 passed

- [ ] **Step 5: 提交**

```bash
cd /home/wangzhiheng/whaleU-crawler && git add explorer-agent/src/preflight.py explorer-agent/tests/test_preflight.py && git commit -m "feat: preflight — crash/checkpoint/backup/strategy pre-launch checks"
```

---

### Task 3: `src/postflight.py` — 后导保存

**Files:**
- Create: `explorer-agent/src/postflight.py`
- Create: `explorer-agent/tests/test_postflight.py`

**Interfaces:**
- Consumes: `FileStore` from Task 1
- Produces: `postflight(domain, store) -> None`

- [ ] **Step 1: 写失败测试**

创建 `explorer-agent/tests/test_postflight.py`：

```python
"""postflight 单元测试。"""
from src.filestore import FileStore
from src.postflight import postflight


def test_no_existing_strategy_direct_save(tmp_path, monkeypatch):
    store = FileStore(str(tmp_path))
    data = {"meta": {"domain": "cs.nju.edu.cn"}, "entries": []}
    store.crash_write("cs.nju.edu.cn", data)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    postflight("cs.nju.edu.cn", store)
    assert store.strategy_exists("cs.nju.edu.cn")
    assert not store.crash_exists("cs.nju.edu.cn")


def test_existing_strategy_delete_old(tmp_path, monkeypatch):
    store = FileStore(str(tmp_path))
    old = {"meta": {"domain": "cs.nju.edu.cn"}, "entries": [{"name": "old"}]}
    new = {"meta": {"domain": "cs.nju.edu.cn"}, "entries": [{"name": "new"}]}
    store.strategy_write("cs.nju.edu.cn", old)
    store.crash_write("cs.nju.edu.cn", new)
    answers = iter(["删除"])  # 删除 or 备份
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    postflight("cs.nju.edu.cn", store)
    assert store.strategy_read("cs.nju.edu.cn")["entries"][0]["name"] == "new"
    assert not store.crash_exists("cs.nju.edu.cn")


def test_existing_strategy_backup_old(tmp_path, monkeypatch):
    store = FileStore(str(tmp_path))
    old = {"meta": {"domain": "cs.nju.edu.cn"}, "entries": [{"name": "old"}]}
    new = {"meta": {"domain": "cs.nju.edu.cn"}, "entries": [{"name": "new"}]}
    store.strategy_write("cs.nju.edu.cn", old)
    store.crash_write("cs.nju.edu.cn", new)
    answers = iter(["备份"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    postflight("cs.nju.edu.cn", store)
    assert store.strategy_read("cs.nju.edu.cn")["entries"][0]["name"] == "new"
    assert store.backup_count("cs.nju.edu.cn") == 1
    assert store.backup_read("cs.nju.edu.cn", 1)["entries"][0]["name"] == "old"
    assert not store.crash_exists("cs.nju.edu.cn")
```

- [ ] **Step 2: 运行测试确认失败（红）**

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_postflight.py -v 2>&1 | tail -10
```
Expected: 3 FAIL

- [ ] **Step 3: 实现 postflight**

创建 `explorer-agent/src/postflight.py`：

```python
"""后导保存：crash 写入→策略读出→备份/替换→清理 crash。"""
import json

from .filestore import FileStore


def postflight(domain: str, store: FileStore):
    data = store.crash_read(domain)
    if data is None:
        print("未发现生成策略，后导跳过")
        return

    if not store.strategy_exists(domain):
        store.strategy_write(domain, data)
        store.crash_delete(domain)
        print(f"策略已保存: {store.strategy_path(domain)}")
        return

    ans = input("已有策略，删除还是备份？（删除/备份）: ")
    if "删除" in ans:
        store.strategy_delete(domain)
        store.strategy_write(domain, data)
        store.crash_delete(domain)
        print(f"已删除旧策略，新策略已保存")
    else:
        if store.backup_count(domain) >= 3:
            _manage_backup_limit(domain, store)
        if store.backup_count(domain) < 3:
            old = store.strategy_read(domain)
            if old:
                store.backup_write(domain, old)
            store.strategy_write(domain, data)
            store.crash_delete(domain)
            print(f"旧策略已备份，新策略已保存")
        else:
            store.strategy_write(domain, data)
            store.crash_delete(domain)
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
```

- [ ] **Step 4: 运行测试确认通过（绿）**

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_postflight.py -v 2>&1 | tail -10
```
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
cd /home/wangzhiheng/whaleU-crawler && git add explorer-agent/src/postflight.py explorer-agent/tests/test_postflight.py && git commit -m "feat: postflight — crash-protected strategy save with backup management"
```

---

### Task 4: main.py 重构 + 配置更新

**Files:**
- Modify: `explorer-agent/main.py`
- Modify: `explorer-agent/.env.example`
- Modify: `explorer-agent/agent.yaml`

**Interfaces:**
- Consumes: `FileStore`, `preflight`, `postflight` from Tasks 1-3

- [ ] **Step 1: 更新 agent.yaml**

在 `explorer-agent/agent.yaml` 的 `paths:` 段追加：

```yaml
paths:
  strategies_dir: "${STRATEGIES_DIR}"
  crawler_script: "${CRAWLER_SCRIPT}"
  nju_browser: "${NJU_BROWSER_DIR}"
  data_dir: "${DATA_DIR}"
```

- [ ] **Step 2: 更新 .env.example**

在 `explorer-agent/.env.example` 的路径配置段追加一行：

```
DATA_DIR="/home/wangzhiheng/whaleU-crawler/data"
```

- [ ] **Step 3: 重构 main.py**

替换 `explorer-agent/main.py` 为三段式版本：

```python
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
```

- [ ] **Step 4: 测试**

运行 preflight + postflight 的已有测试确认重构不破坏：

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_preflight.py tests/test_postflight.py tests/test_filestore.py -v 2>&1 | tail -15
```
Expected: all pass (8+6+3=17 tests)

- [ ] **Step 5: 提交**

```bash
cd /home/wangzhiheng/whaleU-crawler && git add explorer-agent/main.py explorer-agent/.env.example explorer-agent/agent.yaml && git commit -m "refactor: three-stage main.py (preflight→agent→postflight) + DATA_DIR config"
```

---

### Task 5: AGENT_LOG 更新

- [ ] **Step 1: 追加日志**

在 `AGENT_LOG.md` 末尾追加：

```
## 2026-08-05 会话七：三段式流程（preflight + postflight + FileStore）

### [人] 需求
- 按 无关文档/流程改进设计.md 的完整流程图实现：前导检查（崩溃/暂存/备份/策略）+ 后导保存（备份/替换）+ FileStore 文件层
- 目录：data/strategies/（策略）、data/backups/（≤3备份）、data/checkpoints/（暂存+crash）
- crash/checkpoint 不经 Guardrail，直接读写

### [AI] brainstorm + spec
- 方案 1（三段式模块）：FileStore 文件层 → preflight 前导 → postflight 后导
- spec 自审通过 → writing-plans → 5 task
- 目录 `data/`（非 strategies 内部），4 种文件类型各有格式标准

### [AI] 实现
- Task 1-3: FileStore + preflight + postflight（TDD，17 测试新+原）
- Task 4: main.py 重构为三段式 + agent.yaml/.env.example 加 DATA_DIR
- Task 5: 本日志

### 待办
- [ ] 用户跑检查 1 验证三段式流程
```

- [ ] **Step 2: 提交**

```bash
cd /home/wangzhiheng/whaleU-crawler && git add AGENT_LOG.md && git commit -m "docs: log three-stage flow (preflight+postflight+filestore) implementation"
```

---

## Self-Review

**1. Spec coverage:**
- §4 目录结构 → Task 1 (FileStore `__init__` creates dirs)
- §5.1 FileStore 接口 → Task 1 (full implementation)
- §5.2 preflight 六关 → Task 2 (all checks + tests)
- §5.3 postflight 保存 → Task 3 (full flow + tests)
- §5.4 main.py 重构 → Task 4 (three-stage refactor)
- §6 确认规则 → Task 3 (crash exempt, others via input())

**2. Placeholder scan:** No TBD/TODO. All code blocks are complete.

**3. Type consistency:** `PreflightResult` used in Task 2 and Task 4 consistently. `FileStore` used across all tasks. `postflight(domain, store)` signature consistent.
