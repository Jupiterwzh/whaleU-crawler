# AGENT_LOG — 开发过程记录

> 记录 AI 行为、人工决定、关键操作，用于复习与教师检查。
> 格式：按会话倒序，每条标注 [AI] 或 [人] 或 [AI+人]。

---

## 2026-08-03 会话一：项目理解 + 爬虫检查 + Agent 设计

### [AI] 项目通读
- 通读全部文档：README.md、流程参考.md、教程.md、AGENT_REQUIREMENTS.md、notes.md、SPEC.md、AGENTS.md、context-pack.md 等。
- 通读全部代码：crawler（原 standalone）的 collector.js / site-explorer.js / analyzer.js / strategy-manager.js；src/crawler-core.js；agent-harness 的 base-agent/crawler-agent/explorer-agent；src/agent/llm.js。

### [AI] 爬虫检查结论
- 真正完整的爬虫在 `standalone/`（现改名 `crawler/`），5 个核心文件 `node --check` 全通过。
- collector.js（1322 行）：6 种提取模式+置信度去重、文章提取、BFS 全站探索、策略管理，功能完整。
- 发现问题：① 无 node_modules（@anthropic-ai/sdk 未装，Claude 模式会报错，但 OpenAI 兼容模式可用）；② site-explorer.js:304 重复条件 bug；③ LLM 路径脆弱；④ 未做运行时测试。
- agent-harness/ 确认不可用：crawler-agent.js 的 crawlSite() 是桩，extractNotices() 只有 1 种模式（crawler 有 6 种）；explorer-agent.js 的 analyzeWithLLM() 是 TODO。

### [人] 关键决策（通过问答确认）
1. **Agent 语言**：Python（照搬 流程参考.md/教程.md，环境已有 Python 3.13）。
2. **Agent 职责**：专注网站探索→策略生成（替代 site-explorer.js 的 LLM 分析部分）。
3. **首版范围**：精简 MVP（Harness + AgentLoop + Tools + Guardrail + 入口），不含 MCP/Skill/Hooks/Sandbox/Memory/SubAgent。
4. **Agent 命名**：explorer-agent（体现"探索"职责）。
5. **LLM**：CherryIN 的 deepseek/deepseek-v4-flash(free)，端点 https://open.cherryin.cc/v1。

### [AI] 架构方案
- 方案 B（推荐，已采纳）：原生 Python 工具 + JS 爬虫只管执行。Agent 自带 fetch_url/read_file/write_file/run_shell，自己做探索；JS 爬虫仅在真正爬取时被 run_shell 调用。

### [人] 双向调用设计改进
- 原设计：爬虫无策略→调 Agent；Agent 确认策略后→调爬虫。
- [AI] 评价：存在 crawler→Agent→crawler 递归风险。
- [人] 采纳改进：两种入口模式，禁止回调递归。
  - 模式 A（爬虫入口）：crawler 调 `python main.py --explore-only`，Agent 只写策略+退出，不回调爬虫。
  - 模式 B（Agent 入口）：Agent 编排，单向调爬虫。

### [AI] 执行的清理操作
1. 移除 `agent-harness/`（无效简版 Agent）→ 备份到 /tmp/opencode/agent-harness-backup。
2. 移除 `AGENT_REQUIREMENTS.md`（旧 Agent 需求文档）→ 备份到 /tmp/opencode/。
3. 重命名 `standalone/` → `crawler/`（语义清晰，与 explorer-agent 并列）。验证内部 require 路径仍可用。
4. 移除根 `.claude/`（空目录，Claude Code 残留）→ 备份。
5. 移除 `crawler/.claude/`（Claude Code 配置，opencode 不用）→ 备份。

### [人] 其他要求
- 绝不硬编码 key/路径，全部环境变量/配置。
- 随时更新说明文档；按需完成 context-pack.md、CHECKLIST.md、AGENTS.md、context-snapshot.md。
- 创建本文件（AGENT_LOG.md）记录 AI 行为与人工决定。
- **适配原则**：Agent 严格按 harness 规格（流程参考.md/教程.md/SPEC）实现，是固定锚点；Agent 与爬虫接口不匹配时，改爬虫适配 Agent，不反过来改 Agent 架构。爬虫代码可自由改动。
- **日志粒度**：简单往返对话合并为一条较实质的记录，不过度合并，由 AI 把握程度。

### [人] SPEC 复核
- 反馈"没大问题"，确认通过。仅补充上述适配原则。

### [AI] 产出
- 写入 `explorer-agent/SPEC.md`（设计规格说明书）。
- 创建 `explorer-agent/` 目录骨架（rules/guardrails/src/llm/src/tools/tests/traces）。
- 创建本文件 `AGENT_LOG.md`。

### 待办
- [x] SPEC.md 自审 + 用户复核（已通过，补入适配原则）
- [x] 转 writing-plans 生成实现计划（PLAN.md，13 个 Task，TDD 逐步）
- [ ] 执行实现计划（Task 0-12）
- [ ] 更新 crawler 内文档（context-pack.md/CHECKLIST.md/AGENTS.md 清理旧 agent-harness 引用）
- [ ] 创建 explorer-agent/AGENTS.md（AI 协作指南）
- [ ] 对 cs.nju.edu.cn 跑验收

---

## 2026-08-03 会话二：SDD 执行（Task 0-12）

### [AI-主] SDD 前置设置
- git init 根目录 + .gitignore（排除 crawler/、src/、.env、__pycache__）
- 预装 pip 依赖（openai/pyyaml/httpx/pytest）
- 建 SDD 工作区 .superpowers/sdd/PLAN/ + 进度账本 progress.md
- 预审计划：Task 间接口一致，无冲突

### Task 0: 项目初始化 — 完成
- [AI-主] 直接做脚手架（纯配置文件，无逻辑无测试，避免 subagent 卡权限）
- 产出：requirements.txt、.env.example、.gitignore、__init__.py×4、conftest.py
- 提交 430ad83

### Task 1: LLM 客户端 — 完成
- [AI-sub-实现] 写测试→实现 src/llm/client.py→3 测试通过→提交 dd30420；修正 .gitignore src/→/src/（避免误忽略 explorer-agent/src/）
- [AI-sub-审查] 规格✓ 质量✓，2 Minor（源自 brief，不阻断）：缺 key 测试用裸 try/except 而非 pytest.raises；文本测试隐式依赖 conftest mock_env
- [AI-主] 通过，Minor 记入账本延迟处理

---
