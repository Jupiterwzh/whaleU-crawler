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
└── opencode.json             # opencode 工具配置
```

## 安装

### 1. 前置依赖

- Python 3.11+
- Node.js 18+
- （可选）Docker，用于容器分发

### 2. 安装 Python 依赖

```bash
pip install -r explorer-agent/requirements.txt
pip install -r query-agent/requirements.txt
pip install -r rag-manager/requirements.txt
```

crawler 与 nju-browser 为 Node 原生模块，无第三方依赖（HTTP 模式），无需 `npm install`。

### 3. 配置凭据（根目录集中配置）

**本项目支持「根目录集中配置」**：公共配置写在项目根 `.env`，所有 Agent 自动继承；各 Agent 目录 `.env` 只放"想独立"的键。

**第 1 步：配置根 `.env`（主配置源，推荐）**

```bash
cp .env.example .env
# 编辑 .env：LLM_API_KEY 填入真实 DeepSeek key（或用 ${DEEPSEEK_API_KEY} 引用环境变量）
# 也可用命令引导录入：
python whale-key.py set    # 隐藏录入，写入项目根 .env
```

**第 2 步（可选）：Agent 独立配置**

各 Agent 的 `.env`（`explorer-agent/.env`、`query-agent/.env`、`rag-manager/.env`）只放想独立的键，例如：

```bash
# query-agent/.env —— 给 query-agent 单独指定 key（覆盖根）
LLM_API_KEY=你的独立key
```

**继承规则**（关键）：
- Agent `.env` **没写的键** → 自动继承根 `.env`（改根 → 全局生效）
- Agent `.env` **写了的键** → 覆盖根（该 Agent 独立）
- 路径无需配置：`STRATEGIES_DIR`/`CRAWLER_SCRIPT`/`RAG_DIR` 等留空自动推导到项目内标准位置

**方式 B：命令行查看/清除 key（隐藏输入）**

```bash
python whale-key.py set    # 隐藏录入 key
python whale-key.py get    # 查看状态（只显示长度，不回显明文）
python whale-key.py clear  # 清除 key
python whale-key.py has    # 是否已配置
```

> 说明：无桌面环境（WSL/纯 Linux/Docker）下系统钥匙串可能不可用，`set` 会自动降级写入 `.env`。查看 key 状态始终只显示长度，不回显明文。
>
> **Docker 分发时**：容器挂载的是 `query-agent/.env`，请将根 `.env` 的关键配置同步到 `query-agent/.env`（或直接用 `cp .env query-agent/.env`），详见「分发（Docker）」章节。
>
> 路径无需手动配置：`STRATEGIES_DIR` / `CRAWLER_SCRIPT` / `RAG_DIR` 等未设置时自动推导到项目内标准位置（见各 Agent `.env.example` 注释），仅非标准布局才需指定。

### 4. 验证安装

```bash
make test    # 3 个 Agent + crawler 全量测试
```

---

## 快速开始

### 1. 查询通知（外层分发 Agent）

query-agent 是分发/编排 Agent：RAG 检索 → 不足则检查策略 → 无策略唤起策略 Agent → 调爬虫入库 → 再检索回答。

```bash
cd query-agent
python query.py "计算机学院最近有什么通知"
```

### 2. 生成/更新策略（内层策略 Agent）

```bash
cd explorer-agent
python main.py "探索 https://cs.nju.edu.cn/ 的通知公告入口"
```

### 3. 爬虫（已有策略时直接爬取）

```bash
cd crawler
node src/collectors/collector.js --site https://cs.nju.edu.cn/ --days 365
```

### 4. 运行 WebUI

```bash
cd query-agent
python webui.py 8000
# 浏览器打开 http://localhost:8000
```

### 5. RAG 管理（分配有效时间 + 重建索引）

rag-manager 给通知分配有效时间（过期自动从查询排除）并重建索引。**只处理已入库的待判定文档，不 ingest**。

```bash
# 推荐：通过查询链自动 ingest + 触发 rag-manager
cd query-agent && python query.py "cs.nju.edu.cn 最近有什么通知"

# 或：手动处理已入库的 pending（先 ingest 新爬虫产物再跑）
cd rag-manager && python rag_manager.py
```

> 详见 `rag-manager/README.md`：工作流程、边界（不删文档、过期靠有效时间排除）、常见问题。

## 协作模式

- **模式 A（爬虫入口）**：`node collector.js --site <url>` 无策略 → 自动调策略 Agent → 继续爬取。
- **模式 B（策略 Agent 入口）**：`python main.py "探索 X"` → 前导检查 → Agent 生成 → 交互确认 → 后导保存。
- **模式 C（分发 Agent 入口）**：`cd query-agent && python query.py "问题"` → RAG 检索 → 不足则 `list_sites` 对照候选站点（sites.json 112 站）→ 展示目标 URL 请用户确认（可指正/输入新站点/改 sites.json）→ 检查策略 → 无策略唤起策略 Agent → 调爬虫补充入库 → 再检索回答。关键步骤后交互等待用户（y 继续/新网址换目标/反馈修正/exit）。

## 分发（Docker）

```bash
# 1. 构建镜像（只含代码，不含任何 key）
docker build -t whalequery .

