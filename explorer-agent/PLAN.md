# explorer-agent 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零搭建一个 Python 单 Agent（Harness Engineering），能探索 NJU 网站结构并生成爬取策略 JSON。

**Architecture:** LLM 只做一行任务决策，其余全是工程零件（Harness）。AgentLoop 三段式：上下文装配 → while 循环（LLM 决策→门控→工具分发→回灌）→ 收尾。爬虫保持 JS，Agent 通过 run_shell 调用。

**Tech Stack:** Python 3.13 / openai SDK（OpenAI 兼容，指向 CherryIN deepseek）/ pyyaml / httpx / pytest

## Global Constraints

- 绝不硬编码 key/路径：全部 `os.environ`，agent.yaml 用 `${VAR}` 占位
- Agent 架构严格按 `流程参考.md`/`教程.md`/`SPEC.md`，不偏离；接口不匹配时改爬虫不改 Agent
- 策略 JSON 必须匹配爬虫 v3 格式（`meta`/`entries`/`pagination`/`extraction`/`notes`）
- 策略写入 `crawler/data/strategies/{domain}.json`（路径走环境变量）
- LLM 端点：`https://open.cherryin.cc/v1`，模型 `deepseek/deepseek-v4-flash(free)`，key 走 `LLM_API_KEY`
- 不读 `.env` 文件内容；只通过 `os.environ` 读

---

## File Structure

| 文件 | 职责 |
|------|------|
| `explorer-agent/requirements.txt` | Python 依赖 |
| `explorer-agent/.env.example` | 环境变量模板（不含真实 key） |
| `explorer-agent/.gitignore` | 忽略 .env/traces/__pycache__ |
| `explorer-agent/agent.yaml` | 声明式总配置 |
| `explorer-agent/rules/AGENTS.md` | Agent 行为约束 |
| `explorer-agent/guardrails/policy.yaml` | 权限门控策略 |
| `explorer-agent/src/__init__.py` | 包标识 |
| `explorer-agent/src/llm/__init__.py` | 包标识 |
| `explorer-agent/src/llm/client.py` | OpenAI 兼容 LLM 客户端 |
| `explorer-agent/src/tools/__init__.py` | 包标识 |
| `explorer-agent/src/tools/registry.py` | Tool 类 + 注册表 |
| `explorer-agent/src/tools/file_tools.py` | read_file / write_file |
| `explorer-agent/src/tools/web_tools.py` | fetch_url |
| `explorer-agent/src/tools/shell_tools.py` | run_shell |
| `explorer-agent/src/guardrail.py` | Guardrail 门控 |
| `explorer-agent/src/tracer.py` | 轨迹记录 |
| `explorer-agent/src/harness.py` | Harness 装配 |
| `explorer-agent/src/agent_loop.py` | 核心循环 |
| `explorer-agent/main.py` | 入口（两种模式） |
| `explorer-agent/tests/conftest.py` | pytest 共享 fixture |
| `explorer-agent/tests/test_*.py` | 各组件测试 |

---

## Task 0: 项目初始化

**Files:**
- Create: `explorer-agent/requirements.txt`
- Create: `explorer-agent/.env.example`
- Create: `explorer-agent/.gitignore`
- Create: `explorer-agent/src/__init__.py`, `src/llm/__init__.py`, `src/tools/__init__.py`
- Create: `explorer-agent/tests/conftest.py`

- [ ] **Step 1: 写 requirements.txt**

```
openai>=1.0
pyyaml>=6.0
httpx>=0.27
pytest>=8.0
```

- [ ] **Step 2: 写 .env.example（模板，不含真实 key）**

```
# LLM 配置（CherryIN deepseek）
LLM_BASE_URL=https://open.cherryin.cc/v1
LLM_API_KEY=your-key-here
LLM_MODEL=deepseek/deepseek-v4-flash(free)

# 路径配置（绝不硬编码）
STRATEGIES_DIR=/home/wangzhiheng/whaleU-crawler/crawler/data/strategies
CRAWLER_SCRIPT=/home/wangzhiheng/whaleU-crawler/crawler/src/collectors/collector.js
NJU_BROWSER_DIR=/mnt/c/Users/wangzhiheng/Desktop/skills-nju-browser
```

- [ ] **Step 3: 写 .gitignore**

```
.env
__pycache__/
*.pyc
traces/
.pytest_cache/
```

- [ ] **Step 4: 建包标识文件**

