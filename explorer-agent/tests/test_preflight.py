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