# 2. 配置 key（首次引导录入，隐藏输入；写入项目根 .env）
python whale-key.py set    # 根目录执行，key 写根 .env
#   或手动编辑 .env（根目录集中配置，见「3. 配置凭据」）

# 3. 运行（挂载根 .env，key 不写入镜像、不进命令行）
docker run --rm \
  -v $PWD/.env:/app/.env \
  whalequery "计算机学院最近有什么通知"
```

> **key 配置说明（填一次，Docker 复用）**：
> - 首次用 `python whale-key.py set` 引导录入（隐藏输入），key 写入**项目根 `.env`**（钥匙串不可用时的降级路径，见下）
> - Docker 容器通过 `-v` 挂载宿主机的根 `.env` 到 `/app/.env`，容器内 `load_env` 先读根 `.env`（集中配置），**无需在容器内重复配置**
> - key 全程不出现在命令行 / shell history，不写入镜像（`.dockerignore` 排除 `.env`）
> - 这是容器隔离的正确用法：容器不接触宿主机钥匙串，凭据经挂载文件单向传入

> **已知限制（务必阅读）**：
> - **Docker/Linux 无系统钥匙串后端**：`whale-key.py set` 在无桌面 Linux/WSL/Docker 下会降级写入 `.env`（明文，gitignore 保护）；有桌面环境（macOS/Win）用系统钥匙串。查看 key 状态只显示长度，不回显明文。
> - **explorer-agent（策略生成）无法在 Docker 非交互环境使用**：它需要用户在结构遍历后选择入口、确认策略（`_interactive_input` 在无 stdin 时自动确认 y）。Docker 容器默认只运行 **query-agent 问答链路**；需要交互式策略生成的场景请在宿主机直接运行 `python main.py`。

## 测试与 CI

- 一键测试：`make test`（3 个 Agent + crawler 全量测试）
- CI 双配置：
  - GitHub Actions：`.github/workflows/ci.yml`，定义 `unit-test` job，push 自动跑
  - GitLab CI：`.gitlab-ci.yml`，同样定义 `unit-test` job
- 核心机制（主循环/工具分发/guardrail/RAG）用 mock/stub LLM 做确定性单元测试，无真实 key 也能跑

### 端到端验收

需真实 LLM/网络的端到端验收（策略 Agent→爬虫→RAG 管理→分发 Agent→SSO 共 7 条），见 **`ACCEPTANCE.md`**（含命令、预期、通过判定与结果记录表）。测试 6/7（需登录站点）在 Windows 上执行。

## 环境变量

| 变量 | 说明 |
|------|------|
| `LLM_BASE_URL` | LLM 端点 |
| `LLM_API_KEY` | LLM 密钥（可用钥匙串替代） |
| `LLM_MODEL` | 模型名 |
| `DEEPSEEK_API_KEY` | DeepSeek 官方 key（`.env` 里 `LLM_API_KEY=${DEEPSEEK_API_KEY}` 引用） |
| `STRATEGIES_DIR` | 策略目录 |
| `CRAWLER_SCRIPT` | 爬虫脚本路径 |
| `NJU_BROWSER_DIR` | NJU 浏览器服务目录 |
| `RAG_DIR` | RAG 存储目录（默认从 STRATEGIES_DIR 推导） |

## 安全边界

- 凭据：key 走系统钥匙串（`src/keys.py`，keyring）或环境变量或 `.env`；`.env` 为明文且被 gitignore，SPEC 安全节有威胁模型
- keyring 环境限制：无桌面环境（WSL/纯 Linux/Docker）可能无钥匙串后端，代码自动降级到 `.env` 或环境变量；查看 key 状态只显示长度，不回显明文
- 门控：Agent 工具调用经 guardrail 策略（危险操作 deny/ask_user）
- 注入：用户反馈注入 LLM 时有边界标记，防 prompt 注入
- 崩溃：strategy/crash 文件原子写，防中断截断

## 依赖

- **Node.js 18+**（爬虫）
- **Python 3.11+**（Agent）
- 爬虫（crawler）：无外部 npm 依赖
- Agent：`openai` / `pyyaml` / `httpx` / `pytest` / `python-dotenv` / `keyring`
- nju-browser：`puppeteer`

## 第三方代码与许可证

本项目遵守所用第三方库的许可证，列表如下：

| 依赖 | 用途 | 许可证 |
|------|------|--------|
| [openai](https://pypi.org/project/openai/) | LLM 客户端（DeepSeek 兼容 OpenAI 接口） | Apache-2.0 |
| [PyYAML](https://pypi.org/project/PyYAML/) | 策略/配置解析 | MIT |
| [httpx](https://pypi.org/project/httpx/) | HTTP 客户端 | BSD-3-Clause |
| [pytest](https://pypi.org/project/pytest/) | 测试框架 | MIT |
| [python-dotenv](https://pypi.org/project/python-dotenv/) | `.env` 加载 | BSD-3-Clause |
| [keyring](https://pypi.org/project/keyring/) | 系统钥匙串凭据存储 | MIT |
| [puppeteer](https://github.com/puppeteer/puppeteer) | 浏览器自动化（nju-browser） | Apache-2.0 |

其余代码为项目自研（agent harness、RAG、爬虫、策略生成），无第三方代码引入。
