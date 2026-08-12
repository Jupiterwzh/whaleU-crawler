"""内建工具：读写文件。"""
from pathlib import Path

from .registry import Tool


def _read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _write_file(path: str, content: str) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"已写入 {path}（{len(content)} 字符）"


def make_file_tools(strategies_dir: str) -> list[Tool]:
    """返回 read_file / write_file 两个工具。"""
    return [
        Tool(
            name="read_file",
            description="读取指定路径的文件内容。",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "文件绝对路径"}},
                "required": ["path"],
            },
            handler=_read_file,
            require_approval=False,
        ),
        Tool(
            name="write_file",
            description="写入文件。用于保存爬取策略 JSON。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目标文件绝对路径"},
                    "content": {"type": "string", "description": "文件内容"},
                },
                "required": ["path", "content"],
            },
            handler=_write_file,
            require_approval=True,
        ),
    ]
