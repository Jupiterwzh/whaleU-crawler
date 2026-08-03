# SDD 实战教程 — explorer-agent 实现全过程

> 基于 AGENT_LOG.md 与 task 报告的补充教学
> 目标：详细可复现，满足学习 harness 工程实战的需求
> 更新：2026-08-03

---

## 一、什么是 SDD（Subagent 驱动开发）

**核心思想**：每个 Task 派一个**全新 subagent**（独立上下文）去实现，再派另一个 subagent 审查。我自己是"调度员"，不亲自写代码。

**为什么用 subagent**：
- 隔离上下文：subagent 只拿到它那个 Task 的需求，不被会话历史污染
- 保护我的上下文：我把精力放在调度和审查，不被实现细节填满
- 可审查：每个 Task 都有独立的实现报告 + 审查报告

**每个 Task 的完整流程**：
```
① 提取 brief（task-brief 脚本把 Task N 的内容抽到独立文件）
② 记录 BASE（git rev-parse HEAD，审查时生成 diff 用）
③ 派实现 subagent（给 brief 路径 + 上下文 + 报告契约）
④ 处理报告（DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT）
⑤ 生成 review 包（review-package 脚本生成 diff 文件）
⑥ 派审查 subagent（给 brief + 报告 + diff）
⑦ 处理审查（通过 → 记账本 → 下一 Task；有问题 → 修复循环）
⑧ 修复循环（最多 5 轮：1-3 轮恢复原实现者，4-5 轮换更强的）
```

---

## 二、前置设置（可复现）

### 2.1 git 初始化

```bash
cd /home/wangzhiheng/whaleU-crawler
cat > .gitignore << 'EOF'
.env
__pycache__/
*.pyc
crawler/          # crawler 有自己的 .git
src/              # 暂留的旧代码
explorer-agent/traces/
EOF
git init
git add .gitignore README.md explorer-agent/SPEC.md explorer-agent/PLAN.md ...
git commit -m "chore: init repo with explorer-agent design docs"
```

### 2.2 SDD 工作区 + 进度账本

SDD 技能自带脚本，用 git 管理工作区：

```bash
# 建工作区（每个 plan 独立目录，防串扰）
WS=$(bash .../scripts/sdd-workspace explorer-agent/PLAN.md)
# 输出：/home/wangzhiheng/whaleU-crawler/.superpowers/sdd/PLAN

# 建进度账本（防上下文丢失后重复执行）
echo "# SDD ledger — plan: explorer-agent/PLAN.md" > "$WS/progress.md"
```

**为什么需要账本**：对话上下文可能被压缩（compaction），丢失后我会忘记哪些 Task 做过了。账本是"恢复地图"——它记录的 commit 在 git 里确实存在，可信度高于我的记忆。

### 2.3 预审计划

扫一遍 PLAN.md 的 Task 间接口一致性：
- Task 1 产出 `LLMClient.chat()→{text,tool_calls}` ← Task 9 消费 ✓
- Task 2 产出 `Tool/ToolRegistry` ← Task 3-5,8 消费 ✓
- Task 6 产出 `Guardrail.allow()→(bool,str)` ← Task 9 消费 ✓
- Task 8 产出 `Harness.from_yaml` ← Task 9,10 消费 ✓

无冲突，开始执行。

---

## 三、Task 逐个走读（重点 Task）

### Task 0：项目初始化（调度员直接做）

**为什么不用 subagent**：Task 0 是纯脚手架（空文件 + 配置），无逻辑无测试。用 subagent 会卡在文件写入权限提示上（opencode.json 的 `edit: * = ask`）。

**做了什么**：
- requirements.txt（openai/pyyaml/httpx/pytest）
- .env.example（环境变量模板，无真实 key）
- src/__init__.py、src/llm/__init__.py、src/tools/__init__.py（包标识）
- tests/conftest.py（共享 fixture：注入假环境变量 + sys.path）

