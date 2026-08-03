# 蓝鲸U — AI 协作指南

> 给后续接手此项目的 AI Agent 阅读
> 最后更新：2026-08-02

---

## 项目目标

**一句话**：南京大学通知公告智能爬虫 — 自动爬取各院系通知，输出结构化 JSONL 数据。

**当前阶段**：Phase 1 (MVP) 完成，目录重构完成，Phase 2 (增强) 待做。

---

## 优先阅读文件（按此顺序）

1. **`context-pack.md`** — 完整上下文总结（含目录结构、模块说明、Harness配置）
2. **`SPEC.md`** — 项目规格说明书
3. **`CHECKLIST.md`** — 验收清单，修改后逐条验证
4. **`src/collectors/collector.js`** — 主爬虫入口
5. **`src/explorers/site-explorer.js`** — 探索Agent
6. **`src/strategies/strategy-manager.js`** — 策略存储

---

## 目录结构

```
standalone/
├── src/
│   ├── collectors/collector.js     # 主爬虫
│   ├── explorers/site-explorer.js  # 探索Agent（核心入口）
│   ├── analyzers/                  # 分析器
│   │   ├── analyzer.js             # 启发式+LLM降级
│   │   └── agent-analyzer.js       # 纯LLM分析
│   ├── strategies/strategy-manager.js  # 策略CRUD
│   └── data/sites.js               # 站点清单
├── data/                           # 数据目录
│   └── strategies/                 # 策略文件
├── .claude/                        # Claude Code配置
│   ├── settings.json               # Harness权限
│   └── CLAUDE.md                   # 项目说明
├── config/.env.example             # 环境模板
├── scripts/                        # 辅助脚本
└── browser/                        # 浏览器服务
```

---

## 常用命令

```bash
# 探索新网站（交互式，需LLM）
node src/explorers/site-explorer.js --url https://jw.nju.edu.cn/

# 继续探索
node src/explorers/site-explorer.js --continue jw.nju.edu.cn

# 列出进行中的探索
node src/explorers/site-explorer.js --list

# 爬取（有策略时直接爬）
node src/collectors/collector.js --site https://cs.nju.edu.cn/ --days 365 --max-pages 5

# 爬取通知列表
node src/collectors/collector.js --notices https://cs.nju.edu.cn/1702/list.htm

# 验证策略
node -e "const sm=require('./src/strategies/strategy-manager'); console.log(sm.listStrategies());"

# 验证语法
node --check src/collectors/collector.js
node --check src/explorers/site-explorer.js

# 验证导入
node -e "require('./src/collectors/collector'); console.log('ok');"
```

---

## 禁止事项

| 禁止 | 原因 |
|------|------|
| ❌ 不读取 `.env` 文件 | 含 API Key，安全风险 |
| ❌ 不读取任何含 `KEY`/`SECRET`/`PASSWORD`/`TOKEN` 的文件 | 安全风险 |
| ❌ 不提交 `.env` 到版本库 | 安全风险 |
| ❌ 不删除 `data/strategies.json` | v2迁移标记 |
| ❌ 不修改 `browser/chrome/` | 浏览器二进制 |
| ❌ 不硬编码凭证 | 必须通过环境变量 |
| ❌ 不引入大型依赖 | 保持轻量 |

---

## 双重隔离架构（重要）

