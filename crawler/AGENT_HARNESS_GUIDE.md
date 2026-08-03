# 蓝鲸U — Claude Code Agent 安全配置指南

> 本文档解决两个核心问题：
> 1. 如何为Agent配置独立的API Key，避免与你使用的Key混淆
> 2. 如何防止你向.env填写Key后被Claude Code意外读取导致泄露

---

## 一、问题分析

### 1.1 settings.json的env块与.env文件的关系

Claude Code的`settings.json`中有一个被注释的env块：

```json
// "env": {
//   "LLM_MODE": "env:LLM_MODE",
//   "ANTHROPIC_API_KEY": "env:ANTHROPIC_API_KEY",
//   ...
// },
```

**这个env块的含义**：
- 它是一个"通道声明"，告诉Claude Code哪些环境变量可以通过Harness注入
- 它**不会**自动创建环境变量，只是一个映射配置
- 实际的环境变量读取是通过Node.js的`process.env`

**关键误解**：
- ❌ 启用env块 ≠ 从.env文件读取
- ❌ .env文件 ≠ 会被自动加载
- ✅ Claude Code运行时能访问`process.env`，但.env文件需要代码主动加载

### 1.2 实际风险分析

```
┌─────────────────────────────────────────────────────────────┐
│                    你的环境                                  │
├─────────────────────────────────────────────────────────────┤
│  系统环境变量 (control panel设置)                           │
│  └── ANTHROPIC_API_KEY=sk-xxx-your  ← 你自己用的key        │
│                                                              │
│  .env文件 (standalone/)                                     │
│  └── ANTHROPIC_API_KEY=sk-yyy-agent  ← Agent专用的key       │
│                                                              │
│  Claude Code进程                                             │
│  └── process.env 同时继承系统环境变量和父进程环境变量         │
└─────────────────────────────────────────────────────────────┘
```

**风险点**：
1. Claude Code运行时，`process.env.ANTHROPIC_API_KEY` = 你系统级的key
2. 无论是否启用settings.json的env块，Claude Code都能访问系统环境变量
3. 如果你填写.env文件，Agent代码需要通过`dotenv`库才能读取

### 1.3 为什么当前设计有问题

当前设计中：
- **你**使用的Claude Code和**Agent**使用的Claude Code**共享**同一个key
- 这意味着：
  - 你无法区分哪些请求是你发的，哪些是Agent发的
  - 费用无法分开统计
  - 无法为一个Agent单独禁用或更换key

---

## 二、解决方案

### 2.1 架构设计：双重Claude Code隔离

```
┌─────────────────────────────────────────────────────────────┐
│                    推荐架构                                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  你的环境 (User Environment)                                 │
│  └── ANTHROPIC_API_KEY=sk-xxx-you  ← 你自己的key           │
│                                                              │
│  ┌─────────────────┐      ┌─────────────────┐              │
│  │  Claude Code    │      │  Agent专用      │              │
│  │  (你的会话)      │      │  Claude Code    │              │
│  │                 │      │                 │              │
│  │  - 完整权限     │      │  - 受限权限     │              │
│  │  - 可读.env    │      │  - deny .env    │              │
│  │  - 管理任务     │      │  - 专用key      │              │
│  └─────────────────┘      └─────────────────┘              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 方案一：为Agent创建独立Harness（推荐）

**原理**：
- 创建一个独立的Claude Code项目目录
- 该目录有独立的`settings.json`，配置独立的API Key
- 两个Claude Code实例互相隔离

**步骤**：

1. **创建Agent专用目录结构**：
```bash
D:\PY\lanling-u\
├── standalone\           # 你使用的版本（有完整权限）
│   └── .claude\
│       └── settings.json
└── agent-harness\        # Agent专用（受限）
    └── .claude\
        └── settings.json
