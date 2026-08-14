#!/usr/bin/env python3
"""whale-key — 凭据管理命令（根目录入口）。

在项目根目录运行，无需 cd 进 Agent 目录：
    python whale-key.py set      # 引导隐藏录入 key，写入根 .env
    python whale-key.py get      # 查看状态（只显示长度，不回显明文）
    python whale-key.py clear    # 清除 key
    python whale-key.py has      # 是否已配置

等价于在任一 Agent 目录执行 `python -m src.keys <cmd>`。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "explorer-agent"))

from src.keys import cmd_cli


if __name__ == "__main__":
    cmd_cli()
