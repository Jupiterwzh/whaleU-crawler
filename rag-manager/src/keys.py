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
_ACCOUNT = "llm_api_key"
_AGENT_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
# 根 .env 为集中配置主源；keys CLI 统一写根，各 Agent 继承
_ROOT_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def _env_key() -> str:
    """从 .env 文件读取 LLM_API_KEY；值若是 ${VAR} 引用则从环境变量展开。"""
    for env_path in (_AGENT_ENV_PATH, _ROOT_ENV_PATH):
        if not env_path.exists():
            continue
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("LLM_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if not val:
                        continue
                    # ${VAR} 引用 → 从环境变量展开
                    import re as _re
                    m = _re.fullmatch(r"\$\{(\w+)\}", val)
                    if m:
                        return os.environ.get(m.group(1), "")
                    return val
        except OSError:
            continue
    return ""


def _env_write_key(key: str):
    """把 LLM_API_KEY 写进根 .env（保留其他行）。

    防误删保护：key 为空时不删除 .env 的 LLM_API_KEY 行（避免误调清空真实 key）。
    """
    if not key:
        return
    _ROOT_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = _ROOT_ENV_PATH.read_text(encoding="utf-8").splitlines() if _ROOT_ENV_PATH.exists() else []
    new_lines = [l for l in lines if not l.strip().startswith("LLM_API_KEY=")]
    new_lines.append(f"LLM_API_KEY={key}")
    _ROOT_ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def get_key() -> str:
    """返回 key。优先 LLM_API_KEY env，其次 DEEPSEEK_API_KEY env，再次 keyring，最后 .env。无则空。"""
    key = os.environ.get("LLM_API_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", "")
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
    """清除 key：keyring 与 .env 都清（.env 显式删除 LLM_API_KEY 行，需二次确认）。"""
    try:
        keyring.delete_password(_SERVICE, _ACCOUNT)
    except Exception:
        pass
    # 显式删除 .env 的 LLM_API_KEY 行（不受 _env_write_key 空 key 保护限制）
    if _ROOT_ENV_PATH.exists():
        lines = _ROOT_ENV_PATH.read_text(encoding="utf-8").splitlines()
        new_lines = [l for l in lines if not l.strip().startswith("LLM_API_KEY=")]
        _ROOT_ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def has_key() -> bool:
    return bool(get_key())


def prompt_and_store() -> str:
    """引导用户隐藏录入 key 并存入 keyring/.env。返回 key 值。"""
    key = getpass.getpass("🔑 请输入 LLM API Key（输入不回显）: ").strip()
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
        confirm = input("⚠️ 将清除全部已存储的 key（钥匙串 + .env 的 LLM_API_KEY 行）。\n"
                         "清除后各 Agent 将无法调用 LLM，需重新配置。确定清除？(y/n): ").strip().lower()
        if confirm in ("y", "yes"):
            clear_key()
            print("✅ 已清除 key")
        else:
            print("已取消清除")
    elif cmd == "has":
        print("true" if has_key() else "false")
    else:
        print(__doc__)


if __name__ == "__main__":
    cmd_cli()
