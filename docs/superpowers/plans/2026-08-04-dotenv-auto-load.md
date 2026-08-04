# .env 自动加载（python-dotenv）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `python main.py` 无需预先 `source .env` 即可运行，由 `main.py` 启动时自动加载同目录 `.env`。

**Architecture:** 在 `main.py` 新增自包含函数 `load_env()`，用 `python-dotenv` 以显式路径（`Path(__file__).resolve().parent / ".env"`）、`override=False` 加载。`main()` 开头调用。硬依赖进 `requirements.txt`。未来多 Agent 时迁移到 `src/env.py`（见 spec 第 6 节）。

**Tech Stack:** Python 3.13、python-dotenv>=1.0、pytest。

## Global Constraints

- 禁止硬编码 key/路径（AGENTS.md A1）——`.env` 路径用 `Path(__file__)` 推导，不用字面量绝对路径。
- `override=False`——已导出的 env 优先，CI/手动 export 与测试 mock 不被覆盖。
- 不破坏现有 21 个测试（不回归）。
- 注释恰到好处（AGENTS.md A4）。
- 较大改动后即提交（AGENTS.md A3）。

---

### Task 1: 依赖 + `load_env()` + 测试（TDD）

**Files:**
- Modify: `explorer-agent/requirements.txt`
- Modify: `explorer-agent/main.py`
- Create: `explorer-agent/tests/test_main_env.py`

**Interfaces:**
- Produces: `main.load_env()` —— 无参，调用 `load_dotenv(Path(__file__).resolve().parent / ".env", override=False)`。`main()` 开头调用之。

- [ ] **Step 1: 加依赖到 requirements.txt**

在 `explorer-agent/requirements.txt` 末尾追加一行：

```
python-dotenv>=1.0
```

完整文件应为：
```
openai>=1.0
pyyaml>=6.0
httpx>=0.27
pytest>=8.0
python-dotenv>=1.0
```

- [ ] **Step 2: 安装依赖**

Run:
```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && pip install -r requirements.txt 2>&1 | tail -3
```
Expected: 出现 `Successfully installed python-dotenv-...`（或 `Requirement already satisfied`）。

- [ ] **Step 3: 写失败测试**

创建 `explorer-agent/tests/test_main_env.py`：

```python
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
```

> 说明：`conftest.py` 已把 `explorer-agent/` 加入 `sys.path`，故 `import main` 可用。`mock_env`（autouse）用 `monkeypatch.setenv` 注入假 env，与本测试无交集（本测试只 mock `load_dotenv`，不碰 env 变量）。

- [ ] **Step 4: 运行测试，确认失败（红）**

Run:
```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_main_env.py -v 2>&1 | tail -15
```
Expected: FAIL —— `AttributeError: module 'main' has no attribute 'load_env'`（或 `ImportError: cannot import name 'load_env'`）。

- [ ] **Step 5: 实现 `load_env()` 并在 `main()` 开头调用**

修改 `explorer-agent/main.py`。改后完整文件：

```python
# main.py
"""explorer-agent 入口。两种模式：--explore-only（爬虫委托）/ 直接目标（Agent 编排）。"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.harness import Harness
from src.agent_loop import AgentLoop
from src.llm.client import LLMClient


def load_env():
    """从 main.py 同目录的 .env 加载环境变量。已存在的 env 优先（override=False）。"""
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)


def main():
    load_env()
    args = sys.argv[1:]
    explore_only = "--explore-only" in args
    if explore_only:
        idx = args.index("--explore-only")
        url = args[idx + 1] if idx + 1 < len(args) else ""
        strategies_dir = os.environ.get("STRATEGIES_DIR", "")
        domain = url.split("//")[1].split("/")[0] if "//" in url else url
        strategy_path = f"{strategies_dir}/{domain}.json" if strategies_dir else "策略目录"
        goal = f"探索 {url} 的通知公告入口，生成爬取策略 JSON，写入 {strategy_path}。不要调用爬虫执行爬取。"
    else:
        goal = " ".join(args) or input("🎯 任务: ")

    harness = Harness.from_yaml("agent.yaml")
    llm = LLMClient()
    loop = AgentLoop(harness, llm)
    result = loop.run(goal)
    print(f"\n✅ 结果:\n{result}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 运行新测试，确认通过（绿）**

Run:
```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_main_env.py -v 2>&1 | tail -10
```
Expected: PASS（1 passed）。

- [ ] **Step 7: 运行全量测试，确认无回归**

Run:
```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest -q 2>&1 | tail -5
```
Expected: `22 passed`（原 21 + 新 1）。

- [ ] **Step 8: 提交**

```bash
cd /home/wangzhiheng/whaleU-crawler && git add explorer-agent/requirements.txt explorer-agent/main.py explorer-agent/tests/test_main_env.py && git commit -m "feat: auto-load .env in main.py via python-dotenv (override=False)"
```

---

### Task 2: 文档同步

**Files:**
- Modify: `explorer-agent/.env.example`
- Modify: `explorer-agent/MANUAL_CHECKS.md`
- Modify: `无关文档/AGENT_STRUCTURE.md`
- Modify: `AGENT_LOG.md`

- [ ] **Step 1: `.env.example` 顶部加自动加载说明**

在 `explorer-agent/.env.example` 第 2 行后插入一行注释。把：

```
# LLM 配置（CherryIN deepseek）— 复制为 .env 并填入真实 key
# 注意：值含特殊字符（如括号）时必须加双引号
```

改为：

```
# LLM 配置（CherryIN deepseek）— 复制为 .env 并填入真实 key
# 注意：值含特殊字符（如括号）时必须加双引号
# main.py 启动时自动加载本文件（python-dotenv），无需手动 source
```

- [ ] **Step 2: `MANUAL_CHECKS.md` 更新前置章节**

在 `explorer-agent/MANUAL_CHECKS.md` 中，把"重要"警告（原第 25 行）：

```
> **重要**：Python 不自动加载 .env（无 python-dotenv 依赖）。必须在运行 `python main.py` **之前**、**同一个终端**里执行 `source .env`，否则环境变量不生效。
```

改为：

```
> **说明**：`main.py` 启动时通过 python-dotenv 自动加载 `.env`，无需手动 `source`。`.env` 仍需存在并填入真实值。
```

并把方法 A 的步骤（原第 13-23 行）：

```
### 方法 A（推荐）：.env 文件

