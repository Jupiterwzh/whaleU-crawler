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