`src/__init__.py`、`src/llm/__init__.py`、`src/tools/__init__.py` 各写一行注释即可：
```python
"""explorer-agent 源码包。"""
```

- [ ] **Step 5: 写 tests/conftest.py（共享 fixture）**

```python
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# 让 src 可导入
sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """每个测试都注入假环境变量，绝不依赖真实 key。"""
    monkeypatch.setenv("LLM_BASE_URL", "https://fake.example.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "fake-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("STRATEGIES_DIR", "/tmp/test-strategies")
    monkeypatch.setenv("CRAWLER_SCRIPT", "/tmp/fake-collector.js")
    monkeypatch.setenv("NJU_BROWSER_DIR", "/tmp/fake-browser")
```

- [ ] **Step 6: 安装依赖并验证**

Run: `cd explorer-agent && pip install -r requirements.txt && python -c "import openai, yaml, httpx; print('deps ok')"`
Expected: 输出 `deps ok`

- [ ] **Step 7: 初始化 git 并提交**

```bash
cd /home/wangzhiheng/whaleU-crawler
git init
git add explorer-agent
git commit -m "chore: init explorer-agent scaffold"
```

---

## Task 1: LLM 客户端

**Files:**
- Create: `explorer-agent/src/llm/client.py`
- Test: `explorer-agent/tests/test_llm_client.py`

**Interfaces:**
- Produces: `LLMClient` 类，方法 `chat(messages: list[dict], tools: list[dict] | None = None) -> dict`，返回 `{"text": str, "tool_calls": list[dict] | None}`。每个 tool_call 形如 `{"name": str, "arguments": dict}`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_llm_client.py
from unittest.mock import MagicMock, patch
from src.llm.client import LLMClient

def test_chat_returns_text_when_no_tool_calls():
    client = LLMClient()
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="完成", tool_calls=None))]
    with patch.object(client._client.chat.completions, "create", return_value=fake_resp):
        result = client.chat([{"role": "user", "content": "hi"}])
    assert result["text"] == "完成"
    assert result["tool_calls"] is None

def test_chat_parses_tool_calls():
    client = LLMClient()
    tc = MagicMock()
    tc.function.name = "fetch_url"
    tc.function.arguments = '{"url": "https://x"}'
    tc.id = "call_1"
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="", tool_calls=[tc]))]
    with patch.object(client._client.chat.completions, "create", return_value=fake_resp):
        result = client.chat([{"role": "user", "content": "go"}])
    assert result["tool_calls"] == [{"name": "fetch_url", "arguments": {"url": "https://x"}, "id": "call_1"}]
    assert result["text"] == ""

