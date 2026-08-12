"""凭据安全存储：操作系统钥匙串（keyring）+ 隐藏录入。

优先顺序：环境变量 LLM_API_KEY → keyring 钥匙串 → 引导录入（getpass 隐藏）后存钥匙串。
"""
import os
import sys
import getpass

import keyring

_SERVICE = "whalequery"
_ACCOUNT = "cherryin_api_key"


def get_key() -> str:
    """返回 key。优先 env，其次 keyring。无则返回空。"""
    key = os.environ.get("LLM_API_KEY", "")
    if key:
        return key
    try:
        return keyring.get_password(_SERVICE, _ACCOUNT) or ""
    except Exception:
        return ""


def set_key(key: str):
    """把 key 存进钥匙串。后端不可用时给出提示（Docker/Linux 无 keyring 后端场景）。"""
    try:
        keyring.set_password(_SERVICE, _ACCOUNT, key)
    except Exception as e:
        print(f"⚠️ 钥匙串不可用（{e}），key 未持久化。请改用环境变量 LLM_API_KEY。")


def clear_key():
    """从钥匙串清除 key。"""
    try:
        keyring.delete_password(_SERVICE, _ACCOUNT)
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception:
        pass


def has_key() -> bool:
    return bool(get_key())


def prompt_and_store() -> str:
    """引导用户隐藏录入 key 并存入钥匙串。返回 key 值。"""
    key = getpass.getpass("🔑 请输入 CherryIN API Key（输入不回显）: ").strip()
    if not key:
        print("未输入，退出。")
        sys.exit(1)
    set_key(key)
    print("✅ 已安全存入系统钥匙串（查看/更新/清除：whale-key 命令）")
    return key


def ensure_key() -> str:
    """确保有 key：env/keyring 已有则用，否则引导录入。"""
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
        print("✅ 已清除钥匙串中的 key")
    elif cmd == "has":
        print("true" if has_key() else "false")
    else:
        print(__doc__)
