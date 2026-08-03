# explorer-agent — 设计规格说明书 (SPEC)

> 南京大学通知公告智能爬虫 — 网站探索 Agent
> 版本：0.1 (MVP) | 日期：2026-08-03
> 基于 Harness Engineering 架构（参考 `流程参考.md` Phase 1 + `教程.md`）

---

## 1. 概述

### 1.1 一句话定义

`explorer-agent` 是一个 **Python 单 Agent**，基于 Harness Engineering 架构。它的职责是：**探索南京大学院系网站结构 → 生成爬取策略 JSON**，供 JS 爬虫（`crawler/`）使用。

### 1.2 核心公式

```
单次 Agent = LLM × Harness
```

LLM 只负责一行任务决策（"下一步做什么"），其余（工具调度、权限门控、上下文装配、轨迹记录）全是工程零件（Harness）。

### 1.3 与爬虫的关系（并列结构）

```
whaleU-crawler/
├── crawler/           # JS 爬虫（执行者：按策略爬取）
└── explorer-agent/    # Python Agent（探索者：生成策略）
```

- Agent **不重写**爬虫，而是把爬虫当作 `run_shell` 工具调用。
- 爬虫在无策略时可委托 Agent 生成策略（模式 A）。
- Agent 也可作为编排者，生成策略后调爬虫执行（模式 B）。

**适配原则（重要）**：Agent 严格按 Harness 工程规格（`流程参考.md`/`教程.md`/本 SPEC）实现，是固定锚点。当 Agent 与爬虫之间出现接口不匹配时，**改爬虫去适配 Agent，不反过来为迁就爬虫而改 Agent 架构**。即：爬虫代码可自由改动，Agent 的核心循环/装配/门控设计不被允许偏离规格。

---

## 2. 架构

```
┌─────────────────────────────────────────────────┐
│                   agent.yaml                      │
│               （声明式总配置）                      │
└────────────┬────────────────────────────────────┘
             │ 驱动装配
             ▼
┌─────────────────────────────────────────────────┐
│              Harness（零件容器）                    │
│  system_prompt │ rules │ tools │ guardrail        │
│  (tracer)                                        │
└────────────┬────────────────────────────────────┘
             │ 传入
             ▼
┌─────────────────────────────────────────────────┐
│           AgentLoop（核心循环）                     │
│  ① 上下文装配 → ② while 循环 → ③ 收尾            │
│  每轮: LLM 决策 → 门控 → 工具分发 → 回灌          │
└─────────────────────────────────────────────────┘
```

MVP 范围（对应 `流程参考.md` Phase 1）：Harness + AgentLoop + Tools + Guardrail + 入口。
**不含**（后续迭代）：MCP、Skill、Hooks、Sandbox(Docker)、Memory、SubAgent、RAG、反馈闭环。

---

## 3. 目录结构

```
explorer-agent/
├── agent.yaml                # 声明式总配置（模型/工具/规则/门控）
├── rules/
│   └── AGENTS.md             # 行为约束（Agent 该做什么、不该做什么）
├── guardrails/
│   └── policy.yaml           # 权限门控策略（deny/ask_user/allow）
├── src/
│   ├── harness.py            # Harness 类 + from_yaml 装配
│   ├── agent_loop.py         # AgentLoop 核心循环
│   ├── llm/
│   │   └── client.py         # OpenAI 兼容 LLM 客户端
│   └── tools/
│       ├── registry.py       # Tool 对象 + 注册表
│       ├── file_tools.py     # read_file / write_file
│       ├── shell_tools.py    # run_shell（调 node collector.js / nju-query.js）
│       └── web_tools.py      # fetch_url（Python httpx 抓页面 HTML）
├── main.py                   # 入口
├── requirements.txt          # openai / pyyaml / httpx
├── traces/                   # 轨迹输出目录（jsonl）
├── SPEC.md                   # 本文件
├── AGENTS.md                 # AI 协作指南
└── tests/
    ├── test_harness.py
    ├── test_agent_loop.py
    └── test_tools.py
```