def test_chat_raises_on_missing_env(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY")
    import importlib
    import src.llm.client
    importlib.reload(src.llm.client)
    try:
        src.llm.client.LLMClient()
        assert False, "应抛错"
    except RuntimeError:
        pass
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd explorer-agent && python -m pytest tests/test_llm_client.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**

```python
# src/llm/client.py
"""OpenAI 兼容 LLM 客户端。绝不硬编码 key/端点。"""
import json
import os

from openai import OpenAI


class LLMClient:
    def __init__(self):
        base_url = os.environ.get("LLM_BASE_URL")
        api_key = os.environ.get("LLM_API_KEY")
        if not api_key:
            raise RuntimeError("LLM_API_KEY 环境变量未设置")
        self.model = os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-flash(free)")
        self._client = OpenAI(base_url=base_url, api_key=api_key)

    def chat(self, messages, tools=None):
        """返回 {"text": str, "tool_calls": list | None}。"""
        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                {
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                    "id": tc.id,
                }
                for tc in msg.tool_calls
            ]
        return {"text": msg.content or "", "tool_calls": tool_calls}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_llm_client.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add explorer-agent/src/llm/ explorer-agent/tests/test_llm_client.py
git commit -m "feat: add LLM client with OpenAI-compatible endpoint"
```

---

## Task 2: Tool 类与注册表

**Files:**
- Create: `explorer-agent/src/tools/registry.py`
- Test: `explorer-agent/tests/test_tools.py`

**Interfaces:**
- Produces: `Tool` dataclass（`name, description, parameters, handler`）；`ToolRegistry` 类（`register(tool)`, `get(name)`, `to_openai_schemas()`, `call(name, args)`）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_tools.py
from src.tools.registry import Tool, ToolRegistry

def _dummy_handler(path):
    return f"content of {path}"

def test_tool_to_openai_schema():
    t = Tool(name="read_file", description="读文件", parameters={"type": "object", "properties": {}}, handler=_dummy_handler)
    schema = t.to_openai_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "read_file"
    assert schema["function"]["description"] == "读文件"

def test_registry_register_and_call():
    reg = ToolRegistry()
    reg.register(Tool("read_file", "读文件", {"type": "object", "properties": {}}, _dummy_handler))
    result = reg.call("read_file", {"path": "a.txt"})
    assert result == "content of a.txt"

def test_registry_call_unknown_raises():
    import pytest
    reg = ToolRegistry()
    with pytest.raises(KeyError):
        reg.call("nope", {})
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_tools.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
# src/tools/registry.py
"""工具标准接口与注册表。"""
from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable
    require_approval: bool = False

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def to_openai_schemas(self) -> list[dict]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def call(self, name: str, args: dict) -> str:
        if name not in self._tools:
            raise KeyError(f"工具不存在: {name}")
        return str(self._tools[name].handler(**args))
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_tools.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add explorer-agent/src/tools/registry.py explorer-agent/tests/test_tools.py
git commit -m "feat: add Tool class and ToolRegistry"
```

---

## Task 3: file_tools（read_file / write_file）

**Files:**
- Create: `explorer-agent/src/tools/file_tools.py`
- Modify: `explorer-agent/tests/test_tools.py`（追加测试）

**Interfaces:**
- Produces: `make_file_tools(strategies_dir: str) -> list[Tool]`，返回 read_file 和 write_file 两个 Tool。

- [ ] **Step 1: 追加失败测试**

```python
# 追加到 tests/test_tools.py
import os
from src.tools.file_tools import make_file_tools

def test_read_file(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    tools = make_file_tools(str(tmp_path))
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)
    assert reg.call("read_file", {"path": str(f)}) == "hello"

def test_write_file(tmp_path):
    tools = make_file_tools(str(tmp_path))
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)
    out = tmp_path / "out.txt"
    reg.call("write_file", {"path": str(out), "content": "data"})
    assert out.read_text() == "data"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_tools.py -v`
Expected: FAIL（file_tools 不存在）

- [ ] **Step 3: 写实现**

```python
# src/tools/file_tools.py
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
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_tools.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add explorer-agent/src/tools/file_tools.py explorer-agent/tests/test_tools.py
git commit -m "feat: add read_file/write_file tools"
```

---

## Task 4: web_tools（fetch_url）

**Files:**
- Create: `explorer-agent/src/tools/web_tools.py`
- Modify: `explorer-agent/tests/test_tools.py`

- [ ] **Step 1: 追加失败测试**

```python
# 追加到 tests/test_tools.py
from unittest.mock import patch, MagicMock
from src.tools.web_tools import make_web_tools

def test_fetch_url():
    tools = make_web_tools()
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)
    fake = MagicMock()
    fake.status_code = 200
    fake.text = "<html>hi</html>"
    fake.raise_for_status = MagicMock()
    with patch("src.tools.web_tools.httpx.get", return_value=fake):
        result = reg.call("fetch_url", {"url": "https://x"})
    assert result == "<html>hi</html>"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_tools.py::test_fetch_url -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
# src/tools/web_tools.py
"""内建工具：抓取页面 HTML。"""
import httpx

from .registry import Tool


def _fetch_url(url: str, timeout: float = 15.0) -> str:
    resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                     headers={"User-Agent": "Mozilla/5.0 (compatible; explorer-agent/0.1)"})
    resp.raise_for_status()
    return resp.text


def make_web_tools() -> list[Tool]:
    return [
        Tool(
            name="fetch_url",
            description="抓取指定 URL 的页面 HTML 内容。用于探索网站结构。",
            parameters={
                "type": "object",
                "properties": {"url": {"type": "string", "description": "要抓取的页面 URL"}},
                "required": ["url"],
            },
            handler=_fetch_url,
            require_approval=False,
        ),
    ]
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_tools.py -v`
Expected: 6 passed

- [ ] **Step 5: 提交**

```bash
git add explorer-agent/src/tools/web_tools.py explorer-agent/tests/test_tools.py
git commit -m "feat: add fetch_url tool"
```

---

## Task 5: shell_tools（run_shell）

**Files:**
- Create: `explorer-agent/src/tools/shell_tools.py`
- Modify: `explorer-agent/tests/test_tools.py`

- [ ] **Step 1: 追加失败测试**

```python
# 追加到 tests/test_tools.py
from src.tools.shell_tools import make_shell_tools

