# AGENTS.md — opencode 协作规则

> 本文件由 opencode 每轮自动读取，是 AI 助手的持久指令。
> 用户指令 > 本文件 > Superpowers skills > 默认行为。
> 最后更新：2026-08-04

---

## A. 工作纪律

1. **禁止硬编码** — 路径、密钥、URL 全部通过环境变量或 `${VAR}` 占位符，绝不写死在代码里。
2. **不假设而是询问** — 不确定时用 question 工具问用户，不猜路径、名称、偏好。
3. **较大改动后提交** — 每完成一次有意义的改动（新增文件、修复 bug、重构等）即提交，不等用户催。
4. **注释恰到好处** — 遵循通用最佳实践：保证可读性，不冗余，不缺失。该加时加，不该加时不加。
5. **回复详略得当** — 教学场景（写教程、解释架构）详细展开；解释自己刚做的操作时正常即可；不强制简洁。

## B. 文档维护

6. **随时完善文档** — 每次改动后同步更新以下文档。**若后续新增需要维护的文档，在此处补充**：
   - `AGENT_LOG.md` — 开发日志
   - `AGENT_STRUCTURE.md` — 结构详解
   - `explorer-agent/MANUAL_CHECKS.md` — 验收清单
7. **AGENT_LOG 格式** — `[AI]`/`[人]`/`[AI+人]` 标注，合并简短交流，不过度合并。

## C. Superpowers 强制

8. **brainstorm** — 任何创造性工作前必须用（创建功能/组件/修改行为）。
9. **systematic-debugging** — 修 bug 前必须用。
10. **verification-before-completion** — 声称完成前必须用（跑测试/lint）。
11. **test-driven-development** — 实现功能前必须用。

## D. 安全

12. **不 echo 密钥** — 检查 .env 时只判断非空，不打印值。
13. **不暴露密钥** — 代码中不 log secrets，不 commit 密钥。

## E. 代码约定

14. **先检查库可用性** — 用库前先看 `package.json`/`requirements.txt`，不假设可用。
15. **遵循现有约定** — 模仿已有代码风格，用已有库和模式。
16. **不猜测 URL** — 除非确定是编程相关。

## F. 项目特定

17. **Agent 是锚点** — Agent 架构严格遵循 `explorer-agent/SPEC.md`，不偏离；Agent 与 crawler 接口不匹配时，改 crawler 不改 Agent。
18. **MVP 范围** — 不加 MCP/Skill/Hooks/Sandbox/Memory/SubAgent/RAG/compact，除非用户明确要求。