---

## 4. 组件设计

### 4.1 Harness（`src/harness.py`）

装配所有零件的容器。从 `agent.yaml` 声明式构建。

```python
@dataclass
class Harness:
    system_prompt: str          # 系统提示词
    rules: str                  # rules/AGENTS.md 内容
    tools: dict[str, Tool]      # 内建工具
    guardrail: Guardrail        # 权限门控
    config: dict                # 原始配置

    @classmethod
    def from_yaml(cls, path: str) -> "Harness":
        """从 agent.yaml 装配。"""
```

### 4.2 AgentLoop（`src/agent_loop.py`）

核心循环，三段式：

```
① 上下文装配（一次性）：system_prompt + rules + goal
② while 主循环（每轮）：
   - LLM 决策（唯一一次 LLM 调用）→ 返回 {text, action}
   - action.type == "done" → 结束
   - Guardrail 门控 → 拦截危险动作
   - 分发：call_tool → 执行 → 结果回灌上下文
   - Tracer 记录（决策 + 观察）
③ 收尾：Tracer.flush() 落盘
```

action 解析（基于 OpenAI Function Calling）：
- LLM 返回 `tool_calls` → action = `call_tool`，参数从 tool_call.arguments 取
- LLM 只返回 text、无 `tool_calls` → action = `done`（"无工具调用即停"），text 即最终答案

预算守卫：`max_steps` 上限（默认 30），超时，重复调用检测。
**compact（熵管理）MVP 不实现**：`token_limit` 在 agent.yaml 中保留占位，但首版不触发压缩（探索任务上下文量可控；compact 留待后续迭代）。

### 4.3 LLM 客户端（`src/llm/client.py`）

OpenAI 兼容接口。**绝不硬编码** key/路径，全部走环境变量：

```python
class LLMClient:
    def __init__(self):
        self.base_url = os.environ["LLM_BASE_URL"]      # https://open.cherryin.cc/v1
        self.api_key  = os.environ["LLM_API_KEY"]       # CHERRYIN_API_KEY
        self.model    = os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-flash(free)")

    def chat(self, messages, tools=None) -> dict:
        """返回 {text, action}。action 从 tool_calls 解析。"""
```

默认指向 CherryIN 的 deepseek-v4-flash(free)。用户可通过环境变量切换到任意 OpenAI 兼容端点。

### 4.4 工具系统（`src/tools/`）

每个工具 = `{name, description, parameters(JSON Schema), handler}`。

| 工具 | 文件 | 职责 | 沙箱 | 需审批 |
|------|------|------|------|--------|
| `fetch_url` | web_tools.py | 抓取页面 HTML（Python httpx） | 否 | 否（只读） |
| `read_file` | file_tools.py | 读文件（策略/配置） | 否 | 否（只读） |
| `write_file` | file_tools.py | 写文件（策略 JSON） | 否 | **是** |
| `run_shell` | shell_tools.py | 执行 shell（调爬虫/浏览器服务） | 否 | **是** |

工具描述自动转 OpenAI Function Calling 格式。工具失败时错误信息回灌上下文（不崩溃）。

### 4.5 权限门控（`guardrails/policy.yaml`）

```yaml
rules:
  - pattern: "rm -rf *"           # 黑名单：直接拒绝
    action: deny
    reason: "禁止递归删除"
  - tools: ["write_file"]
    scope: "outside_strategies"   # 写策略目录外需确认
    action: ask_user
    reason: "在策略目录外写文件需要确认"
  - tools: ["run_shell"]
    pattern: "rm *"               # 删除操作需确认
    action: ask_user
  - tools: ["run_shell"]
    pattern: "sudo *"             # sudo 需确认
    action: ask_user
  - tools: ["fetch_url", "read_file"]
    action: allow                 # 只读自动放行
```

拦截原因回灌上下文，让 LLM 知道为什么被拦。

### 4.6 Tracer（轻量，内置于 AgentLoop）