def test_run_shell():
    tools = make_shell_tools()
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)
    result = reg.call("run_shell", {"cmd": "echo hello"})
    assert "hello" in result
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_tools.py::test_run_shell -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
# src/tools/shell_tools.py
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
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_tools.py -v`
Expected: 7 passed

- [ ] **Step 5: 提交**

```bash
git add explorer-agent/src/tools/shell_tools.py explorer-agent/tests/test_tools.py
git commit -m "feat: add run_shell tool"
```

---

## Task 6: Guardrail 门控

**Files:**
- Create: `explorer-agent/guardrails/policy.yaml`
- Create: `explorer-agent/src/guardrail.py`
- Test: `explorer-agent/tests/test_guardrail.py`

**Interfaces:**
- Produces: `Guardrail.from_yaml(path) -> Guardrail`；`allow(action: dict) -> tuple[bool, str]`。action 形如 `{"tool": "run_shell", "args": {"cmd": "rm -rf /"}}`。

- [ ] **Step 1: 写 policy.yaml**

```yaml
# guardrails/policy.yaml
rules:
  - pattern: "rm -rf"
    action: deny
    reason: "禁止递归删除"
  - tools: ["run_shell"]
    pattern: "sudo"
    action: ask_user
    reason: "sudo 操作需确认"
  - tools: ["run_shell"]
    pattern: "rm "
    action: ask_user
    reason: "删除操作需确认"
  - tools: ["write_file"]
    action: ask_user
    reason: "写文件需确认"
  - tools: ["fetch_url", "read_file"]
    action: allow
```

- [ ] **Step 2: 写失败测试**

```python
# tests/test_guardrail.py
from src.guardrail import Guardrail

def test_deny_rm_rf():
    g = Guardrail.from_yaml("guardrails/policy.yaml")
    ok, reason = g.allow({"tool": "run_shell", "args": {"cmd": "rm -rf /"}})
    assert ok is False
    assert "递归删除" in reason

def test_allow_fetch_url():
    g = Guardrail.from_yaml("guardrails/policy.yaml")
    ok, _ = g.allow({"tool": "fetch_url", "args": {"url": "https://x"}})
    assert ok is True

def test_ask_user_write_file(monkeypatch):
    g = Guardrail.from_yaml("guardrails/policy.yaml")
    monkeypatch.setattr("builtins.input", lambda _: "y")
    ok, reason = g.allow({"tool": "write_file", "args": {"path": "/tmp/x"}})
    assert ok is True
    assert "确认" in reason
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest tests/test_guardrail.py -v`
Expected: FAIL

- [ ] **Step 4: 写实现**

```python
# src/guardrail.py
"""权限门控：危险动作拦截。"""
import yaml


class Guardrail:
    def __init__(self, rules: list[dict]):
        self.rules = rules

    @classmethod
    def from_yaml(cls, path: str) -> "Guardrail":
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(data.get("rules", []))

    def allow(self, action: dict) -> tuple[bool, str]:
        tool = action.get("tool", "")
        args = action.get("args", {})
        args_text = " ".join(str(v) for v in args.values())
        for rule in self.rules:
            if rule.get("tools") and tool not in rule["tools"]:
                continue
            pat = rule.get("pattern")
            if pat and pat not in args_text:
                continue
            verdict = rule["action"]
            reason = rule.get("reason", "")
            if verdict == "deny":
                return False, f"动作被拒绝: {reason}"
            if verdict == "ask_user":
                ans = input(f"⚠️ {reason}。允许吗? (y/n): ")
                if ans.lower() == "y":
                    return True, f"用户批准: {reason}"
                return False, f"用户拒绝: {reason}"
            return True, ""
        return True, ""
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_guardrail.py -v`
Expected: 3 passed

- [ ] **Step 6: 提交**

```bash
git add explorer-agent/guardrails/ explorer-agent/src/guardrail.py explorer-agent/tests/test_guardrail.py
git commit -m "feat: add Guardrail with policy.yaml"
```

---

## Task 7: Tracer 轨迹记录

**Files:**
- Create: `explorer-agent/src/tracer.py`
- Test: `explorer-agent/tests/test_tracer.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_tracer.py
import json
from pathlib import Path
from src.tracer import Tracer

