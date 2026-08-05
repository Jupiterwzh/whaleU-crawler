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
        count = self.backup_count(domain)
        if count == 3:
            b2 = self.backup_read(domain, 2)
            b3 = self.backup_read(domain, 3)
            self._backup_path(domain, 1).write_text(json.dumps(b2, ensure_ascii=False, indent=2))
            self._backup_path(domain, 2).write_text(json.dumps(b3, ensure_ascii=False, indent=2))
            self._backup_path(domain, 3).write_text(json.dumps(data, ensure_ascii=False, indent=2))
            return 3
        for i in [1, 2, 3]:
            p = self._backup_path(domain, i)
            if not p.exists():
                p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
                return i
        return -1

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
        with open(self.strategy_path(domain), "w", encoding="utf-8") as f:
            json.dump(bak, f, ensure_ascii=False, indent=2)
        with open(self._backup_path(domain, index), "w", encoding="utf-8") as f:
            json.dump(strat, f, ensure_ascii=False, indent=2)

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
