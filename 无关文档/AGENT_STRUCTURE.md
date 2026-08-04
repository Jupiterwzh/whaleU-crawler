# explorer-agent 结构详解

> 南京大学网站探索 Agent — 每个文件的详细介绍
> 用于学习 harness 工程实战 + 手动核查
> 更新：2026-08-03

---

## 一、Agent 是什么

一句话：**LLM 只做一行任务决策，其余全是工程零件（Harness）。**

```
单次 Agent = LLM × Harness
```

- **LLM**（大脑）：每轮看上下文，决定"下一步做什么"（调哪个工具 / 还是结束）。只占代码里一行。
- **Harness**（躯壳）：装配上下文、调度工具、拦截危险动作、记录轨迹。全是工程，不含智能。

explorer-agent 的职责：探索南大网站结构 → 生成爬取策略 JSON → 供 JS 爬虫使用。

---

## 二、目录结构总览

```
explorer-agent/
├── agent.yaml              # ① 声明式总配置（装配入口）
├── rules/
│   └── AGENTS.md           # ② 行为约束（你填的内容物）
├── guardrails/
│   └── policy.yaml         # ③ 权限门控策略
├── src/
│   ├── harness.py          # ④ Harness 类：装配所有零件
│   ├── agent_loop.py       # ⑤ 核心循环（Agent 的心脏）
│   ├── llm/
│   │   └── client.py       # ⑥ LLM 客户端（OpenAI 兼容）
│   ├── tools/
│   │   ├── registry.py     # ⑦ Tool 类 + 注册表
│   │   ├── file_tools.py   # ⑧ read_file / write_file
│   │   ├── web_tools.py    # ⑨ fetch_url
│   │   └── shell_tools.py  # ⑩ run_shell
│   ├── guardrail.py        # ⑪ 权限门控（拦截危险动作）
│   └── tracer.py           # ⑫ 轨迹记录
├── main.py                 # ⑬ 入口（两种模式）
├── traces/                 # 运行时生成：轨迹 jsonl
├── tests/                  # 21 个自动化测试
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
├── SPEC.md                 # 设计规格说明书
├── PLAN.md                 # 实现计划（13 个 Task）
└── MANUAL_CHECKS.md        # 手动验收清单
```

---

## 三、逐文件详解

### ① agent.yaml — 声明式总配置

**作用**：一次性装配的声明式入口。Harness.from_yaml() 读它来构建整个 Harness 对象。

**格式**：YAML，用 `${ENV_VAR}` 占位敏感值（运行时从环境变量注入，绝不硬编码）。

**关键字段**：

| 字段 | 说明 | 当前值 |
|------|------|--------|
| `agent.name` | Agent 名称 | "explorer-agent" |
| `agent.model` | LLM 模型 | `${LLM_MODEL}` → deepseek/deepseek-v4-flash(free) |
| `agent.max_steps` | 循环步数上限 | 30 |
| `llm.base_url` | LLM 端点 | `${LLM_BASE_URL}` → https://open.cherryin.cc/v1 |
| `llm.api_key` | LLM 密钥 | `${LLM_API_KEY}`（环境注入） |
| `rules` | 规则文件路径列表 | ["./rules/AGENTS.md"] |
| `tools.builtin` | 内建工具列表 | fetch_url/read_file/write_file/run_shell |
| `guardrail.policy` | 门控策略文件 | "./guardrails/policy.yaml" |
| `tracer.output` | 轨迹输出目录 | "./traces/" |
| `paths.strategies_dir` | 策略目录 | `${STRATEGIES_DIR}` |
| `paths.crawler_script` | 爬虫脚本 | `${CRAWLER_SCRIPT}` |

**怎么改**：换模型改 `agent.model`；加工具在 `tools.builtin` 加条目；调步数改 `max_steps`。

---

### ② rules/AGENTS.md — 行为约束

**作用**：harness 的"内容物"——你填的行为约束。作为第二条 system 消息注入上下文。LLM 据此决定怎么探索、生成什么格式的策略。

**格式**：Markdown 纯文本。

**当前内容**：6 条规则 + 1 个策略 JSON 示例。关键规则：
- 职责：分析网站结构，找通知公告列表页入口
- 工具优先级：先 fetch_url 抓页面，再 write_file 存策略
- 策略 JSON 必含字段：meta/entries/pagination/extraction/notes
- 完成后停止（无工具调用即 done）
- 末尾有完整 JSON 示例让 LLM 照格式填