def test_record_and_flush(tmp_path):
    t = Tracer(output_dir=str(tmp_path))
    t.record(step=1, text="思考", action={"type": "call_tool", "tool": "fetch_url"}, observation="<html>")
    t.flush()
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").strip().split("\n")
    rec = json.loads(lines[0])
    assert rec["step"] == 1
    assert rec["action"]["tool"] == "fetch_url"
    assert rec["observation"] == "<html>"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_tracer.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
# src/tracer.py
"""轨迹记录：每轮决策+观察，会话末落盘。"""
import json
import time
from pathlib import Path


class Tracer:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.trace_id = f"trace-{int(time.time())}"
        self._records: list[dict] = []
        self._start = time.time()

    def record(self, step: int, text: str, action: dict, observation: str = ""):
        self._records.append({
            "trace_id": self.trace_id,
            "step": step,
            "timestamp": time.time() - self._start,
            "text": text,
            "action": action,
            "observation": observation,
        })

    def flush(self):
        path = self.output_dir / f"{self.trace_id}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for r in self._records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"📊 轨迹已保存: {path} ({len(self._records)} 步)")
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_tracer.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add explorer-agent/src/tracer.py explorer-agent/tests/test_tracer.py
git commit -m "feat: add Tracer"
```

---

## Task 8: Harness 装配 + agent.yaml + rules

**Files:**
- Create: `explorer-agent/agent.yaml`
- Create: `explorer-agent/rules/AGENTS.md`
- Create: `explorer-agent/src/harness.py`
- Test: `explorer-agent/tests/test_harness.py`

**Interfaces:**
- Consumes: `LLMClient`, `ToolRegistry`, `make_file_tools/make_web_tools/make_shell_tools`, `Guardrail`, `Tracer`
- Produces: `Harness.from_yaml(path) -> Harness`，属性 `system_prompt/rules/tools/guardrail/tracer/config`

- [ ] **Step 1: 写 rules/AGENTS.md**

```markdown
# explorer-agent 行为约束

- 你是南京大学网站探索 Agent，职责：分析网站结构，找出通知公告列表页入口，生成爬取策略。
- 优先用 fetch_url 抓取页面，分析 HTML 后用 write_file 保存策略 JSON。
- 策略 JSON 必须含 meta/entries/pagination/extraction/notes 字段，entries 每项含 name/url/type/paginationType。
- 不确定时多抓几个候选子页验证，不要猜测。
- 完成后停止（不再调用工具即表示 done）。
- 回复简洁，中文。
```

- [ ] **Step 2: 写 agent.yaml**

```yaml
agent:
  name: "explorer-agent"
  model: "${LLM_MODEL}"
  max_steps: 30

llm:
  base_url: "${LLM_BASE_URL}"
  api_key: "${LLM_API_KEY}"

rules:
  - path: "./rules/AGENTS.md"

tools:
  builtin:
    - name: "fetch_url"
      module: "src.tools.web_tools"
      factory: "make_web_tools"
    - name: "read_file"
      module: "src.tools.file_tools"
      factory: "make_file_tools"
    - name: "write_file"
      module: "src.tools.file_tools"
      factory: "make_file_tools"
      require_approval: true
    - name: "run_shell"
      module: "src.tools.shell_tools"
      factory: "make_shell_tools"
      require_approval: true

guardrail:
  policy: "./guardrails/policy.yaml"

tracer:
  output: "./traces/"

paths:
  strategies_dir: "${STRATEGIES_DIR}"
  crawler_script: "${CRAWLER_SCRIPT}"
  nju_browser: "${NJU_BROWSER_DIR}"
```

- [ ] **Step 3: 写失败测试**

```python
# tests/test_harness.py
import os
from src.harness import Harness

def test_from_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(os.path.dirname(__file__) + "/..")
    h = Harness.from_yaml("agent.yaml")
    assert "explorer-agent" in h.system_prompt or "探索" in h.rules
    assert "fetch_url" in h.tools.names()
    assert "write_file" in h.tools.names()
    assert "run_shell" in h.tools.names()
    assert h.guardrail is not None
    assert h.tracer is not None
    assert h.config["agent"]["name"] == "explorer-agent"
```

- [ ] **Step 4: 运行确认失败**

Run: `python -m pytest tests/test_harness.py -v`
Expected: FAIL

- [ ] **Step 5: 写实现**

```python
# src/harness.py
"""Harness：从 agent.yaml 装配所有零件。"""
import importlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .guardrail import Guardrail
from .tools.registry import ToolRegistry
from .tracer import Tracer