**conftest.py 的关键设计**：
```python
@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake-key")  # 测试绝不依赖真实 key
    monkeypatch.setenv("STRATEGIES_DIR", "/tmp/test-strategies")
    # ...
```
`autouse=True` 让每个测试自动注入假环境，绝不碰真实 key。

**提交**：`430ad83`

---

### Task 1：LLM 客户端（第一个 subagent）

**提取 brief**：
```bash
bash .../scripts/task-brief explorer-agent/PLAN.md 1
# 写到 .superpowers/sdd/PLAN/task-1-brief.md（109 行）
```

**记录 BASE**：`git rev-parse HEAD` → `430ad83`（审查时生成 diff 的起点）

**派实现 subagent**，给它的内容：
1. 一句话定位："你负责实现 Task 1: LLM 客户端"
2. brief 路径："读这个文件，它是你的完整需求"
3. 上下文："Task 0 已完成，conftest 已注入假 env，pip 已装"
4. 报告契约："写报告到 task-1-report.md，回复只返回摘要"

**实现 subagent 做了什么**（据 task-1-report.md）：
- 写测试 `test_llm_client.py`（3 个：文本返回、tool_calls 解析、缺 key 报错）
- 跑测试确认失败（模块不存在）
- 写实现 `client.py`（LLMClient 类，chat() 返回 {text, tool_calls}）
- 跑测试确认通过（3 passed）
- **额外发现**：根 .gitignore 的 `src/` 规则误忽略了 `explorer-agent/src/`，改为 `/src/`（锚定根目录）
- 提交 `dd30420`

**生成 review 包**：
```bash
bash .../scripts/review-package explorer-agent/PLAN.md 430ad83 HEAD
# 写到 review-430ad83..dd30420.diff（含 commit 列表 + stat + 完整 diff）
```

**派审查 subagent**，给它：brief + 报告 + diff 路径 + 全局约束（不硬编码 key、chat 返回结构、缺 key 抛 RuntimeError、测试 mock）。

**审查结论**（据 task-1-review.md）：
- 规格 ✅：所有要求实现，无遗漏
- 质量 ✅：2 个 Minor（缺 key 测试用裸 try/except 而非 pytest.raises；文本测试隐式依赖 conftest）——均源自 brief，不阻断

**记账本**：
```
Task 1: complete (commits 430ad83..dd30420, review clean, 2 minor deferred)
```

**教训**：subagent 能发现 brief 之外的问题（.gitignore 误忽略），这是独立上下文的价值——它带着新鲜眼光看代码。

---

### Task 2-5：工具系统（4 个机械 Task，顺利通过）

这 4 个 Task 都是"写 Tool 类 + 测试"的机械模式，brief 含完整代码，subagent 逐字实现 + TDD。

| Task | 产出 | commit | 测试 | 审查 |
|------|------|--------|------|------|
| 2 | Tool/ToolRegistry | 82034ec | 3 | ✅ 3 Minor |
| 3 | read_file/write_file | eca571d | +2=5 | ✅ 5 Minor |
| 4 | fetch_url | b0d63ce | +1=6 | ✅ A |
| 5 | run_shell | d1dda0d | +1=7 | ✅ A |

**Task 2 后的意外**：发现 `__init__.py` 文件未被 git 跟踪——因为 Task 0 时 .gitignore 的 `src/` 误忽略了它们，Task 1 修正了规则但文件没补提交。我（调度员）直接修复：`git add` + commit `355b105`。这是调度员做 git 跟踪修复（非代码修复）的合理场景。

**教训**：.gitignore 的 `src/` 会匹配任意层级的 src/ 目录。要锚定根目录用 `/src/`。这个坑在 Task 0 埋下，Task 1 才暴露——说明预审没覆盖 .gitignore。

---

### Task 6：Guardrail 门控（标记了集成问题）

**实现**：policy.yaml + guardrail.py + 3 个测试。deny rm -rf、ask_user write_file、allow fetch_url。

**实现者标记的集成问题**（重要）：
> ask_user 用 input()，在非交互环境（Agent 自主运行时）会 EOFError

