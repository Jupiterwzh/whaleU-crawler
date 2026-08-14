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


def test_parse_backup_cmd():
    """备份管理命令解析：支持 删除1 / 删除 1 / 1 / 删除 1 2 等写法。"""
    from src.preflight import _parse_backup_cmd
    assert _parse_backup_cmd("删除1") == ("delete", [1])
    assert _parse_backup_cmd("删除 1") == ("delete", [1])
    assert _parse_backup_cmd("启用2") == ("enable", [2])
    assert _parse_backup_cmd("简介 3") == ("detail", [3])
    assert _parse_backup_cmd("删除 1 2") == ("delete", [1, 2])
    assert _parse_backup_cmd("1") == ("detail", [1])  # 纯编号默认简介
    assert _parse_backup_cmd("exit") == ("exit", [])
    assert _parse_backup_cmd("列表") == ("list", [])
    assert _parse_backup_cmd("abc") == ("unknown", [])


def test_parse_backup_cmd_bare_index_is_detail():
    """纯编号默认显示简介（而非删除）。"""
    from src.preflight import _parse_backup_cmd
    assert _parse_backup_cmd("1") == ("detail", [1])
    assert _parse_backup_cmd("2") == ("detail", [2])


def test_parse_backup_cmd_concatenated_indices():
    """连写编号 12 拆成 [1,2]（备份上限 3，多位按位拆）。"""
    from src.preflight import _parse_backup_cmd
    assert _parse_backup_cmd("删除12") == ("delete", [1, 2])
    assert _parse_backup_cmd("简介12") == ("detail", [1, 2])
    assert _parse_backup_cmd("启用 12") == ("enable", [1, 2])


def test_parse_backup_cmd_done_exits():
    """done 仍可退出。"""
    from src.preflight import _parse_backup_cmd
    assert _parse_backup_cmd("done") == ("exit", [])