本项目支持**你**和**Agent**使用独立的API Key，避免混淆和泄露风险。

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  你的环境 (User Environment)                                 │
│  └── ANTHROPIC_API_KEY=sk-xxx-you  ← 你自己的key           │
│                                                              │
│  Agent专用环境                                               │
│  └── AGENT_ANTHROPIC_API_KEY=sk-yyy-agent  ← Agent专用key   │
└─────────────────────────────────────────────────────────────┘
```

### 为什么需要隔离？

1. **费用分离**：你发的请求和Agent发的请求使用不同key
2. **权限控制**：可以单独禁用Agent的key而不影响你的使用
3. **审计追踪**：通过key来源区分请求来源

### 配置方法

**详细教程见 `AGENT_HARNESS_GUIDE.md`**

快速配置：
1. 创建 `agent-harness/` 目录
2. 复制 `standalone/src/` 和 `standalone/data/` 到该目录
3. 配置独立的 `.claude/settings.json`（使用 `AGENT_*` 环境变量）
4. 创建Agent启动脚本，设置 `AGENT_ANTHROPIC_API_KEY`

---

**⚠️ 环境变量访问规则**

AI 只能通过以下方式访问环境变量：
- `process.env.LLM_MODE`
- `process.env.ANTHROPIC_API_KEY`
- `process.env.OPENAI_API_KEY`
- `process.env.LLM_MODEL`

绝对禁止：
- 读取 `.env` 文件内容
- 读取任何 `*.local.json`、`*secret*` 文件
- 尝试从文件系统查找 API Key

---

## Harness 配置（.claude/settings.json）

```json
{
  "permissions": {
    "allow": [
      {"prompt": "run node commands", "tool": "Bash"},
      {"prompt": "read any file in project", "tool": "Read"},
      {"prompt": "write js/json/md files", "tool": "Write"},
      {"prompt": "edit existing files", "tool": "Edit"}
    ],
    "deny": [
      {"prompt": "read .env file", "tool": "Read", "reason": "Security: .env contains credentials"},
      {"prompt": "read *secret* files", "tool": "Read", "reason": "Security: secret files may contain credentials"},
      {"prompt": "read *.local.json", "tool": "Read", "reason": "Security: local config may contain credentials"}
    ]
  }
}
```

---

## API Key 配置教学

### 目标
将 API Key 存放在：不被 AI 读取、不被 git 上传、但可被 Agent 使用的文件中。

### 已实现的保护机制

1. **AI 禁止读取**：`settings.json` 中 `deny` 规则阻止 AI 读取 `.env`
2. **Git 忽略**：`.gitignore` 中 `.env` 被排除
3. **代码读取**：Agent 通过 `process.env` 读取，由操作系统提供

### 隔离配置：你的Key vs Agent的Key

**你的Key**（用于直接在命令行运行或与Claude Code对话）：
```bash
# 系统环境变量
LLM_MODE=claude
ANTHROPIC_API_KEY=sk-ant-your-personal-key
```

**Agent专用Key**（用于Agent自动化运行）：
```bash
# Agent环境变量（使用AGENT_前缀）
AGENT_LLM_MODE=claude
AGENT_ANTHROPIC_API_KEY=sk-ant-agent-key
```

详细配置见 `AGENT_HARNESS_GUIDE.md`。

### 配置步骤（基础）

**方式一：系统环境变量（推荐）**
```
Windows → 控制面板 → 系统 → 高级 → 环境变量 → 新建系统变量
LLM_MODE = claude
ANTHROPIC_API_KEY = sk-ant-xxx
```

**方式二：BAT 脚本临时设置**
```bat
@echo off
set LLM_MODE=claude
set ANTHROPIC_API_KEY=sk-ant-xxx
node src/explorers/site-explorer.js --url https://jw.nju.edu.cn/
```

### Agent专用配置（高级）

见 `AGENT_HARNESS_GUIDE.md` 的完整指南。

### 调试 Harness

```bash
# 修改 settings.json 后验证
claude --project .

# 检查 deny 规则是否生效
# 在对话中尝试让AI读 .env，应被拒绝

# 验证环境变量隔离
node -e "console.log('Your:', process.env.ANTHROPIC_API_KEY)"
node -e "console.log('Agent:', process.env.AGENT_ANTHROPIC_API_KEY)"
```

---

## 常见任务指引

### 如何探索新站点？

```bash
# 交互式（推荐）
node src/explorers/site-explorer.js --url https://新站点/

# 非交互式（自动）
node src/collectors/collector.js --site https://新站点/
```

### 如何修复提取不准确？

1. 确认CMS类型：`node src/collectors/collector.js --force-analyze <URL>`
2. 检查 `src/analyzers/analyzer.js` 中对应类型的提取正则
3. 修正后重新验证

### 如何回退策略？

```bash
node src/collectors/collector.js --re-discover cs.nju.edu.cn
```

---

## 文件编码

- `.js` → UTF-8
- `.bat` → GBK（含中文）
- `.json` → UTF-8