```

2. **Agent专用settings.json配置**：
```json
{
  "permissions": {
    "allow": [
      { "prompt": "run node commands", "tool": "Bash" },
      { "prompt": "read any file in project", "tool": "Read" },
      { "prompt": "write js/json/md files", "tool": "Write" },
      { "prompt": "edit existing files", "tool": "Edit" }
    ],
    "deny": [
      { "prompt": "read .env file", "tool": "Read" },
      { "prompt": "read *secret* files", "tool": "Read" },
      { "prompt": "read *.local.json", "tool": "Read" },
      { "prompt": "read *KEY* files", "tool": "Read" },
      { "prompt": "read *PASSWORD* files", "tool": "Read" },
      { "prompt": "read *SECRET* files", "tool": "Read" },
      { "prompt": "read *TOKEN* files", "tool": "Read" }
    ]
  },
  "env": {
    "LLM_MODE": "env:AGENT_LLM_MODE",
    "ANTHROPIC_API_KEY": "env:AGENT_ANTHROPIC_API_KEY",
    "OPENAI_API_KEY": "env:AGENT_OPENAI_API_KEY"
  },
  "project": {
    "name": "蓝鲸U - Agent",
    "description": "南京大学通知公告爬虫Agent"
  }
}
```

3. **在Agent的BAT脚本中设置独立环境变量**：
```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Agent专用环境变量（不会影响系统级key）
set AGENT_LLM_MODE=claude
set AGENT_ANTHROPIC_API_KEY=sk-ant-agent-key-here
set AGENT_OPENAI_API_KEY=

REM 运行Agent专用脚本
node src/explorers/site-explorer.js --continue %1
```

### 2.3 方案二：使用Harness的env注入隔离（高级）

**原理**：
- 在settings.json的env块中指定从特定环境变量读取
- 通过Harness注入，确保Claude Code无法直接访问其他环境变量

**配置**：
```json
{
  "permissions": { ... },
  "env": {
    "LLM_MODE": "env:AGENT_LLM_MODE",
    "ANTHROPIC_API_KEY": "env:AGENT_ANTHROPIC_API_KEY",
    "OPENAI_API_KEY": "env:AGENT_OPENAI_API_KEY"
  }
}
```

**关键点**：
- `"ANTHROPIC_API_KEY": "env:AGENT_ANTHROPIC_API_KEY"` 表示从`AGENT_ANTHROPIC_API_KEY`环境变量读取
- Claude Code运行时，`process.env.ANTHROPIC_API_KEY` = `process.env.AGENT_ANTHROPIC_API_KEY`
- 但Claude Code无法直接访问你系统级的`ANTHROPIC_API_KEY`

---

## 三、防泄露最佳实践

### 3.1 多层防护机制

```
┌─────────────────────────────────────────────────────────────┐
│                    防护层级                                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Layer 1: .gitignore                                         │
│  └── .env 被排除，不会提交到版本库                           │
│                                                              │
│  Layer 2: settings.json deny规则                            │
│  └── AI无法读取 .env 文件                                    │
│                                                              │
│  Layer 3: 环境变量隔离                                       │
│  └── Agent使用独立的AGENT_*环境变量                          │
│                                                              │
│  Layer 4: 定期更换Key                                        │
│  └── 定期更换API Key，减少泄露风险                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 .env文件安全配置

`.env`文件应该：
```bash
# 蓝鲸U - Agent专用环境配置
# 此文件仅供脚本读取，Claude Code无法访问

AGENT_LLM_MODE=claude
AGENT_ANTHROPIC_API_KEY=sk-ant-agent-key
AGENT_OPENAI_API_KEY=
```

**关键**：
- 文件名不要包含`KEY`、`SECRET`等关键词（会被deny规则拦截）
- 使用`AGENT_*`前缀明确标识这是Agent专用

### 3.3 防止意外读取的检查清单

运行以下命令验证：

```bash
# 1. 验证.env被gitignore排除
git check-ignore .env && echo "OK: .env会被忽略"

# 2. 验证deny规则生效（尝试让AI读.env）
# 如果返回"Permission denied"，则规则生效

# 3. 验证环境变量隔离
node -e "console.log('AGENT_ANTHROPIC_API_KEY:', process.env.AGENT_ANTHROPIC_API_KEY)"
```

---

## 四、完整配置步骤

### 4.1 步骤一：创建Agent目录

```bash
cd D:\PY\lanling-u
mkdir agent-harness
cd agent-harness
```

### 4.2 步骤二：复制必要文件

```bash
# 复制源代码（只读）
xcopy /E /I standalone\src src
xcopy /E /I standalone\data data
xcopy /E /I standalone\browser browser

# 复制必要配置（修改后使用）
copy standalone\.claude\.claude.md .\.claude\
copy standalone\.gitignore .
```

### 4.3 步骤三：配置Agent专用settings.json