**怎么改**：直接编辑这个 md 文件，不动任何代码。比如：
- 加一条"优先检查 /list.htm 结尾的链接"
- 改示例的 entries 字段
- 加输出语言要求

**这是你后续调 Agent 行为的主要抓手——改 md 不改代码。**

---

### ③ guardrails/policy.yaml — 权限门控策略

**作用**：声明式配置什么动作自动放行、什么需确认、什么直接拒绝。

**格式**：YAML，`rules` 列表，每条规则按顺序匹配。

**规则字段**：

| 字段 | 说明 | 示例 |
|------|------|------|
| `tools` | 匹配的工具名列表 | ["run_shell", "write_file"] |
| `pattern` | 参数子串匹配 | "rm -rf" |
| `scope` | 路径范围匹配 | "outside_strategies" / "inside_strategies" / "outside_project" |
| `action` | 裁定 | deny / ask_user / allow |
| `reason` | 原因（回灌给 LLM） | "禁止递归删除" |

**当前规则**：
1. `rm -rf` → **deny**（禁止递归删除）
2. `run_shell` + `sudo` → **ask_user**
3. `run_shell` + `rm ` → **ask_user**
4. `write_file` + `inside_strategies` → **allow**（策略目录内自动放行）
5. `write_file` + `outside_strategies` → **ask_user**（目录外需确认）
6. `read_file` + `outside_project` → **ask_user**（项目外需确认）
7. `fetch_url` / `read_file` → **allow**（默认放行）

**怎么改**：加规则在 `rules` 列表追加。注意**顺序敏感**（先匹配的先生效），deny 要在 ask_user 之前。

---

### ④ src/harness.py — Harness 装配

**作用**：把所有零件拼到一起，生成 Harness 对象。对应 notes.md 里的 `build_agent()`。

**关键方法**：
- `Harness.from_yaml(path)`：读 agent.yaml → 解析 ${ENV_VAR} → 加载 rules 文本 → 导入工具模块调工厂 → 装配 Guardrail（含路径 context）→ 创建 Tracer → 返回 Harness 对象
- `_resolve_env(value)`：递归把 `${VAR}` 替换为环境变量值（处理 str/dict/list）

**Harness 对象属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `system_prompt` | str | 系统提示词（极简，只身份） |
| `rules` | str | rules/AGENTS.md 全文 |
| `tools` | ToolRegistry | 工具注册表 |
| `guardrail` | Guardrail | 权限门控（含 strategies_dir/project_root context） |
| `tracer` | Tracer | 轨迹记录器 |
| `config` | dict | 原始 agent.yaml 配置 |

**装配流程**：
```
agent.yaml → _resolve_env → 读 rules 文件 → import 工具模块 → 调工厂函数
→ ToolRegistry.register → Guardrail.from_yaml(带 context) → Tracer(output_dir)
→ 返回 Harness
```

**怎么改**：加新零件类型（如 Skill/Memory）时，在 from_yaml 里加装配逻辑。

---

### ⑤ src/agent_loop.py — 核心循环

**作用**：Agent 的心脏。三段式：上下文装配 → while 循环 → 收尾。LLM 只占其中一行。

**三段式**：

```
① 上下文装配（一次性）
   context = [system_prompt, rules, goal]

② while 主循环（每轮）
   ├─ LLM 决策：chat(context, tools) → {text, tool_calls}  ← 唯一的 LLM 调用
   ├─ 无 tool_calls → done（返回 text）
   ├─ 追加 assistant 消息（含 tool_calls 字段，符合 OpenAI 规范）
   └─ 对每个 tool_call：
      ├─ Guardrail 门控（allow/deny/ask_user）
      ├─ 执行 tools.call(name, args)
      └─ 结果回灌 context（role:tool 消息）

③ 收尾
   Tracer.flush() → 落盘 jsonl
```

**关键设计**：
- **done 检测**：无 tool_calls 即停（"无工具调用即停"派）
- **assistant 消息**：有 tool_calls 时一次性追加（含 tool_calls 字段），不重复
- **tool 结果**：每个 tool_call 都有对应的 role:tool 消息（OpenAI 要求）
- **EOFError 防护**：guardrail.allow() 在非交互环境调 input() 会 EOFError，try/except 捕获后当 deny
- **步数上限**：max_steps（默认 30），超限返回"任务未完成"

