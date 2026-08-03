# SESSION_HANDOFF — 会话交接文档

> 新 opencode 窗口读此文件 + AGENTS.md 即可恢复完整记忆。
> 最后更新：2026-08-04

---

## 项目概述

**whaleU-crawler**：南京大学通知公告智能爬虫。两个并行组件：
- **explorer-agent**（Python）：探索 NJU 网站结构，生成爬取策略 JSON
- **crawler**（JavaScript）：用策略 JSON 爬取通知，输出 JSONL

Agent 通过 `run_shell` 调用爬虫；爬虫无策略时通过 `spawnSync` 委托 Agent 生成策略。

## 当前状态

- ✅ Agent 全部代码实现完毕（13 个 Task，21 个测试通过）
- ✅ 文档齐全：SPEC.md / PLAN.md / AGENT_STRUCTURE.md / SDD_TUTORIAL.md / MANUAL_CHECKS.md / AGENT_LOG.md
- ✅ 仓库合并完成（单一 git 仓库跟踪 explorer-agent/ + crawler/ + nju-browser/）
- ✅ .env 修复完成（6 个环境变量三层验证通过）
- ✅ AGENTS.md 规则文件已创建（18 条规则，opencode 每轮自动读取）
- ⏳ **待做：6 项手动验收**（见 `explorer-agent/MANUAL_CHECKS.md`）

## 下一步：手动验收

按 `explorer-agent/MANUAL_CHECKS.md` 顺序执行 6 项检查：

1. **检查 1**：Agent 探索 cs.nju.edu.cn 并生成策略（核心验收）
2. **检查 2**：爬虫用 Agent 生成的策略爬取通知
3. **检查 3**：移走策略文件，爬虫自动调起 Agent（模式 A）
4. **检查 4**：Guardrail 拦截 `rm -rf` 危险操作
5. **检查 5**：traces/ 轨迹文件可审计
6. **检查 6**：src/ 无硬编码 key 或绝对路径

每步的命令、预期结果、确认项都在 MANUAL_CHECKS.md 里。

## 环境准备

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent
set -a && source .env && set +a   # 必须同终端 source，Python 不自动加载 .env
```

验证环境变量生效（三层，不打印 key）：

```bash
python -c "
import os
from src.harness import Harness
from src.llm.client import LLMClient
for v in ['LLM_API_KEY','LLM_BASE_URL','LLM_MODEL','STRATEGIES_DIR','CRAWLER_SCRIPT','NJU_BROWSER_DIR']:
    print(f'  {v}: {\"✓\" if os.environ.get(v) else \"✗\"}')
h = Harness.from_yaml('agent.yaml')
print('  Harness: ✓')
c = LLMClient()
print('  LLMClient: ✓')
"
```

## 关键文件索引

| 文件 | 作用 |
|------|------|
| `AGENTS.md` | opencode 协作规则（18 条，自动读取） |
| `AGENT_LOG.md` | 完整开发日志（8.03-8.04，4 个会话） |
| `AGENT_STRUCTURE.md` | Agent 逐文件结构详解 |
| `SDD_TUTORIAL.md` | SDD 实现全过程教程 |
| `explorer-agent/SPEC.md` | Agent 设计规格 |
| `explorer-agent/PLAN.md` | 13 Task 实现计划（已完成） |
| `explorer-agent/MANUAL_CHECKS.md` | 6 项手动验收清单（**下一步做这个**） |
| `explorer-agent/agent.yaml` | Agent 声明式配置（`${VAR}` 占位） |
| `explorer-agent/rules/AGENTS.md` | Python Agent 行为规则（Harness 加载） |
| `explorer-agent/guardrails/policy.yaml` | 安全门控策略 |
| `explorer-agent/src/` | Python 源码（harness/agent_loop/llm/tools/guardrail/tracer） |
| `explorer-agent/main.py` | 入口（`--explore-only` 模式 A / 直接 goal 模式 B） |
| `crawler/src/collectors/collector.js` | 爬虫主文件（无策略时委托 Agent） |
| `nju-browser/` | NJU 浏览器服务（Puppeteer + Chrome，Agent 通过 run_shell 调用） |

## 规则提醒

详见 `AGENTS.md`（opencode 自动读取）。核心几条：
- 禁止硬编码 key/路径，全部环境变量或 `${VAR}`
- 不确定时用 question 工具问，不猜
- 较大改动后即提交
- 修 bug 前用 systematic-debugging，声称完成前用 verification-before-completion
- Agent 架构不偏离 SPEC.md，接口不匹配时改 crawler 不改 Agent
