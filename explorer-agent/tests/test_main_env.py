"""load_env() 用正确路径、override=False 调用 load_dotenv。"""
import main


def test_load_env_passes_correct_env_path(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "load_dotenv", lambda *a, **kw: calls.append((a, kw)))
    main.load_env()
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert str(args[0]).endswith("/.env")
    assert kwargs["override"] is False