这个问题在 Task 6 不影响测试（测试用 fetch_url 走 allow 规则，不触发 input），但**Task 9 集成时会暴露**。我记入账本：
```
Task 6: important (deferred to Task 9): ask_user uses input() which EOFErrors
```

**教训**：subagent 的"顾虑"不是噪音——它是跨 Task 的集成预警。调度员要把它记入账本，在相关 Task 的 dispatch 里携带。

---

### Task 8：Harness 装配（集成点）

**为什么重要**：Harness 把前面所有零件（Tool/ToolRegistry/Guardrail/Tracer）组装起来。如果接口不对，这里会暴露。

**关键实现**：
- `_resolve_env(value)`：递归把 `${VAR}` 替换为环境变量值
- 工具装配：`importlib.import_module(module)` → `getattr(factory)` → 调工厂
- make_file_tools 需要 strategies_dir 参数（特判），其他工厂无参

**审查**：规格 ✅ 质量 ✅。_resolve_env 递归正确，工具工厂参数对，agent.yaml 无硬编码 key。

---

### Task 9：AgentLoop 核心循环（最重要 + 唯一触发修复循环）

这是整个 Agent 的心脏，也是唯一发现 Important 问题的 Task。

#### 9.1 首次实现

实现者按 brief 逐字写了 AgentLoop，加了 EOFError 防护（Task 6 标记的问题）。2 个测试通过，commit `3500457`。

**实现者标记的顾虑**（关键）：
> 当 LLM 返回 tool_calls 时，context 里追加的 assistant 消息只有 content，没有 tool_calls 字段。真实 OpenAI API 要求带 tool_calls 的 assistant 消息必须含该字段。

#### 9.2 审查发现 2 个 Important

审查 subagent 发现：

**问题 1（Important）**：assistant 消息缺 tool_calls 字段
- 代码：`context.append({"role":"assistant","content":text})`
- 真实 LLM 必失败：OpenAI 要求有 tool_calls 的 assistant 消息必须含 tool_calls 字段
- mock 测试不覆盖（mock 不校验 context 结构）

**问题 2（Important）**：多 tool_call 时 assistant 消息被重复追加
- 在 for 循环内每个 tool_call 都 append 一次 assistant 消息
- 违反 OpenAI 消息结构（应一次 assistant + 多个 tool 结果）

#### 9.3 修复循环第 1 轮

**恢复原实现者**（task_id 复用同一 subagent 会话），给它：
1. 两个 Important 发现的原文
2. 具体修复要求：
   - for 循环**之前**一次性追加含 tool_calls 的 assistant 消息
   - for 循环内**不再追加** assistant 消息，只追加 tool 结果
   - 每个 tool_call 都要有对应 tool 结果（含被拒绝的）
3. 追加一个测试验证 tool_calls 字段存在

**修复实现**（commit `e82953d`）：
```python
# for 循环前，一次性追加
context.append({
    "role": "assistant",
    "content": text,
    "tool_calls": [{"id": tc["id"], "type": "function",
                    "function": {"name": tc["name"],
                                 "arguments": json.dumps(tc["arguments"])}}
                   for tc in tool_calls]
})
# for 循环内，只追加 tool 结果
for tc in tool_calls:
    # ... 门控 + 执行 ...
    context.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
```

#### 9.4 范围复审

生成修复 diff 的 review 包（`3500457..e82953d`），派复审 subagent。复审只看修复 diff，裁定每个发现 ADDRESSED/NOT ADDRESSED + 有无新破坏。

**结论**：两个发现均 **ADDRESSED**，无新破坏。新增测试有效验证 tool_calls 字段。

**记账本**：
```
Task 9: fix round 1/5 (2 addressed, 0 open; commits 3500457..e82953d)
Task 9: complete (commits 7004735..e82953d, review clean after fix)
```

#### 9.5 教训

1. **mock 测试的盲区**：mock LLM 不校验 context 结构，所以"assistant 消息缺 tool_calls"这种真实 API 才暴露的问题，测试抓不到。审查 subagent 凭规范知识抓住了它。
2. **brief 本身可能有 bug**：两个 Important 都源自 PLAN.md 的 brief 代码。subagent 逐字照搬，把 brief 的 bug 也搬进来了。审查是兜底。
3. **修复循环的高效**：恢复原实现者（它记得自己的代码）+ 给具体修复要求 = 1 轮搞定。不需要换更强的模型。