```json
{
  "permissions": {
    "allow": [
      { "prompt": "run node commands", "tool": "Bash" },
      { "prompt": "read any file in project", "tool": "Read" },
      { "prompt": "write js/json/md files", "tool": "Write" },
      { "prompt": "edit existing files", "tool": "Edit" }
    ],
    "deny": [
      { "prompt": "read .env file", "tool": "Read" },
      { "prompt": "read *secret* files", "tool": "Read" },
      { "prompt": "read *local.json", "tool": "Read" },
      { "prompt": "read *KEY*", "tool": "Read" },
      { "prompt": "read *PASSWORD*", "tool": "Read" },
      { "prompt": "read *SECRET*", "tool": "Read" },
      { "prompt": "read *TOKEN*", "tool": "Read" },
      { "prompt": "read *credential*", "tool": "Read" },
      { "prompt": "run *key* commands", "tool": "Bash" },
      { "prompt": "run *secret* commands", "tool": "Bash" },
      { "prompt": "run *credential* commands", "tool": "Bash" }
    ]
  },
  "env": {
    "LLM_MODE": "env:AGENT_LLM_MODE",
    "ANTHROPIC_API_KEY": "env:AGENT_ANTHROPIC_API_KEY",
    "OPENAI_API_KEY": "env:AGENT_OPENAI_API_KEY",
    "LLM_MODEL": "env:AGENT_LLM_MODEL"
  },
  "project": {
    "name": "蓝鲸U - Agent Runner",
    "description": "南京大学通知公告爬虫 - Agent自动化运行"
  },
  "tools": {
    "node": {
      "enabled": true,
      "cwd": "D:/PY/lanling-u/agent-harness"
    }
  }
}
```

### 4.4 步骤四：创建Agent启动脚本

```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM ========================================
REM  Agent专用环境变量（与你的key隔离）
REM ========================================
set AGENT_LLM_MODE=claude
set AGENT_ANTHROPIC_API_KEY=sk-ant-your-agent-key
set AGENT_OPENAI_API_KEY=
set AGENT_LLM_MODEL=claude-haiku-4-5-20251001

REM ========================================
REM  启动Claude Code Agent
REM ========================================
echo.
echo ==========================================
echo   Blue Whale U - Agent Runner
echo   Mode: %AGENT_LLM_MODE%
echo ==========================================
echo.

claude --project .

pause
```

### 4.5 步骤五：验证隔离效果

```bash
# 在你的环境中
node -e "console.log('Your Key:', process.env.ANTHROPIC_API_KEY)"
# 输出: Your Key: sk-ant-your-personal-key

# 在Agent环境中
node -e "console.log('Agent Key:', process.env.ANTHROPIC_API_KEY)"
# 输出: Agent Key: sk-ant-agent-key
```

---

## 五、故障排除

### 问题1: Agent无法读取环境变量

**检查**：
1. BAT脚本中是否设置了`AGENT_ANTHROPIC_API_KEY`
2. settings.json中是否配置了env映射
3. 环境变量是否在BAT脚本的`set`之后生效

**解决**：
```bat
REM 在BAT脚本开头添加调试
echo AGENT_ANTHROPIC_API_KEY=%AGENT_ANTHROPIC_API_KEY%
```

### 问题2: .env文件被意外读取

**原因**：可能有代码使用`dotenv`库

**检查**：
```bash
grep -r "dotenv" src/
grep -r "require.*env" src/
```

**解决**：
1. 移除`dotenv`依赖
2. 确认settings.json的deny规则包含`.env`

### 问题3: 权限不足

**检查**：settings.json的allow规则

**常见错误**：
- `Permission denied: run node commands` → 添加Bash到allow
- `Permission denied: edit files` → 添加Edit/Write到allow

---

## 六、快速参考

### 6.1 完整文件清单

```
agent-harness\
├── .claude\
│   └── settings.json      # Agent专用Harness配置
├── src\                    # 源代码（只读）
├── data\                   # 数据目录
├── browser\                # 浏览器（可选）
├── 启动Agent.bat           # Agent启动脚本
└── .gitignore
```

### 6.2 环境变量对照表

| 变量 | 你使用的 | Agent使用的 |
|------|---------|------------|
| LLM_MODE | LLM_MODE | AGENT_LLM_MODE |
| API Key | ANTHROPIC_API_KEY | AGENT_ANTHROPIC_API_KEY |
| Model | LLM_MODEL | AGENT_LLM_MODEL |

### 6.3 验证命令

```bash
# 验证环境隔离
node -e "console.log('Your:', process.env.ANTHROPIC_API_KEY ? 'Set' : 'Not set')"
node -e "console.log('Agent:', process.env.AGENT_ANTHROPIC_API_KEY ? 'Set' : 'Not set')"

# 验证deny规则
# 让AI读取.env，应该被拒绝

# 验证gitignore
git check-ignore .env && echo "Protected"
```