**怎么改**：加 compact（熵管理）在循环开头加 token 检查；加 SubAgent 在分发逻辑加 spawn_subagent 分支。

---

### ⑥ src/llm/client.py — LLM 客户端

**作用**：OpenAI 兼容接口封装。绝不硬编码 key/端点。

**环境变量**：

| 变量 | 说明 | 默认 |
|------|------|------|
| `LLM_BASE_URL` | 端点 | 无（必填） |
| `LLM_API_KEY` | 密钥 | 无（必填，缺则 RuntimeError） |
| `LLM_MODEL` | 模型名 | deepseek/deepseek-v4-flash(free) |

**chat() 方法参数**：
- `max_tokens=4096`（限制单次回复长度）
- `temperature=0.3`（低温度，探索要确定性）
- 失败重试 1 次（共 2 次尝试）

**返回**：`{"text": str, "tool_calls": list|None}`，tool_calls 每项 `{name, arguments, id}`

**怎么改**：换 LLM 提供商只改环境变量；调温度/长度改 kwargs。

---

### ⑦ src/tools/registry.py — Tool 类 + 注册表

**Tool dataclass 字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 工具名（LLM 看到） |
| `description` | str | 描述（决定 LLM 何时调用） |
| `parameters` | dict | JSON Schema（参数定义） |
| `handler` | callable | 实际执行的函数 |
| `require_approval` | bool | 是否需门控审批 |

**ToolRegistry 方法**：
- `register(tool)`：注册工具
- `get(name)`：取工具
- `names()`：列出所有工具名
- `to_openai_schemas()`：转 OpenAI Function Calling 格式
- `call(name, args)`：执行工具（**args 解包，返回 str）

**怎么加新工具**：在 tools/ 下新建文件，定义 handler 函数 + make_xxx_tools() 工厂，在 agent.yaml 的 tools.builtin 加条目。

---

### ⑧ src/tools/file_tools.py — read_file / write_file

**read_file(path)**：读文件，UTF-8。require_approval=False（只读自动放行）。
**write_file(path, content)**：写文件，自动建父目录。require_approval=True（门控：策略目录内 allow，外 ask_user）。

**工厂**：`make_file_tools(strategies_dir)` 返回两个 Tool。strategies_dir 从 agent.yaml 的 paths 注入。

---

### ⑨ src/tools/web_tools.py — fetch_url

**fetch_url(url)**：用 httpx 抓页面 HTML，follow_redirects，设 User-Agent，timeout=20s。require_approval=False。

**工厂**：`make_web_tools()` 无参数。

---

### ⑩ src/tools/shell_tools.py — run_shell

**run_shell(cmd)**：用 subprocess.run(shell=True)，capture stdout+stderr，timeout=300s。require_approval=True（门控：rm/sudo 需确认）。

**工厂**：`make_shell_tools()` 无参数。用于调 `node collector.js` 或 NJU 浏览器服务。

---

### ⑪ src/guardrail.py — 权限门控

**作用**：动作执行前校验。返回 (是否放行, 原因)。不放行时原因回灌给 LLM。

**关键方法**：
- `from_yaml(path, context)`：加载 policy.yaml，context 含 strategies_dir + project_root
- `allow(action)` → `(bool, str)`：按规则顺序匹配，三种裁定 deny/ask_user/allow
- `_scope_match(scope, args)`：路径范围检查（inside/outside_strategies/project）

**路径检查**：用 `os.path.realpath` + `startswith(目录 + os.sep)`，防前缀误匹配（如 `/tmp/strat` 误匹配 `/tmp/strategies`）。

---

### ⑫ src/tracer.py — 轨迹记录

**作用**：每轮记录决策+观察，会话末落盘 jsonl。便于教师检查决策链。

**记录格式**（每行一个 JSON）：
```json
{"trace_id": "trace-...", "step": 1, "timestamp": 0.12, "text": "...", "action": {...}, "observation": "..."}
```

**方法**：`record(step, text, action, observation)` 追加到内存；`flush()` 写 `traces/trace-<毫秒时间戳>.jsonl`。

---

### ⑬ main.py — 入口

**两种模式**：

| 模式 | 命令 | 行为 |
|------|------|------|
| A（爬虫委托） | `python main.py --explore-only <url>` | goal 含具体策略路径 + "不要爬取"；Agent 只生成策略 |
| B（Agent 编排） | `python main.py "探索并爬取 X"` | Agent 探索→写策略→调爬虫→汇报 |

