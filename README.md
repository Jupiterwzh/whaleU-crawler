# 蓝鲸U — 南京大学通知公告智能爬虫

> 版本 2.0 | 更新：2026-08-03

自动发现、爬取、汇总南京大学各院系网站的通知公告，输出结构化 JSONL 数据。项目由**并列的两部分**组成：

| 部分 | 目录 | 语言 | 职责 |
|------|------|------|------|
| 爬虫 | `crawler/` | JavaScript | 按策略爬取网页、提取通知、存储 JSONL |
| 探索 Agent | `explorer-agent/` | Python | 探索网站结构、生成爬取策略（Harness Engineering） |

```
whaleU-crawler/
├── crawler/              # JS 爬虫（执行者）
│   ├── src/{collectors,explorers,analyzers,strategies}
│   ├── data/strategies/   # 策略文件（Agent 写、爬虫读）
│   └── browser/           # 浏览器服务
├── explorer-agent/       # Python Agent（探索者，生成策略）
│   ├── agent.yaml         # 声明式总配置
│   ├── src/{harness,agent_loop,llm,tools}
│   └── SPEC.md            # 设计规格
├── src/                  # 暂留（浏览器模式爬虫 + 旧 llm.js，待清理）
├── docs/
├── AGENT_LOG.md          # 开发过程记录（AI 行为 + 人工决定）
├── notes.md              # Harness 工程理论
├── 流程参考.md            # Agent 需求规格
├── 教程.md               # Agent 搭建教程
└── opencode.json
```

## 快速开始

### 爬虫（已有策略时直接爬取）
```bash
cd crawler
node src/collectors/collector.js --site https://cs.nju.edu.cn/ --days 365
```

### 探索 Agent（生成策略）
```bash
# 配置环境变量（绝不硬编码 key）
export LLM_BASE_URL=https://open.cherryin.cc/v1
export LLM_API_KEY=$CHERRYIN_API_KEY
export LLM_MODEL=deepseek/deepseek-v4-flash(free)
export STRATEGIES_DIR=$(pwd)/crawler/data/strategies
export CRAWLER_SCRIPT=$(pwd)/crawler/src/collectors/collector.js

cd explorer-agent
python main.py "探索 https://cs.nju.edu.cn/ 的通知入口"
```

## 协作模式

- **模式 A（爬虫入口）**：`node collector.js --site <url>` 无策略 → 自动调 Agent 生成策略 → 继续爬取。
- **模式 B（Agent 入口）**：`python main.py "探索并爬取 X"` → Agent 生成策略 → 调爬虫执行 → 汇报。

## 文档

| 文档 | 说明 |
|------|------|
| `explorer-agent/SPEC.md` | Agent 设计规格说明书 |
| `AGENT_LOG.md` | 开发过程记录（复习/教师检查用） |
| `流程参考.md` | Agent 需求规格（Cherry Agent Framework） |
| `教程.md` | Agent 搭建教程 |
| `notes.md` | Harness 工程理论 |
| `crawler/` 内各 .md | 爬虫详细文档 |

## 环境变量（绝不硬编码）

| 变量 | 说明 |
|------|------|
| `LLM_BASE_URL` | LLM 端点（CherryIN: https://open.cherryin.cc/v1） |
| `LLM_API_KEY` | LLM 密钥（CHERRYIN_API_KEY） |
| `LLM_MODEL` | 模型名（deepseek/deepseek-v4-flash(free)） |
| `STRATEGIES_DIR` | 策略目录（指向 crawler/data/strategies/） |
| `CRAWLER_SCRIPT` | 爬虫脚本路径 |
| `NJU_BROWSER_DIR` | NJU 浏览器服务目录（可选） |

## 依赖

- **Node.js 18+**（爬虫）
- **Python 3.11+**（Agent，环境已有 3.13）
- 爬虫：无外部 npm 依赖（HTTP 模式纯内置模块）
- Agent：`openai` / `pyyaml` / `httpx` / `pytest`
