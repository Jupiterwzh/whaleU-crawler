# 蓝鲸U — 南京大学通知公告多 Agent 协作系统

> 版本 3.0 | 更新：2026-08-12

基于 harness 工程的多 Agent 协作系统：自动探索 NJU 各院系网站、生成爬取策略、抓取通知、建立 RAG 知识库，并用自然语言查询通知。

| 部分 | 目录 | 语言 | 职责 |
|------|------|------|------|
| 爬虫 | `crawler/` | JavaScript | 按策略爬取网页、提取通知、存储 JSONL |
| 策略 Agent（内层） | `explorer-agent/` | Python | 探索网站、生成/管理爬取策略 |
| 查询 Agent（外层） | `query-agent/` | Python | 管理 RAG 与爬虫：检索回答、不足则调爬虫补充 |
| RAG 管理 Agent | `rag-manager/` | Python | 入库后自动触发：赋予通知有效时间、重建索引 |
| RAG 存储（公共） | `shared/rag/` | Python | JSONL 文档库 + 倒排索引（current/archive + 有效时间） |

```
whaleU-crawler/
├── crawler/                  # JS 爬虫（执行者）
│   └── src/collectors/collector.js
├── explorer-agent/           # 内层策略 Agent（独立 harness）
│   ├── main.py               # 策略 Agent 入口（三段式）
│   ├── src/{harness,agent_loop,llm,tools,guardrail,tracer,filestore,preflight,postflight,keys}
│   ├── rules/AGENTS.md       # Agent 行为规则
│   └── guardrails/           # 安全门控策略
├── query-agent/              # 外层查询 Agent（独立 harness，真复制内核）
│   ├── query.py              # 查询 Agent 入口
│   ├── webui.py              # 单页表单 WebUI（http://localhost:8000）
│   ├── src/{harness,agent_loop,llm,tools,guardrail,tracer,keys}
│   ├── rules/query_AGENTS.md # 查询 Agent 规则
│   └── SPEC.md               # 外层 Agent 设计
├── rag-manager/              # RAG 管理 Agent（入库后自动触发）
│   ├── rag_manager.py        # 有效时间赋予 + 索引重建入口
│   ├── src/                  # 独立 harness 内核（真复制）
│   └── SPEC.md
├── shared/rag/               # RAGStore + validity 判定（公共位置）
├── data/                     # FileStore 目录（策略/备份/暂存/crash，从 STRATEGIES_DIR 推导）
├── SPEC.md                   # 大作业交付物：设计规格
├── PLAN.md                   # 大作业交付物：实现计划
├── SPEC_PROCESS.md           # 大作业交付物：过程记录
├── REFLECTION.md             # 大作业交付物：反思报告
├── Dockerfile / Makefile
├── .gitlab-ci.yml            # CI：unit-test job
├── AGENTS.md / AGENT_LOG.md / README.md
└── SPEC.md / PLAN.md / SPEC_PROCESS.md / REFLECTION.md
```

## 快速开始

### 1. 配置凭据（安全存储，非明文）

```bash
cd explorer-agent
python -m src.keys set    # 引导隐藏录入 key → 存入系统钥匙串
# 或用环境变量：export LLM_API_KEY=$CHERRYIN_API_KEY
```

### 2. 查询通知（外层查询 Agent）

```bash
cd query-agent
python query.py "计算机学院最近有什么通知"
```

### 3. 生成/更新策略（内层策略 Agent）

```bash
cd explorer-agent
python main.py "探索 https://cs.nju.edu.cn/ 的通知公告入口"
```

### 4. 爬虫（已有策略时直接爬取）

```bash
cd crawler
node src/collectors/collector.js --site https://cs.nju.edu.cn/ --days 365
```

### 5. 测试

```bash
make test    # 或 cd explorer-agent && python -m pytest -q
```

## 协作模式

- **模式 A（爬虫入口）**：`node collector.js --site <url>` 无策略 → 自动调策略 Agent → 继续爬取。
- **模式 B（策略 Agent 入口）**：`python main.py "探索 X"` → 前导检查 → Agent 生成 → 交互确认 → 后导保存。
- **模式 C（查询 Agent 入口）**：`cd query-agent && python query.py "问题"` → RAG 检索 → 不够则调爬虫补充入库 → 回答。

## 分发（Docker）

```bash
docker build -t whalequery .
docker run -v $PWD/query-agent/.env:/app/query-agent/.env \
  -e DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY \
  whalequery "计算机学院最近有什么通知"
```

> 说明：Docker/Linux 下 keyring 可能无系统后端，key 用环境变量传入；钥匙串方案适用于本机（macOS/Win/Linux Desktop）。

## 测试与 CI

- 一键测试：`make test`
- CI：`.gitlab-ci.yml` 定义 `unit-test` job，push 自动跑
- 核心机制（主循环/工具分发/guardrail/RAG）用 mock/stub LLM 做确定性单元测试

## 环境变量

| 变量 | 说明 |
|------|------|
| `LLM_BASE_URL` | LLM 端点 |
| `LLM_API_KEY` | LLM 密钥（可用钥匙串替代） |
| `LLM_MODEL` | 模型名 |
| `STRATEGIES_DIR` | 策略目录 |
| `CRAWLER_SCRIPT` | 爬虫脚本路径 |
| `NJU_BROWSER_DIR` | NJU 浏览器服务目录 |
| `RAG_DIR` | RAG 存储目录（默认从 STRATEGIES_DIR 推导） |

## 安全边界

- 凭据：key 走系统钥匙串（`src/keys.py`）或环境变量，`.env` 为明文且被 gitignore，SPec 安全节有威胁模型
- 门控：Agent 工具调用经 guardrail 策略（危险操作 deny/ask_user）
- 注入：用户反馈注入 LLM 时有边界标记，防 prompt 注入
- 崩溃：strategy/crash 文件原子写，防中断截断

## 依赖

- **Node.js 18+**（爬虫）
- **Python 3.11+**（Agent）
- 爬虫：无外部 npm 依赖
- Agent：`openai` / `pyyaml` / `httpx` / `pytest` / `python-dotenv` / `keyring`
