"""load_env() 先读根 .env 再读自身 .env（自身覆盖根）。"""
import main


def test_load_env_reads_root_then_own_env(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(main, "load_dotenv", lambda *a, **kw: calls.append((a, kw)))
    main.load_env()
    # 应先读根 .env，再读自身 .env
    assert len(calls) == 2
    root_arg, root_kw = calls[0]
    own_arg, own_kw = calls[1]
    assert str(root_arg[0]).endswith("/.env")
    assert str(own_arg[0]).endswith("/.env")
    # 根 .env 路径是项目根；自身 .env 是 agent 目录
    assert str(own_arg[0]) != str(root_arg[0])
    assert own_kw["override"] is True
