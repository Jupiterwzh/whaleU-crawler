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


def test_strategy_draft_write_promote(tmp_path):
    """草稿写入（不碰正式策略），转正后成为正式策略。"""
    store = FileStore(str(tmp_path))
    # 写正式策略（旧版）
    store.strategy_write("cs.nju.edu.cn", {"meta": {"version": "old"}, "entries": []})
    # 写草稿
    draft_data = {"meta": {"version": "new"}, "entries": [{"name": "院内公告"}]}
    store.strategy_draft_write("cs.nju.edu.cn", draft_data)
    # 正式策略未变
    assert store.strategy_read("cs.nju.edu.cn")["meta"]["version"] == "old"
    # 草稿存在
    assert store.strategy_draft_path("cs.nju.edu.cn").exists()
    # 转正：草稿覆盖正式策略
    store.strategy_draft_promote("cs.nju.edu.cn")
    assert store.strategy_read("cs.nju.edu.cn")["meta"]["version"] == "new"
    # 转正后删除草稿
    assert not store.strategy_draft_path("cs.nju.edu.cn").exists()


def test_strategy_draft_read_and_delete(tmp_path):
    """草稿读取与删除。"""
    store = FileStore(str(tmp_path))
    store.strategy_draft_write("cs.nju.edu.cn", {"meta": {"version": "draft"}, "entries": []})
    assert store.strategy_draft_read("cs.nju.edu.cn")["meta"]["version"] == "draft"
    store.strategy_draft_delete("cs.nju.edu.cn")
    assert not store.strategy_draft_path("cs.nju.edu.cn").exists()