def _resolve_env(value):
    """把 ${VAR} 替换为环境变量值。"""
    if isinstance(value, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(v) for v in value]
    return value


@dataclass
class Harness:
    system_prompt: str
    rules: str
    tools: ToolRegistry
    guardrail: Guardrail
    tracer: Tracer
    config: dict

    @classmethod
    def from_yaml(cls, path: str) -> "Harness":
        base = Path(path).resolve().parent
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        cfg = _resolve_env(cfg)

        # 规则
        rules_text = ""
        for r in cfg.get("rules", []):
            rules_text += (base / r["path"]).read_text(encoding="utf-8") + "\n"

        # 工具
        reg = ToolRegistry()
        paths = cfg.get("paths", {})
        for t in cfg["tools"]["builtin"]:
            mod = importlib.import_module(t["module"])
            factory = getattr(mod, t["factory"])
            tools = factory(strategies_dir=paths.get("strategies_dir", ".")) if t["factory"] == "make_file_tools" else factory()
            for tool in tools:
                if tool.name == t["name"]:
                    if t.get("require_approval"):
                        tool.require_approval = True
                    reg.register(tool)

        # 门控
        guardrail = Guardrail.from_yaml(str(base / cfg["guardrail"]["policy"]))

        # 轨迹
        tracer = Tracer(output_dir=str(base / cfg["tracer"]["output"]))

        system_prompt = f"你是 {cfg['agent']['name']}，一个南京大学网站探索 Agent。"

        return cls(system_prompt=system_prompt, rules=rules_text, tools=reg,
                   guardrail=guardrail, tracer=tracer, config=cfg)
```

- [ ] **Step 6: 运行确认通过**

Run: `python -m pytest tests/test_harness.py -v`
Expected: 1 passed

- [ ] **Step 7: 提交**

```bash
git add explorer-agent/agent.yaml explorer-agent/rules/ explorer-agent/src/harness.py explorer-agent/tests/test_harness.py
git commit -m "feat: add Harness.from_yaml assembly"
```

---

## Task 9: AgentLoop 核心循环

**Files:**
- Create: `explorer-agent/src/agent_loop.py`
- Test: `explorer-agent/tests/test_agent_loop.py`

**Interfaces:**
- Consumes: `Harness`, `LLMClient`
- Produces: `AgentLoop(harness, llm).run(goal: str) -> str`

- [ ] **Step 1: 写失败测试（mock LLM 返回固定动作序列）**

```python
# tests/test_agent_loop.py
from unittest.mock import MagicMock
from src.agent_loop import AgentLoop

def _make_harness(tmp_path):
    from src.harness import Harness
    return Harness.from_yaml("agent.yaml")

def test_loop_done_immediately(tmp_path, monkeypatch):
    import os
    monkeypatch.chdir(os.path.dirname(__file__) + "/..")
    h = _make_harness(tmp_path)
    llm = MagicMock()
    # 第一次：无 tool_calls → done
    llm.chat.return_value = {"text": "已完成", "tool_calls": None}
    loop = AgentLoop(h, llm)
    result = loop.run("测试任务")
    assert result == "已完成"

def test_loop_calls_tool_then_done(tmp_path, monkeypatch):
    import os
    monkeypatch.chdir(os.path.dirname(__file__) + "/..")
    h = _make_harness(tmp_path)
    llm = MagicMock()
    llm.chat.side_effect = [
        {"text": "抓页面", "tool_calls": [{"name": "fetch_url", "arguments": {"url": "https://x"}, "id": "1"}]},
        {"text": "完成", "tool_calls": None},
    ]
    # mock fetch_url 工具
    h.tools.get("fetch_url").handler = MagicMock(return_value="<html>")
    loop = AgentLoop(h, llm)
    result = loop.run("抓 https://x")
    assert result == "完成"
    assert llm.chat.call_count == 2
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_agent_loop.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
# src/agent_loop.py
"""Agent 核心循环。LLM 只占一行决策，其余全是工程。"""
from .llm.client import LLMClient


