# 蓝鲸U — 项目规格说明书

> 版本：1.1
> 更新：2026-08-02

---

## 1. 项目目标（一句话）

**南京大学通知公告智能爬虫**：自动发现、爬取、汇总南京大学各院系网站的通知公告，输出结构化 JSONL 数据供搜索使用。

---

## 2. 目标用户与使用场景

| 用户 | 场景 |
|------|------|
| 教学项目组员 | 提交蓝鲸U爬虫+Agent作品 |
| 南京大学师生 | 查询各院系最新通知 |
| 后续开发者 | 扩展站点、维护代码 |

**典型场景**：
- 运行 `node src/explorers/site-explorer.js --url https://新站点/` → 交互式探索 → 保存策略
- 已有策略 → `node src/collectors/collector.js --site https://站点/` → 自动爬取

---

## 3. 核心模块

### 3.1 源代码（`src/`）

| 模块 | 路径 | 职责 |
|------|------|------|
| 主爬虫 | `src/collectors/collector.js` | 命令行解析、流程调度、HTTP爬取 |
| 探索Agent | `src/explorers/site-explorer.js` | 多轮交互式网站探索、策略生成 |
| 启发式分析 | `src/analyzers/analyzer.js` | HTTP抓取、CMS检测、SPA检测、分页 |
| AI分析器 | `src/analyzers/agent-analyzer.js` | 纯LLM策略分析（置信度<50%降级） |
| 策略管理 | `src/strategies/strategy-manager.js` | 策略CRUD、草稿确认、v2→v3升级 |
| 站点数据 | `src/data/sites.js` | 130+站点URL清单 |

### 3.2 数据格式

- **策略文件**：`data/strategies/{domain}.json`（v3格式）
- **草稿文件**：`data/strategies/{domain}.draft.json`
- **进行中**：`data/strategies/{domain}.in-progress.json`
- **爬取数据**：`data/records/all_records.jsonl`（JSONL）

### 3.3 依赖关系

```
src/collectors/collector.js
├── src/strategies/strategy-manager.js  → 策略CRUD
├── src/analyzers/analyzer.js          → 启发式分析
│   └── src/analyzers/agent-analyzer.js → LLM降级
├── src/explorers/site-explorer.js     → 探索Agent
└── src/data/sites.js                  → 站点数据

LLM依赖（外部）：
../../src/agent/llm.js → Claude/OpenAI API
```

---

## 4. 不做事项

| 不做 | 原因 |
|------|------|
| 不实现后端服务 | 纯前端工具 |
| 不维护用户数据库 | 数据文件即持久化 |
| 不接入RAG/向量检索 | MVP阶段只做爬取 |
| 不部署到云服务器 | 本地运行 |
| 不写单元测试 | 教学项目，功能验证为主 |
| AI不读取.env文件 | 安全规则 |

---

## 5. 技术约束

| 约束 | 说明 |
|------|------|
| **Node.js 18+** | 运行环境 |
| **纯相对路径** | 无硬编码绝对路径 |
| **HTTP模式** | 默认HTTP抓取，无需浏览器 |
| **本地存储** | 所有数据存 `data/` 目录 |
| **AI降级** | LLM不可用时回退到启发式 |

### LLM配置

```bash
# 环境变量（系统或命令行设置）
LLM_MODE=local|claude|openai   # 默认local
ANTHROPIC_API_KEY=sk-ant-...   # Claude
OPENAI_API_KEY=sk-...          # OpenAI
LLM_MODEL=claude-sonnet-4-20250514  # 可选
```

---

## 6. 交付物清单

| 交付物 | 位置 | 说明 |
|--------|------|------|
| 爬虫模块 | `src/collectors/` | 策略驱动HTTP爬取 |
| 探索Agent | `src/explorers/` | 交互式站点探索 |
| 分析器 | `src/analyzers/` | 启发式+LLM混合 |
| 策略管理 | `src/strategies/` | 策略CRUD |
| 策略文件 | `data/strategies/*.json` | 正式策略 |
| Harness配置 | `.claude/settings.json` | Claude Code权限 |
| Claude配置 | `.claude/CLAUDE.md` | 项目说明 |
| 本文档 | `SPEC.md` | 规格说明 |
| 验收清单 | `CHECKLIST.md` | 逐条验证 |
| AI指南 | `AGENTS.md` | 协作指南 |
| Context | `context-pack.md` | 上下文总结 |

---

## 7. 阶段划分

### Phase 1 — MVP ✅ 完成

- [x] HTTP模式多站点爬取
- [x] 5种CMS类型提取
- [x] 分页处理
- [x] 策略存储与复用（v3格式）
- [x] 目录结构重构
- [x] 多轮交互式探索Agent
- [x] Harness基础框架

### Phase 2 — 增强（当前）

- [ ] 配置真实LLM API Key，验证完整交互流程
- [ ] 补充更多站点策略
- [ ] 优化错误处理

### Phase 3 — 收尾

- [ ] 清理临时文件
- [ ] 最终功能验证

---

## 8. 已知限制

1. **AI探索依赖API Key**：local模式不支持（预期行为）
2. **无增量爬取**：每次重新爬取（已有去重）
3. **无定时任务**：需手动运行
4. **browser/chrome 28MB**：打包时需考虑
