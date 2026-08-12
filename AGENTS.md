# AGENTS.md — opencode 协作规则

> 本文件由 opencode 每轮自动读取，是 AI 助手的持久指令。
> 用户指令 > 本文件 > Superpowers skills > 默认行为。
> 最后更新：2026-08-06

---

## A. 工作纪律

1. **禁止硬编码** — 路径、密钥、URL 全部通过环境变量或 `${VAR}` 占位符，绝不写死在代码里。
2. **不假设而是询问** — 不确定时用 question 工具问用户，不猜路径、名称、偏好。
3. **较大改动后提交** — 每完成一次有意义的改动（新增文件、修复 bug、重构等）即提交，不等用户催。
4. **注释恰到好处** — 遵循通用最佳实践：保证可读性，不冗余，不缺失。该加时加，不该加时不加。
5. **回复详略得当** — 教学场景（写教程、解释架构）详细展开；解释自己刚做的操作时正常即可；不强制简洁。

## B. 文档维护

6. **随时完善文档** — 每次改动后同步更新以下文档。**若后续新增需要维护的文档，在此处补充**：
   - `AGENT_LOG.md` — 开发日志（格式见第 7 条）
   - `AGENT_STRUCTURE.md` — 结构详解
   - `explorer-agent/MANUAL_CHECKS.md` — 验收清单
   - `SPEC.md`、`PLAN.md`、`SPEC_PROCESS.md`、`REFLECTION.md` — 大作业交付物（见 H 节）
7. **AGENT_LOG 格式（大作业要求）** — 按时间顺序记录关键节点，每条包含：
   - 时间戳与 task 编号（如 `2026-08-06 T4`）
   - 触发的 Superpowers 技能（如 brainstorm / TDD / subagent-driven-development）
   - 关键 prompt / context 配置（如 goal 内容、约束条件）
   - subagent 输出的关键片段或 commit hash
   - 人工干预（改了什么、为什么）
   - 学到的教训
   - 保留 `[AI]`/`[人]`/`[AI+人]` 标注，合并简短交流，不过度合并。

## C. Superpowers 强制

8. **brainstorm** — 任何创造性工作前必须用（创建功能/组件/修改行为）。
9. **systematic-debugging** — 修 bug 前必须用。
10. **verification-before-completion** — 声称完成前必须用（跑测试/lint）。
11. **test-driven-development** — 实现功能前必须用，红→绿→重构，不接受先实现再补测试。

## D. 安全与凭据

12. **不 echo 密钥** — 检查 .env 时只判断非空，不打印值。
13. **不暴露密钥** — 代码中不 log secrets，不 commit 密钥（含 git 历史）。
14. **凭据安全存储（大作业必做）** — key 绝不硬编码进源码/提交进 Git/写入日志或 history。至少实现一种安全存储：操作系统钥匙串 / 加密文件 / 带主密码的密钥管理。`.env` 仅作为加载来源（明文风险须在 SPEC 安全节说明）。首次运行须引导用户安全录入 key（隐藏输入），支持查看 / 更新 / 清除（查看状态时不得回显明文）。

## E. 代码约定

15. **先检查库可用性** — 用库前先看 `package.json`/`requirements.txt`，不假设可用。
16. **遵循现有约定** — 模仿已有代码风格，用已有库和模式。
17. **不猜测 URL** — 除非确定是编程相关。

## F. 项目特定

18. **Agent 是锚点** — Agent 架构严格遵循 `explorer-agent/SPEC.md`，不偏离；Agent 与 crawler 接口不匹配时，改 crawler 不改 Agent。
19. **MVP 范围** — 不加 MCP/Skill/Hooks/Sandbox/Memory/SubAgent/RAG/compact，除非用户明确要求。

## G. 执行偏好

20. **默认 subagent-driven 执行** — 有实现计划时，按 subagent-driven-development skill 每 Task 派一个新 subagent，Task 间 controller 复核。
21. **子 Agent 行为记入日志** — 每个 subagent 的任务、commit、测试结果、复核结论简记入 `AGENT_LOG.md`。
22. **小改动减仪式** — 小改动可跳过 brainstorm→spec→plan→逐级确认的繁琐流程，执行前问一句即可；用户不认可会在询问时提出。大改动仍走完整流程。
23. **测试范围** — 改动时默认只测新功能（focused test），不跑全量测试；确需全量测试时先问用户是否允许。
24. **耗时命令交由用户手动执行** — 后续遇到需要长时间运行的命令（如安装大型依赖、构建镜像、下载浏览器等），先跳过该步骤，把其他任务完成后再停止并总结，告诉用户要手动执行什么、测试什么。不要自行尝试下载/安装大型依赖。

