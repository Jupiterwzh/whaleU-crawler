# tests/test_keys.py
import sys
from unittest.mock import patch
import src.keys as keys


def test_get_key_env_priority(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "env-key-123")
    with patch.object(keys, "keyring") as mock_kr:
        assert keys.get_key() == "env-key-123"
        mock_kr.get_password.assert_not_called()


def test_get_key_keyring_fallback(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with patch.object(keys, "keyring") as mock_kr:
        mock_kr.get_password.return_value = "ring-key-456"
        assert keys.get_key() == "ring-key-456"


def test_set_clear_key(monkeypatch):
    with patch.object(keys, "keyring") as mock_kr:
        keys.set_key("abc")
        mock_kr.set_password.assert_called_once()
        keys.clear_key()
        mock_kr.delete_password.assert_called_once()


def test_prompt_and_store(monkeypatch):
    with patch.object(keys, "getpass") as mock_gp, \
         patch.object(keys, "keyring") as mock_kr:
        mock_gp.getpass.return_value = "typed-key"
        result = keys.prompt_and_store()
        assert result == "typed-key"
        mock_kr.set_password.assert_called_once()


def test_env_fallback_when_no_keyring(tmp_path, monkeypatch):
    """keyring 不可用时降级到根 .env 文件。"""
    import src.keys as keys
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    monkeypatch.setattr(keys, "_ROOT_ENV_PATH", env_path)
    # 模拟 keyring 后端不可用
    with patch.object(keys, "keyring") as mock_kr:
        mock_kr.get_password.side_effect = Exception("no backend")
        mock_kr.set_password.side_effect = Exception("no backend")
        assert keys.get_key() == ""
        keys.set_key("env-fallback-key")
        assert keys._env_key() == "env-fallback-key"
        assert keys.get_key() == "env-fallback-key"
        keys.clear_key()
        assert keys._env_key() == ""


def test_env_roundtrip(monkeypatch, tmp_path):
    """.env 读写往返（保留其他行），key 写根 .env。"""
    import src.keys as keys
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_BASE_URL=https://api.deepseek.com/v1\nLLM_MODEL=deepseek-v4-flash\n", encoding="utf-8")
    monkeypatch.setattr(keys, "_ROOT_ENV_PATH", env_path)
    with patch.object(keys, "keyring") as mock_kr:
        mock_kr.get_password.side_effect = Exception("no backend")
        mock_kr.set_password.side_effect = Exception("no backend")
        keys.set_key("my-secret")
        content = env_path.read_text(encoding="utf-8")
        assert "LLM_BASE_URL" in content  # 其他行保留
        assert "LLM_API_KEY=my-secret" in content
        assert keys.get_key() == "my-secret"


def test_cmd_cli_clear_requires_confirmation(monkeypatch, capsys):
    """clear 需二次确认，拒绝则不删。"""
    import src.keys as keys
    monkeypatch.setattr(sys, "argv", ["whale-key.py", "clear"])
    # 用户拒绝
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    with patch.object(keys, "keyring"):
        keys.cmd_cli()
    out = capsys.readouterr().out
    assert "确定" in out or "清除" in out  # 有确认提示
    assert "已取消" in out  # 拒绝后取消


def test_cmd_cli_clear_confirmed_clears(monkeypatch, tmp_path):
    """clear 二次确认 y → 执行清除（keyring + .env 的 LLM_API_KEY 行）。"""
    import src.keys as keys
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_BASE_URL=x\nLLM_API_KEY=secret\n", encoding="utf-8")
    monkeypatch.setattr(keys, "_ROOT_ENV_PATH", env_path)
    monkeypatch.setattr(sys, "argv", ["whale-key.py", "clear"])
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    with patch.object(keys, "keyring") as mock_kr:
        keys.cmd_cli()
    mock_kr.delete_password.assert_called_once()
    # .env 的 LLM_API_KEY 行被删除
    assert "LLM_API_KEY" not in env_path.read_text(encoding="utf-8")


def test_env_write_key_empty_does_not_delete(monkeypatch, tmp_path):
    """_env_write_key('') 不应删除 .env 的 LLM_API_KEY 行（防误删）。"""
    import src.keys as keys
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_BASE_URL=x\nLLM_API_KEY=secret\nLLM_MODEL=m\n", encoding="utf-8")
    monkeypatch.setattr(keys, "_ROOT_ENV_PATH", env_path)
    # 空 key 调用 _env_write_key（内部保护：不应删）
    keys._env_write_key("")
    content = env_path.read_text(encoding="utf-8")
    assert "LLM_API_KEY=secret" in content, "空 key 不应删除 .env 的 key 行"
