# 蓝鲸U — 南京大学通知公告智能爬虫

> 版本 2.1 | 更新：2026-08-05

自动发现、爬取、汇总南京大学各院系网站的通知公告，输出结构化 JSONL 数据。

| 部分 | 目录 | 语言 | 职责 |
|------|------|------|------|
| 爬虫 | `crawler/` | JavaScript | 按策略爬取网页、提取通知、存储 JSONL |
| 探索 Agent | `explorer-agent/` | Python | 三段式探索：前导检查→Agent 生成→后导保存 |
| NJU 浏览器 | `nju-browser/` | Node.js | Puppeteer 浏览器服务（Agent 通过 run_shell 调用） |

```
whaleU-crawler/
├── crawler/                  # JS 爬虫（执行者）
│   ├── src/{collectors,explorers,analyzers,strategies}
│   └── data/strategies/      # 策略文件（Agent 写、爬虫读）
├── explorer-agent/           # Python Agent（探索者，Harness Engineering）
│   ├── agent.yaml            # 声明式总配置
│   ├── src/{harness,agent_loop,llm,tools,guardrail,tracer,filestore,preflight,postflight}
│   ├── rules/AGENTS.md       # Agent 行为规则
│   ├── guardrails/           # 安全门控策略
│   └── SPEC.md               # 设计规格
├── data/                     # FileStore 管理目录（备份/暂存/crash，自动从 STRATEGIES_DIR 推导）
│   ├── strategies/           # 标准策略（由 crawler/data/strategies 聚合）
│   ├── backups/              # 策略备份 ≤3/域名
│   └── checkpoints/          # 暂存 + 崩溃恢复
├── nju-browser/              # NJU 浏览器服务（Puppeteer + Chrome）
├── 无关文档/                 # 教程/学习文档（.gitignore 排除）
├── AGENTS.md                # opencode 协作规则
├── AGENT_LOG.md             # 开发过程记录
└── opencode.json
```

## 快速开始

### 1. 配置 .env

复制模板并填入真实值：
```bash
cd explorer-agent
cp .env.example .env
# 编辑 .env：LLM_API_KEY 用 ${CHERRYIN_API_KEY} 引用 WSL 环境变量（不填字面量）
```

### 2. 运行 Agent

```bash
cd explorer-agent
python main.py "探索 https://cs.nju.edu.cn/ 的通知公告入口"
```

流程：**前导检查**（崩溃恢复/暂存/备份/已有策略）→ **Agent 探索**（步进可视化 + 交互确认）→ **后导保存**（备份/替换旧策略）。

### 3. 爬虫（已有策略时直接爬取）

```bash
cd crawler
node src/collectors/collector.js --site https://cs.nju.edu.cn/ --days 365
```

## 协作模式

- **模式 A（爬虫入口）**：`node collector.js --site <url>` 无策略 → 自动调 Agent 生成策略 → 继续爬取。
- **模式 B（Agent 入口）**：`python main.py "探索 X"` → Agent 生成策略 → 交互确认 → 后导保存。

## 环境变量

| 变量 | 说明 |
|------|------|
| `LLM_BASE_URL` | LLM 端点 |
| `LLM_API_KEY` | LLM 密钥（建议 `${CHERRYIN_API_KEY}` 引用 WSL 环境变量） |
| `LLM_MODEL` | 模型名 |
| `STRATEGIES_DIR` | 策略目录（指向 crawler/data/strategies/） |
| `CRAWLER_SCRIPT` | 爬虫脚本路径 |
| `NJU_BROWSER_DIR` | NJU 浏览器服务目录 |
| `DATA_DIR` | 备份/暂存根目录（可选，自动从 STRATEGIES_DIR 推导） |

## 依赖

- **Node.js 18+**（爬虫）
- **Python 3.11+**（Agent，环境已有 3.13）
- 爬虫：无外部 npm 依赖（HTTP 模式纯内置模块）
- Agent：`openai` / `pyyaml` / `httpx` / `pytest` / `python-dotenv`
