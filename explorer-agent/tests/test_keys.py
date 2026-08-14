# tests/test_keys.py
from unittest.mock import patch
import src.keys as keys


def test_get_key_env_priority(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "env-key-123")
    with patch.object(keys, "keyring") as mock_kr:
        assert keys.get_key() == "env-key-123"
        mock_kr.get_password.assert_not_called()


def test_get_key_keyring_fallback(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
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
