"""凭据安全存储：操作系统钥匙串（keyring）+ .env + 隐藏录入。

优先顺序：环境变量 LLM_API_KEY → keyring 钥匙串 → .env 文件 → 引导录入。
keyring 在无桌面后端（WSL/Docker）不可用时，自动降级到 .env 文件。
"""
import os
import sys
import getpass
from pathlib import Path

import keyring

_SERVICE = "whalequery"
_ACCOUNT = "cherryin_api_key"
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _env_key() -> str:
    """从 .env 文件读取 LLM_API_KEY（不做 ${} 展开，取字面值）。"""
    if not _ENV_PATH.exists():
        return ""
    try:
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("LLM_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                return val
    except OSError:
        return ""
    return ""


def _env_write_key(key: str):
    """把 LLM_API_KEY 写进 .env（保留其他行）；key 为空则移除该行。"""
    _ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = _ENV_PATH.read_text(encoding="utf-8").splitlines() if _ENV_PATH.exists() else []
    new_lines = [l for l in lines if not l.strip().startswith("LLM_API_KEY=")]
    if key:
        new_lines.append(f"LLM_API_KEY={key}")
    _ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def get_key() -> str:
    """返回 key。优先 env，其次 keyring，再次 .env。无则空。"""
    key = os.environ.get("LLM_API_KEY", "")
    if key:
        return key
    try:
        ring = keyring.get_password(_SERVICE, _ACCOUNT)
        if ring:
            return ring
    except Exception:
        pass
    return _env_key()


def set_key(key: str):
    """存 key。优先 keyring；后端不可用时写入 .env（降级）。"""
    try:
        keyring.set_password(_SERVICE, _ACCOUNT, key)
        return
    except Exception:
        pass
    _env_write_key(key)


def clear_key():
    """清除 key：keyring 与 .env 都清。"""
    try:
        keyring.delete_password(_SERVICE, _ACCOUNT)
    except Exception:
        pass
    _env_write_key("")


def has_key() -> bool:
    return bool(get_key())


def prompt_and_store() -> str:
    """引导用户隐藏录入 key 并存入 keyring/.env。返回 key 值。"""
    key = getpass.getpass("🔑 请输入 DeepSeek API Key（输入不回显）: ").strip()
    if not key:
        print("未输入，退出。")
        sys.exit(1)
    set_key(key)
    print("✅ 已安全存储（查看/更新/清除：python -m src.keys get/set/clear）")
    return key


def ensure_key() -> str:
    """确保有 key：env/keyring/.env 已有则用，否则引导录入。"""
    key = get_key()
    if key:
        return key
    return prompt_and_store()


def cmd_cli():
    """whale-key 命令：get / set / clear / has。"""
    args = sys.argv[1:]
    cmd = args[0] if args else "has"
    if cmd == "get":
        if has_key():
            print(f"✅ 已配置（{len(get_key())} 字符，不回显明文）")
        else:
            print("❌ 未配置")
    elif cmd == "set":
        prompt_and_store()
    elif cmd == "clear":
        clear_key()
        print("✅ 已清除 key")
    elif cmd == "has":
        print("true" if has_key() else "false")
    else:
        print(__doc__)


if __name__ == "__main__":
    cmd_cli()