## H. 大作业交付要求（AI4SE 期末项目 · B 类应用项目）

> 本项目将作为 AI4SE 期末大作业提交。以下要求全部照常适用（B 类不含 harness 内核/mock-LLM/机制演示，但本项目**含自研 agent 部分**，须满足 B.2：主循环/工具分发/治理护栏自研，移除真实 LLM 后仍能用确定性单元测试验证）。

25. **七步 Superpowers 全流程** — brainstorm → writing-plans → using-git-worktrees → subagent-driven/executing-plans → TDD → requesting-code-review → finishing-a-development-branch。**如实遵循**；合理偏离必须在 AGENT_LOG 记录并解释。在 SPEC 与 PLAN 完成并通过冷启动验证前，禁止写实现代码。
26. **SPEC.md（10 节）** — 问题陈述 / 用户故事≥5(INVEST) / 功能规约(输入-行为-输出-边界-错误处理) / 非功能需求(性能-安全含凭据威胁模型-可用性-可观测性) / 系统架构(组件图-数据流-外部依赖) / 数据模型 / 凭据与分发设计 / 技术选型与理由 / 验收标准 / 风险与未决问题。含 agent 部分须在 SPEC 说明 agent 边界与"无 LLM 可确定性测试"的机制设计。
27. **PLAN.md** — task 级颗粒度（每 task 可由单个 subagent 一次会话完成），每 task 含目标/文件/实现要点/**验证步骤（含失败测试）**，显式标出依赖与可并行部分。**持续更新**：每完成一个 task 即标记完成并附 commit hash。
28. **SPEC_PROCESS.md** — 记录 brainstorm 协作过程：≥3 轮关键迭代对话节选与你的处理决策、AI 建议你采纳/推翻项及原因、反思 brainstorming 的优缺。
29. **冷启动验证（必做）** — 用**与主开发 agent 不同类型**的 agent，**新 session**、不导入任何历史/memory、仅提供 SPEC+PLAN、从 PLAN 选 1-2 task 自主推进，"不确定即暂停询问"。记录到 SPEC_PROCESS：它停在哪、暴露了哪些 spec 缺陷、哪些解读与你原意不符、你据此做了哪些修订（含前后 diff）。
30. **两阶段评审** — 每个 task 完成后先 spec 合规检查 → 再代码质量检查。Critical 必须修复才能进入下一 task。`finishing-a-development-branch` 决定 merge/PR/保留/丢弃。
31. **git worktrees 隔离 + PR 工作流** — 每个独立功能/大模块开一个 worktree 对应一个 PR；拒绝单次 commit 提交全部代码；commit/PR 描述标注由哪个 subagent 完成、人工修改了哪些部分。
32. **测试与 CI（必做）** — 可一键运行的测试命令（`make test` 或等价），覆盖核心功能；配置 `.gitlab-ci.yml` 含名为 `unit-test` 的 job，每次 push 自动跑，**末次必须 pass**。含 agent 部分须保证核心机制用 mock/stub LLM 写确定性单元测试。
33. **分发（必做，容器/二进制/包任选其一）** — 单条命令可构建 + 单条命令可运行；README 写清：获取方式、运行命令、key 在目标机安全配置方式、已知限制（平台/架构/依赖前提）。
34. **README 必备章节** — 项目简介、安装、运行、分发命令、目录结构、安全边界说明。
35. **AGENT_LOG 全流程证据** — 按第 7 条格式记录整个实现过程（时间戳+task+技能+prompt/subagent/人工干预+教训），这是"过程证据"核心。
36. **REFLECTION.md** — 1500-2500 字反思报告（哪些技能最有用/哪些形式大于实质、TDD 在 AI 协作下是阻碍还是放大器、subagent 能自主运行多久、最优 task 颗粒度、SPEC/PLAN 质量如何影响实现质量、最有效 prompt 策略、凭据与分发迫使你想清了什么、重做会改什么、对 Superpowers 的批判）。
37. **待办防遗忘** — 用户一次提出多条任务、我只处理其中部分时，把**未处理项**写入 `待办.md`（含上下文污染风险：分批次处理时，未办事项若不记录，后续可能遗忘）。每个待办项需足够具体（含做什么/为什么/涉及文件），完成即勾掉。
