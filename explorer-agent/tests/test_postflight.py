"""postflight 单元测试。"""
from src.filestore import FileStore
from src.postflight import postflight


def test_no_existing_strategy_direct_save(tmp_path, monkeypatch):
    store = FileStore(str(tmp_path))
    data = {"meta": {"domain": "cs.nju.edu.cn"}, "entries": []}
    store.strategy_write("cs.nju.edu.cn", data)  # agent 写入了
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    postflight("cs.nju.edu.cn", store)
    assert store.strategy_exists("cs.nju.edu.cn")
    assert not store.crash_exists("cs.nju.edu.cn")  # 无旧策略，crash 已清理


def test_existing_strategy_delete_old(tmp_path, monkeypatch):
    store = FileStore(str(tmp_path))
    old = {"meta": {"domain": "cs.nju.edu.cn"}, "entries": [{"name": "old"}]}
    new = {"meta": {"domain": "cs.nju.edu.cn"}, "entries": [{"name": "new"}]}
    store.strategy_write("cs.nju.edu.cn", new)  # agent 写入新策略
    answers = iter(["删除"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    postflight("cs.nju.edu.cn", store, old_data=old)
    assert store.strategy_read("cs.nju.edu.cn")["entries"][0]["name"] == "new"
    assert not store.crash_exists("cs.nju.edu.cn")


def test_existing_strategy_backup_old(tmp_path, monkeypatch):
    store = FileStore(str(tmp_path))
    old = {"meta": {"domain": "cs.nju.edu.cn"}, "entries": [{"name": "old"}]}
    new = {"meta": {"domain": "cs.nju.edu.cn"}, "entries": [{"name": "new"}]}
    store.strategy_write("cs.nju.edu.cn", new)  # agent 写入新策略
    answers = iter(["备份"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    postflight("cs.nju.edu.cn", store, old_data=old)
    assert store.strategy_read("cs.nju.edu.cn")["entries"][0]["name"] == "new"
    assert store.backup_count("cs.nju.edu.cn") == 1
    assert store.backup_read("cs.nju.edu.cn", 1)["entries"][0]["name"] == "old"
    assert not store.crash_exists("cs.nju.edu.cn")

def test_postflight_promotes_draft(tmp_path, monkeypatch):
    """Agent 写草稿 → postflight 从草稿转正为正式策略。"""
    from src.postflight import postflight
    store = FileStore(str(tmp_path))
    # 旧正式策略
    store.strategy_write("cs.nju.edu.cn", {"meta": {"version": "old"}, "entries": []})
    # 新草稿
    store.strategy_draft_write("cs.nju.edu.cn", {"meta": {"version": "new"}, "entries": [{"name": "院内公告"}]})
    # 无旧数据（首次）时直接转正
    monkeypatch.setattr("builtins.input", lambda prompt="": "备份")
    postflight("cs.nju.edu.cn", store, old_data={"meta": {"version": "old"}, "entries": []})
    # 正式策略来自草稿
    assert store.strategy_read("cs.nju.edu.cn")["meta"]["version"] == "new"
    # 草稿已清
    assert not store.strategy_draft_path("cs.nju.edu.cn").exists()


def test_postflight_no_draft_skips(tmp_path, monkeypatch):
    """无草稿无正式策略 → 后导跳过。"""
    from src.postflight import postflight
    store = FileStore(str(tmp_path))
    postflight("cs.nju.edu.cn", store)
    assert not store.strategy_path("cs.nju.edu.cn").exists()