```bash
# 1. 复制模板并填入真实值（只需做一次）
cp .env.example .env
# 编辑 .env，填入你的 CherryIN key 和真实路径

# 2. 每次开新终端时，先加载 .env 再运行 Agent
cd /home/wangzhiheng/whaleU-crawler/explorer-agent
set -a && source .env && set +a
```
```

改为：

```
### 方法 A（推荐）：.env 文件

```bash
# 1. 复制模板并填入真实值（只需做一次）
cp .env.example .env
# 编辑 .env，填入你的 CherryIN key 和真实路径

# 2. 直接运行 Agent（main.py 自动加载 .env，无需 source）
cd /home/wangzhiheng/whaleU-crawler/explorer-agent
python main.py "探索 https://cs.nju.edu.cn/ 的通知公告入口，生成爬取策略"
```
```

> 三层验证命令保留不变（它用 `source .env` 验证内容正确性，仍有效）。

- [ ] **Step 3: `AGENT_STRUCTURE.md` 更新 main.py 条目**

在 `无关文档/AGENT_STRUCTURE.md` 中：

(a) 把第 306 行流程：

```
**流程**：解析参数 → 构造 goal → Harness.from_yaml → LLMClient → AgentLoop.run(goal) → 打印结果
```

改为：

```
**流程**：load_env()（自动加载 .env）→ 解析参数 → 构造 goal → Harness.from_yaml → LLMClient → AgentLoop.run(goal) → 打印结果
```

(b) 在第 306 行流程下方、`---` 之前，插入一段 `load_env()` 说明：

```

**`load_env()`**：`main()` 开头调用，用 `python-dotenv` 从 `main.py` 同目录的 `.env` 加载环境变量，`override=False`（已导出的 env 优先）。无需手动 `source .env`。未来多 Agent 时迁移到 `src/env.py`。
```

- [ ] **Step 4: `AGENT_LOG.md` 追加本次改动记录**

在 `AGENT_LOG.md` 末尾（最后一个 `---` 之后）追加新会话段：

```
## 2026-08-04 会话六：.env 自动加载（python-dotenv）

### [人] 指令
- 检查 1 因未 source .env 失败；要求加自动加载，并更新相关文档
- 后续将发展成多 Agent 协作系统，当前先按方案 1 实现 MVP

### [AI] brainstorm + spec
- 走 brainstorming skill，提 3 方案，采纳方案 1（main.py 内置 load_env + 硬依赖）
- spec 第 6 节记录多 Agent 迁移路径：出现第二个需独立加载 env 的入口时，提取 load_env 到 src/env.py
- spec 提交 0424ae8，用户复核通过

### [AI] 实现（TDD）
- requirements.txt 加 python-dotenv>=1.0
- main.py 加 load_env()（Path(__file__).resolve().parent/.env，override=False），main() 开头调用
- 新增 tests/test_main_env.py（mock load_dotenv，断言路径+override）
- 全量 22 passed（原 21 + 新 1），无回归

### [AI] 文档同步
- .env.example / MANUAL_CHECKS.md / AGENT_STRUCTURE.md / 本日志
- 去掉"必须同终端 source"警告，改为"自动加载"
```

- [ ] **Step 5: 提交**

```bash
cd /home/wangzhiheng/whaleU-crawler && git add explorer-agent/.env.example explorer-agent/MANUAL_CHECKS.md "无关文档/AGENT_STRUCTURE.md" AGENT_LOG.md && git commit -m "docs: reflect .env auto-load in .env.example/MANUAL_CHECKS/AGENT_STRUCTURE/AGENT_LOG"
```

---

## Self-Review（计划自审）

**1. Spec 覆盖：**
- 第 2 节目标（自动加载/不破坏测试/不覆盖已导出/同步文档）→ Task 1 Step 5+6+7、Task 2 全覆盖 ✓
- 第 5 节决策（位置/路径/override/硬依赖/测试）→ Task 1 各 Step 对应 ✓
- 第 6 节多 Agent 迁移路径 → AGENT_STRUCTURE.md 与 AGENT_LOG.md 已写入 ✓
- 第 7 节受影响文档 7 项 → Task 2 Step 1-4 全覆盖（requirements/main/test 在 Task 1）✓
- 第 8 节验收（装依赖/单测通过/不回归/不报错/override 可选）→ Task 1 Step 2/6/7、手动验收由用户跑 ✓

**2. 占位符扫描：** 无 TBD/TODO，所有代码块均为完整可执行内容 ✓

**3. 类型/签名一致：** `load_env()` 无参无返回，Task 1 定义、Task 2 文档描述、测试调用均一致 ✓
