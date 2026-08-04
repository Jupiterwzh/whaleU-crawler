# 设计：.env 自动加载（python-dotenv）

> 日期：2026-08-04
> 状态：已批准（MVP）
> 关联：explorer-agent/main.py、requirements.txt、MANUAL_CHECKS.md、AGENT_STRUCTURE.md

---

## 1. 背景与问题

`explorer-agent` 的 `LLMClient` 直接读 `os.environ`，但 Python 不自动加载 `.env`（项目未装 python-dotenv）。当前要求用户每次开新终端都先执行：

```bash
set -a && source .env && set +a
```

否则 `python main.py` 报 `RuntimeError: LLM_API_KEY 环境变量未设置`。

**痛点**：
- 每次开终端都要手动 source，易忘（已踩坑：会话五检查 1 即因此失败）。
- `set -a` 的原理不直观，用户难理解为何裸 `source` 无效（因 `.env` 用裸 `VAR="value"` 而非 `export VAR=`，赋值不进环境，子进程看不到）。
- 与"直接 `python main.py` 就能跑"的预期不符。

## 2. 目标

- `python main.py ...` 无需预先 `source .env` 即可运行（`.env` 自动加载）。
- 不破坏现有测试（`conftest.py` 的 `mock_env` 用 `monkeypatch.setenv` 注入假 env，须保持优先）。
- 不破坏 CI/手动 export 场景（已导出的真实 env 不被 `.env` 覆盖）。
- 同步更新相关说明文档。

## 3. 非目标（Out of Scope）

- 不引入多 Agent / SubAgent 架构（按 AGENTS.md F18，MVP 不含）。
- 不做 `.env` 校验、schema、类型转换（仅加载原始字符串）。
- 不为绕过 `main.py` 直接 `import LLMClient` 的用法提供自动加载（本项目无此用法）。

## 4. 方案选择

### 方案 1（采纳）：`main.py` 内置 `load_env()` + 硬依赖

- `requirements.txt` 增加 `python-dotenv>=1.0`
- `main.py` 新增 `load_env()` 函数：
  ```python
  from pathlib import Path
  from dotenv import load_dotenv

  def load_env():
      """从 main.py 同目录的 .env 加载环境变量。已存在的 env 优先（override=False）。"""
      load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
  ```
- `main()` 函数体开头调用 `load_env()`（非模块顶层，避免 import 副作用）。

### 方案 2（未采纳）：集中到 `src/env.py` 模块

新建 `src/env.py` 放 `load_env()`，所有入口 import。优点是可复用；缺点是对当前单入口规模过度。**留作多 Agent 时代的迁移目标**（见第 6 节）。

### 方案 3（未采纳）：软依赖 `try/except ImportError`

未装 dotenv 时静默回退手动 source。缺点：掩盖"忘装依赖"，与项目硬依赖风格不一致。

## 5. 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 加载位置 | `main()` 函数体开头 | 唯一入口；非模块顶层，避免 import 副作用与测试干扰 |
| `.env` 路径 | `Path(__file__).resolve().parent / ".env"` | 相对 `main.py`，不依赖 CWD，从任意目录跑都能找到 |
| override | `False` | 已导出的 env 优先：CI/手动 export 不被覆盖；测试 `mock_env` 的 `monkeypatch.setenv` 值也不被覆盖 |
| 依赖方式 | 硬依赖（进 requirements.txt） | 与 openai/pyyaml/httpx/pytest 风格一致；ImportError 比"静默回退"更易排查 |
| 测试 | 1 个单测：mock `load_dotenv`，断言 `load_env()` 传入正确路径 | 隔离、不触发真实 LLM；不测库本身 |

### 测试不干扰分析

`conftest.py` 的 `mock_env`（autouse）用 `monkeypatch.setenv` 在测试前注入假 env。`load_dotenv(override=False)` 见到已存在的变量会跳过，故真实 `.env` 的 key 不会泄漏进测试。且 `load_env()` 只在 `main()` 内调用，测试不调 `main()`，路径上无交集。

## 6. 多 Agent 时代的迁移路径（重要）

用户已明确：**后续将发展成多 Agent 协作系统**。本 MVP 选方案 1 不堵未来的路：

- `load_env()` 是自包含函数，迁移时只需：把它从 `main.py` 剪到 `src/env.py`，各 Agent 入口 `from src.env import load_env`。
- 一次剪切粘贴 + 改 import，零重写，低风险。
- 多 Agent 真正的难题是 Agent 间通信 / 状态共享 / 任务编排，与"env 怎么加载"无关——env 加载是 trivial 层，方案 1 不会成为瓶颈。
- 按 AGENTS.md F18，MVP 不含 SubAgent；"多 Agent"是未来方向，不影响当前选方案 1。

**迁移触发条件**：出现第二个需要独立加载 env 的入口时，即提取到 `src/env.py`。

## 7. 受影响文档

| 文档 | 改动 |
|------|------|
| `explorer-agent/requirements.txt` | 加 `python-dotenv>=1.0` |
| `explorer-agent/main.py` | 加 `load_env()` + 调用 |
| `explorer-agent/tests/test_main_env.py`（新） | 1 个单测 |
| `explorer-agent/MANUAL_CHECKS.md` | 前置章节：去掉"必须同终端 source"警告，改为"自动加载 .env，无需 source"；保留"三层验证"命令 |
| `无关文档/AGENT_STRUCTURE.md` | main.py 条目：补 `load_env()` 说明 |
| `AGENT_LOG.md` | 记录本次改动 |
| `explorer-agent/.env.example` | 顶部注释补一句"main.py 启动时自动加载，无需手动 source" |

## 8. 验收

- `pip install -r requirements.txt` 成功装上 python-dotenv。
- 新增单测通过；原 21 个测试仍全绿（不回归）。
- **不开新终端、不 source**，直接 `python main.py "探索 https://cs.nju.edu.cn/ ..."` 不再报 `LLM_API_KEY 环境变量未设置`（进入真实 LLM 调用阶段即算通过）。
- `override=False` 验证：先 `export LLM_API_KEY=manual-test`，再跑，确认手动值不被 `.env` 覆盖（可选）。