class AgentLoop:
    def __init__(self, harness, llm: LLMClient):
        self.H = harness
        self.llm = llm

    def run(self, goal: str) -> str:
        H = self.H
        # ① 上下文装配
        context = [
            {"role": "system", "content": H.system_prompt},
            {"role": "system", "content": H.rules},
            {"role": "user", "content": goal},
        ]
        max_steps = H.config["agent"].get("max_steps", 30)
        # ② 主循环
        for step in range(1, max_steps + 1):
            tools_schema = H.tools.to_openai_schemas() or None
            resp = self.llm.chat(context, tools=tools_schema)
            text = resp["text"]
            tool_calls = resp.get("tool_calls")
            H.tracer.record(step, text, {"tool_calls": tool_calls})

            if not tool_calls:
                # 无工具调用即停
                H.tracer.flush()
                return text

            # 处理每个 tool_call
            for tc in tool_calls:
                action = {"tool": tc["name"], "args": tc["arguments"]}
                # 门控
                ok, reason = H.guardrail.allow(action)
                if not ok:
                    context.append({"role": "assistant", "content": text})
                    context.append({"role": "user", "content": f"动作被拦截: {reason}"})
                    H.tracer.record(step, "", action, f"GUARDRAIL_DENY: {reason}")
                    continue
                # 执行
                try:
                    result = H.tools.call(tc["name"], tc["arguments"])
                except Exception as e:
                    result = f"工具失败: {e}"
                context.append({"role": "assistant", "content": text})
                context.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                H.tracer.record(step, "", action, result)
        # ③ 收尾（步数上限）
        H.tracer.flush()
        return "任务未完成（达到步数上限）"
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_agent_loop.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add explorer-agent/src/agent_loop.py explorer-agent/tests/test_agent_loop.py
git commit -m "feat: add AgentLoop core loop"
```

---

## Task 10: main.py 入口（两种模式）

**Files:**
- Create: `explorer-agent/main.py`
- Test: `explorer-agent/tests/test_main.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_main.py
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