---

### Task 11：爬虫适配（改 JS 代码）

**特殊点**：这是唯一改爬虫代码的 Task（符合适配原则：改爬虫适配 Agent）。crawler/ 有自己的 git，所以提交在 crawler 仓库。

**实现者还修正了 brief 的变量重名**：brief 代码用 `const existing`，但外层 1185 行已声明同名变量，会 SyntaxError。实现者改为 `agentStrategy`。

**教训**：brief 里的代码是"参考实现"，不是圣旨。subagent 遇到实际冲突时应当修正——这是合理的主动行为。

---

### 最终全分支审查

所有 Task 完成后，派最终审查 subagent 审整个分支（13 commit）：

```bash
bash .../scripts/review-package explorer-agent/PLAN.md 2f1aee5 HEAD
# 13 commit, 36KB diff
```

**结论**：✅ 批准合并。SPEC 7 组件全覆盖，6 验收标准达成，无 Critical/Important。M1（.env.example 机器路径）顺手修为通用占位。

---

## 四、用户确认后的精修（refine）

用户审阅后指出我做了太多假设。逐个确认后，派 subagent 统一应用：

| 改动 | 文件 | 内容 |
|------|------|------|
| A1 加策略示例 | rules/AGENTS.md | 末尾加完整 JSON 示例 |
| A2 极简 system_prompt | harness.py | 保持一句（确认不改） |
| A3 write_file 路径沙箱 | guardrail.py + policy.yaml | 策略目录内 allow，外 ask_user |
| A4 goal 加具体路径 | main.py | goal 含 `{STRATEGIES_DIR}/{domain}.json` |
| B2 fetch_url timeout | web_tools.py | 15→20s |
| B3 run_shell timeout | shell_tools.py | 60→300s |
| B4 max_tokens | llm/client.py | 4096 |
| B5 temperature | llm/client.py | 0.3 |
| C3 read_file 限制 | policy.yaml | 项目外 ask_user |
| C5 LLM 重试 | llm/client.py | 失败重试 1 次 |
| C7 trace_id 微秒 | tracer.py | 秒级→毫秒级 |

commit `4531b41`，21 测试通过（新增 1 个 write_inside_strategies 测试）。

---

## 五、关键教训总结

| 教训 | 出处 | 启示 |
|------|------|------|
| .gitignore `src/` 误忽略子目录 | Task 0→1 | 用 `/src/` 锚定根目录 |
| mock 测试不校验 context 结构 | Task 9 | 审查要凭规范知识补 mock 的盲区 |
| brief 可能有 bug | Task 9, 11 | subagent 逐字照搬会把 brief 的 bug 搬进来，审查是兜底 |
| ask_user input() 在非交互环境 EOFError | Task 6→9 | 跨 Task 集成问题要记账本，在相关 Task 携带 |
| 账本防上下文丢失后重复执行 | 全程 | 进度记文件，不记脑子里 |
| 调度员不做代码修复 | 全程 | 修复走 subagent + 复审，调度员只做 git 跟踪修复 |
| subagent 能发现 brief 外的问题 | Task 1 | 独立上下文带新鲜眼光，是价值不是噪音 |

---

## 六、怎么复现

1. 克隆仓库，`cd explorer-agent`
2. `pip install -r requirements.txt`
3. `python -m pytest tests/ -v` → 21 passed
4. 设环境变量（见 AGENT_STRUCTURE.md 第四节）
5. `python main.py "探索 https://cs.nju.edu.cn/ 的通知公告入口"`
6. 查 `crawler/data/strategies/cs.nju.edu.cn.json` + `explorer-agent/traces/`

SDD 工作区在 `.superpowers/sdd/PLAN/`，含所有 brief/report/review/diff 文件，可逐个翻阅对照本教程。
