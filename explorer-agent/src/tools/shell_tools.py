"""内建工具：执行 shell 命令（调爬虫/浏览器服务）。"""
import subprocess

from .registry import Tool


def _run_shell(cmd: str, timeout: float = 60.0) -> str:
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    out = proc.stdout
    if proc.stderr:
        out += f"\n[stderr]\n{proc.stderr}"
    return out


def make_shell_tools() -> list[Tool]:
    return [
        Tool(
            name="run_shell",
            description="执行 shell 命令。用于调用 JS 爬虫（node collector.js）或 NJU 浏览器服务。",
            parameters={
                "type": "object",
                "properties": {"cmd": {"type": "string", "description": "要执行的 shell 命令"}},
                "required": ["cmd"],
            },
            handler=_run_shell,
            require_approval=True,
        ),
    ]