def test_main_explore_only(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(Path(__file__).parent)
    with patch("src.agent_loop.AgentLoop.run", return_value="已生成策略"):
        sys.argv = ["main.py", "--explore-only", "https://cs.nju.edu.cn/"]
        import main
        main.main()
    out = capsys.readouterr().out
    assert "已生成策略" in out

def test_main_goal_arg(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(Path(__file__).parent)
    with patch("src.agent_loop.AgentLoop.run", return_value="完成"):
        sys.argv = ["main.py", "探索 cs.nju.edu.cn"]
        import main
        main.main()
    out = capsys.readouterr().out
    assert "完成" in out
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL

- [ ] **Step 3: 写实现**

```python
# main.py
"""explorer-agent 入口。两种模式：--explore-only（爬虫委托）/ 直接目标（Agent 编排）。"""
import sys

from src.harness import Harness
from src.agent_loop import AgentLoop
from src.llm.client import LLMClient


def main():
    args = sys.argv[1:]
    explore_only = "--explore-only" in args
    if explore_only:
        idx = args.index("--explore-only")
        url = args[idx + 1] if idx + 1 < len(args) else ""
        goal = f"探索 {url} 的通知公告入口，生成爬取策略 JSON 写入策略目录。不要调用爬虫执行爬取。"
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

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_main.py -v`
Expected: 2 passed

- [ ] **Step 5: 全量测试**

Run: `python -m pytest tests/ -v`
Expected: 全部 passed

- [ ] **Step 6: 提交**

```bash
git add explorer-agent/main.py explorer-agent/tests/test_main.py
git commit -m "feat: add main.py entry with two modes"
```

---

## Task 11: 爬虫适配（collector.js --explore-only 委托）

**Files:**
- Modify: `crawler/src/collectors/collector.js`（`--site` 分支：无策略时调 `python main.py --explore-only`）

**说明：** 这是改爬虫适配 Agent（符合 SPEC 适配原则）。原逻辑无策略时调 `exploreSiteSimple`（依赖 site-explorer.js + llm.js），改为调 Python Agent。

- [ ] **Step 1: 找到 collector.js 中 `--site` 无策略的分支**

Run: `grep -n "exploreSiteSimple\|无策略\|未找到策略" crawler/src/collectors/collector.js`
定位 `--site` 分支里 `exploreSiteSimple(rootUrl, { forceStrategy })` 调用处。

- [ ] **Step 2: 改为调用 Python Agent**

把 `const result = await exploreSiteSimple(rootUrl, { forceStrategy });` 这段替换为调用 Agent 子进程：

```javascript
// 无策略 → 委托 Python Agent 生成策略（--explore-only，不回调爬虫）
const { spawnSync } = require('child_process');
const agentScript = process.env.EXPLORER_AGENT_MAIN || path.resolve(__dirname, '..', '..', '..', 'explorer-agent', 'main.py');
console.log(`\n== 委托 explorer-agent 生成策略: ${domain} ==`);
const py = spawnSync('python', [agentScript, '--explore-only', rootUrl], {
  encoding: 'utf8',
  timeout: 120000,
  env: { ...process.env, STRATEGIES_DIR: path.resolve(__dirname, '..', '..', 'data', 'strategies') },
});
console.log(py.stdout);
if (py.stderr) console.error('[Agent stderr]', py.stderr);
// Agent 已写策略文件，重新加载
const existing = getStrategy(domain);
if (existing) {
  console.log(`\n== 使用 Agent 生成的策略爬取 ${domain} ==`);
  for (const entry of existing.entries || []) {
    if (entry.url) await crawlNotices(entry.url, { maxDays, maxPages });
  }
  return;
}
console.error('[Agent] 未生成策略，回退到启发式');
await crawlSite(rootUrl, { maxDays, maxPages, outputFile, forceStrategy: true });
return;
```

- [ ] **Step 3: 语法检查**

Run: `node --check crawler/src/collectors/collector.js`
Expected: 无输出（OK）

- [ ] **Step 4: 提交（在 crawler 的 git 仓库）**

```bash
cd crawler
git add src/collectors/collector.js
git commit -m "feat: delegate to explorer-agent when no strategy (--site)"
cd ..
```

---

## Task 12: 验收（对 cs.nju.edu.cn 跑通）

**Files:** 无（运行验证）

- [ ] **Step 1: 配置环境变量**

```bash
export LLM_BASE_URL=https://open.cherryin.cc/v1
export LLM_API_KEY=$CHERRYIN_API_KEY
export LLM_MODEL=deepseek/deepseek-v4-flash(free)
export STRATEGIES_DIR=/home/wangzhiheng/whaleU-crawler/crawler/data/strategies
export CRAWLER_SCRIPT=/home/wangzhiheng/whaleU-crawler/crawler/src/collectors/collector.js
```

- [ ] **Step 2: 模式 B 验收（Agent 入口）**

Run: `cd explorer-agent && python main.py "探索 https://cs.nju.edu.cn/ 的通知公告入口，生成策略"`
Expected: Agent 自主 fetch 首页+子页 → LLM 分析 → 写出 `crawler/data/strategies/cs.nju.edu.cn.json` → 报告完成。检查 `traces/` 有 jsonl 轨迹。

- [ ] **Step 3: 验证策略可用**

Run: `node crawler/src/collectors/collector.js --site https://cs.nju.edu.cn/ --days 365 --max-pages 2`
Expected: 爬虫用 Agent 生成的策略爬取到通知。

- [ ] **Step 4: 模式 A 验收（爬虫入口委托）**

先删除策略：`mv crawler/data/strategies/cs.nju.edu.cn.json /tmp/opencode/cs-strat.bak`
Run: `node crawler/src/collectors/collector.js --site https://cs.nju.edu.cn/ --days 365 --max-pages 2`
Expected: 爬虫检测无策略 → 调 `python main.py --explore-only` → Agent 生成策略 → 爬虫继续爬取。

- [ ] **Step 5: 门控验收**

Run: `cd explorer-agent && python main.py "用 run_shell 执行 rm -rf /tmp/test"`
Expected: Guardrail 拦截 `rm -rf`，回灌原因，Agent 不执行删除。

- [ ] **Step 6: 记录验收结果到 AGENT_LOG.md**

把验收通过/失败情况追加到 `AGENT_LOG.md`。

---

## Self-Review

**Spec 覆盖：**
- Harness 装配 → Task 8 ✓
- AgentLoop → Task 9 ✓
- 4 个内建工具 → Task 2-5 ✓
- Guardrail → Task 6 ✓
- Tracer → Task 7 ✓
- LLM 客户端 → Task 1 ✓
- main.py 两种模式 → Task 10 ✓
- 爬虫适配（模式 A）→ Task 11 ✓
- 验收标准 1-6 → Task 12 ✓
- 无硬编码 → Global Constraints + conftest mock_env ✓

**类型一致性：** `Tool.handler(**args)` / `ToolRegistry.call(name, args)` / `LLMClient.chat()` 返回 `{"text","tool_calls"}` / `Guardrail.allow(action)` 返回 `(bool, str)` —— 各 Task 间签名一致 ✓

**占位符扫描：** 无 TBD/TODO，每步含可运行代码 ✓