> 注：Tracer 不在 `流程参考.md` Phase 1 严格范围内（属 Phase 3/P1），但因其极简（~20 行）且对"教师检查决策链"价值高，MVP 纳入一个最简版本。

MVP 用最简 Tracer：每轮记录 `{step, text, action, observation}` 到内存，会话末 `flush()` 写 `traces/trace-<ts>.jsonl`。便于教师检查 Agent 决策链。

---

## 5. 双向调用设计（两种入口模式，无递归）

### 模式 A — 爬虫入口（委托，one-shot）

```
node crawler/src/collectors/collector.js --site <url>
  → 无策略
  → 调用: python explorer-agent/main.py --explore-only <url>
  → Agent 探索 + 写策略 + 退出（绝不回调爬虫）
  → 爬虫进程拿到新策略，继续爬取
```

`--explore-only` 标志保证 Agent 只生成策略、不调爬虫，避免 crawler→Agent→crawler 递归。

### 模式 B — Agent 入口（编排）

```
python explorer-agent/main.py "探索并爬取 cs.nju.edu.cn 通知入口"
  → Agent 探索 + 写策略
  → Agent 调用: node crawler/src/collectors/collector.js --site <url>
  → 爬虫找到策略 → 爬取 → 返回结果
  → Agent 汇报
```

Agent 是唯一入口，单向调爬虫，无环。

**关键约束**：模式 A 中 Agent 绝不回调爬虫。两种模式都无相互递归。

---

## 6. 配置（agent.yaml）

**绝不硬编码** key/路径。agent.yaml 只声明结构，敏感值用 `${ENV_VAR}` 占位，运行时从环境注入。

```yaml
agent:
  name: "explorer-agent"
  model: "${LLM_MODEL}"              # deepseek/deepseek-v4-flash(free)
  max_steps: 30
  token_limit: 60000

llm:
  base_url: "${LLM_BASE_URL}"        # https://open.cherryin.cc/v1
  api_key: "${LLM_API_KEY}"          # 环境注入，不落盘

rules:
  - path: "./rules/AGENTS.md"

tools:
  builtin:
    - name: "fetch_url"
      module: "src.tools.web_tools"
    - name: "read_file"
      module: "src.tools.file_tools"
    - name: "write_file"
      module: "src.tools.file_tools"
      require_approval: true
    - name: "run_shell"
      module: "src.tools.shell_tools"
      require_approval: true

guardrail:
  policy: "./guardrails/policy.yaml"

tracer:
  type: "file"
  output: "./traces/"

paths:                               # 路径集中声明，不硬编码
  strategies_dir: "${STRATEGIES_DIR}" # 指向 crawler/data/strategies/
  crawler_script: "${CRAWLER_SCRIPT}" # crawler/src/collectors/collector.js
  nju_browser: "${NJU_BROWSER_DIR}"   # NJU 浏览器服务目录（可选）
```

环境变量通过 `.env`（不进版本库）或系统环境设置。opencode.json 已 deny 读取 `.env`。

---

## 7. 数据流

```
用户目标 "探索 cs.nju.edu.cn"
  │
  ▼
AgentLoop 上下文装配（system_prompt + rules + goal）
  │
  ▼ while 循环
  ├─ LLM 决策 → call_tool(fetch_url, "https://cs.nju.edu.cn/")
  ├─ 工具执行 → 返回首页 HTML
  ├─ 回灌上下文
  ├─ LLM 决策 → call_tool(fetch_url, "https://cs.nju.edu.cn/1702/list.htm")  # 候选子页
  ├─ 工具执行 → 返回子页 HTML
  ├─ 回灌上下文
  ├─ LLM 决策 → call_tool(write_file, "crawler/data/strategies/cs.nju.edu.cn.json", <策略JSON>)
  ├─ Guardrail: write_file 需审批 → ask_user → 用户确认
  ├─ 工具执行 → 写策略文件
  ├─ 回灌上下文
  └─ LLM 决策 → done("已生成策略，共 N 个入口")
  │
  ▼ 收尾
  Tracer.flush() → traces/trace-<ts>.jsonl
```