**流程**：load_env()（自动加载 .env）→ 解析参数 → 构造 goal → Harness.from_yaml → LLMClient → AgentLoop.run(goal) → 打印结果

**`load_env()`**：`main()` 开头调用，用 `python-dotenv` 从 `main.py` 同目录的 `.env` 加载环境变量，`override=False`（已导出的 env 优先）。无需手动 `source .env`。未来多 Agent 时迁移到 `src/env.py`。

---

## 四、怎么配置

### 环境变量（绝不硬编码）

```bash
export LLM_BASE_URL=https://open.cherryin.cc/v1
export LLM_API_KEY=你的CherryIN密钥
export LLM_MODEL=deepseek/deepseek-v4-flash(free)
export STRATEGIES_DIR=/home/wangzhiheng/whaleU-crawler/crawler/data/strategies
export CRAWLER_SCRIPT=/home/wangzhiheng/whaleU-crawler/crawler/src/collectors/collector.js
```

或复制 `.env.example` 为 `.env` 填入真实值，用 `set -a && source .env && set +a` 加载。

### 依赖安装

```bash
cd explorer-agent
pip install -r requirements.txt   # openai pyyaml httpx pytest
```

---

## 五、怎么修改

| 想改什么 | 改哪里 | 要动代码吗 |
|---------|--------|-----------|
| Agent 行为规则 | `rules/AGENTS.md` | 否，改 md |
| 策略 JSON 格式 | `rules/AGENTS.md` 的示例 | 否 |
| 安全策略（拦什么） | `guardrails/policy.yaml` | 否，改 yaml |
| LLM 模型/端点 | 环境变量 | 否 |
| 步数上限 | `agent.yaml` max_steps | 否，改 yaml |
| 工具超时 | 对应 tools/*.py | 是 |
| 加新工具 | tools/ 新建文件 + agent.yaml 加条目 | 是 |
| system_prompt | `harness.py:67` | 是 |
| 加 compact 熵管理 | `agent_loop.py` 循环开头 | 是 |

---

## 六、怎么使用

### 模式 B：Agent 编排（主动探索）

```bash
cd explorer-agent
python main.py "探索 https://cs.nju.edu.cn/ 的通知公告入口"
```
Agent 自主抓首页→分析→抓子页→写策略→（可选）调爬虫→汇报。

### 模式 A：爬虫委托（被动生成）

```bash
node crawler/src/collectors/collector.js --site https://cs.nju.edu.cn/
```
爬虫无策略时自动调 `python main.py --explore-only <url>`，Agent 生成策略后爬虫继续。

### 查看轨迹

```bash
ls explorer-agent/traces/
cat explorer-agent/traces/$(ls -t explorer-agent/traces/ | head -1)
```

### 跑测试

```bash
cd explorer-agent
python -m pytest tests/ -v   # 21 个测试
```

---

## 七、数据流（一次完整运行）

```
用户："探索 cs.nju.edu.cn"
  │
  ▼ main.py 构造 goal
  │
  ▼ Harness.from_yaml("agent.yaml") 装配
  │   system_prompt + rules + tools + guardrail + tracer
  │
  ▼ AgentLoop.run(goal)
  │
  │  ① 上下文：[system_prompt, rules, goal]
  │
  │  ② 循环第 1 轮：
  │     LLM.chat(context, tools) → "抓首页" + tool_calls:[fetch_url(cs.nju.edu.cn)]
  │     Guardrail.allow → allow
  │     tools.call("fetch_url", {url}) → "<html>...</html>"
  │     context 回灌：assistant(含tool_calls) + tool(结果)
  │     Tracer.record(1, ...)
  │
  │  ② 循环第 2 轮：
  │     LLM.chat(context, tools) → "抓子页" + tool_calls:[fetch_url(/1702/list.htm)]
  │     ... 同上
  │
  │  ② 循环第 N 轮：
  │     LLM.chat(context, tools) → "写策略" + tool_calls:[write_file(策略.json, {...})]
  │     Guardrail.allow → inside_strategies → allow
  │     tools.call("write_file", {path, content}) → "已写入"
  │
  │  ② 循环第 N+1 轮：
  │     LLM.chat(context, tools) → "已生成策略，共 1 个入口" (无 tool_calls)
  │     → done，返回 text
  │
  ▼ ③ 收尾：Tracer.flush() → traces/trace-xxx.jsonl
  │
  ▼ 打印结果
```