策略文件格式复用爬虫现有 v3 格式（`{domain}.json`），保证 `collector.js --site` 能直接使用。

---

## 8. 错误处理

| 场景 | 处理 |
|------|------|
| LLM 调用失败 | 重试 1 次，仍失败则回灌错误，Agent 换路径 |
| 工具执行失败 | 错误信息回灌上下文（不崩溃），Agent 据此重试/换路 |
| `fetch_url` 超时/404 | 回灌错误，Agent 选其他 URL |
| `write_file` 被门控拒绝 | 原因回灌，Agent 改路径或放弃 |
| 达到 max_steps | 返回"任务未完成（步数上限）"+ 已完成部分 |
| 环境变量缺失 | 启动时报错退出，不静默降级 |

---

## 9. 测试

- **单元测试**（pytest）：Harness.from_yaml 装配、Tool 注册/调用、Guardrail 匹配、LLM 客户端 mock。
- **集成测试**：mock LLM 返回固定 action，验证 AgentLoop 跑通"fetch_url → write_file → done"闭环。
- **验收测试**（手动）：对 `cs.nju.edu.cn` 跑真实 Agent，检查生成的策略能被 `node collector.js --site` 使用。

---

## 10. 验收标准

1. **单 Agent 闭环**：输入"探索 https://cs.nju.edu.cn/ 的通知入口"，Agent 自主 fetch 首页+子页 → LLM 分析 → 写出 `crawler/data/strategies/cs.nju.edu.cn.json`。
2. **策略可用**：生成的策略能被 `node crawler/src/collectors/collector.js --site https://cs.nju.edu.cn/` 直接使用并爬取到通知。
3. **门控生效**：尝试 `run_shell` 执行 `rm -rf /tmp/x` 时，Guardrail 拦截并回灌原因。
4. **轨迹可审计**：每次运行在 `traces/` 生成 jsonl 轨迹文件，含每步决策+观察。
5. **无硬编码**：代码中无任何 key/绝对路径；全部走环境变量/配置。
6. **模式 A 可用**：`node collector.js --site <新站点>` 无策略时，能调起 Agent 生成策略并继续爬取。

---

## 11. 不做事项（YAGNI）

| 不做 | 原因 |
|------|------|
| 不重写爬虫 | 爬虫保持 JS，Agent 通过 run_shell 调用 |
| 不做多 Agent | MVP 只需单 Agent，SubAgent 后续迭代 |
| 不接 MCP/Skill/Hooks | Phase 2 内容，MVP 不含 |
| 不接 Memory/RAG | 跨会话记忆后续迭代 |
| 不做 Docker 沙箱 | 本地开发模式，后续加 |
| 不硬编码 key/路径 | 全部环境变量/配置 |
| 不读 .env 文件内容 | 安全规则，只通过 process.env 读 |

---

## 12. 依赖

```
openai       # OpenAI 兼容 SDK（用于 CherryIN 端点）
pyyaml       # 解析 agent.yaml / policy.yaml
httpx        # fetch_url 工具用
pytest       # 测试
```

Python ≥ 3.11（环境已有 3.13）。

---

## 13. 开发优先级（实现阶段）

| 步骤 | 范围 | 产出 |
|------|------|------|
| 1 | LLM 客户端 + 环境变量配置 | 能调通 CherryIN deepseek |
| 2 | Tool 注册 + 4 个内建工具 | fetch_url/read_file/write_file/run_shell 可用 |
| 3 | Harness.from_yaml + agent.yaml | 声明式装配跑通 |
| 4 | AgentLoop 核心循环 + Tracer | 能跑单 Agent 闭环 |
| 5 | Guardrail + policy.yaml | 危险动作拦截 |
| 6 | main.py 入口 + 两种模式 | 模式 A/B 可用 |
| 7 | 测试 + 验收 | 对 cs.nju.edu.cn 跑通 |
```
