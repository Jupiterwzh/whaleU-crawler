# 蓝鲸U — 验收清单

> 验证时间：2026-08-02
> 用途：逐条检查，每条必须可验证

---

## 检查标记说明

- ✅ 已验证通过
- ❌ 未通过 / 缺失
- ⏳ 待验证（需配置）

---

## F — 功能检查（Function）

### F1. 策略管理

- [ ] **F1.1** 策略管理器支持目录存储
  - 验证：`ls data/strategies/` 存在 `*.json` 文件
  - 判据：每域名一个JSON文件

- [ ] **F1.2** `getStrategy()` 正确读取策略
  - 验证：`node -e "const sm=require('./src/strategies/strategy-manager'); console.log('entries:', sm.getStrategy('cs.nju.edu.cn')?.entries?.length);"`
  - 判据：输出 `entries: 1` 或更高

- [ ] **F1.3** `confirmDraft()` 草稿转正式策略
  - 验证：创建测试草稿后运行 confirmDraft，检查文件变更
  - 判据：草稿消失，正式策略存在

- [ ] **F1.4** `listStrategies()` 正确列出
  - 验证：`node src/collectors/collector.js --list-strategies`
  - 判据：输出策略列表

- [ ] **F1.5** v2→v3 自动升级
  - 验证：`data/strategies.json` 存在且标记为 `_migrationDone`
  - 判据：迁移已完成

### F2. 探索Agent

- [ ] **F2.1** site-explorer.js 交互式探索启动
  - 验证：`node src/explorers/site-explorer.js --help`
  - 判据：输出帮助信息

- [ ] **F2.2** site-explorer.js 启发式探索
  - 验证：`node -e "const {exploreSiteSimple}=require('./src/explorers/site-explorer'); exploreSiteSimple('https://cs.nju.edu.cn/',{forceStrategy:true}).then(r=>console.log('ok:',r.entries.length));"`
  - 判据：输出 `ok: N`（N>0）

- [ ] **F2.3** in-progress 文件检测
  - 验证：`node src/explorers/site-explorer.js --list`
  - 判据：列出进行中的探索（或显示"没有"）

### F3. 爬取功能

- [ ] **F3.1** `--site` 有策略时直接爬取
  - 验证：`node src/collectors/collector.js --site https://cs.nju.edu.cn/ --days 365 --max-pages 1`
  - 判据：使用已有策略，出现爬取日志

- [ ] **F3.2** `--site` 无策略时触发探索
  - 验证：`node src/collectors/collector.js --site https://new-unknown.nju.edu.cn/`
  - 判据：触发探索或提示

- [ ] **F3.3** `--notices` 直接爬取列表
  - 验证：`node src/collectors/collector.js --notices https://cs.nju.edu.cn/1702/list.htm --max-pages 1`
  - 判据：爬取日志

- [ ] **F3.4** `--url` 爬取单页面
  - 验证：`node src/collectors/collector.js --url https://cs.nju.edu.cn/`
  - 判据：输出标题和时间

- [ ] **F3.5** `--confirm` 确认草稿并爬取
  - 验证：手动创建草稿 → `--confirm` 验证
  - 判据：草稿转正式策略后开始爬取

### F4. 数据输出

- [ ] **F4.1** `data/records/all_records.jsonl` 结构化记录
  - 验证：`node -e "const d=require('fs').readFileSync('data/records/all_records.jsonl','utf8').trim().split('\n')[0]; console.log(Object.keys(JSON.parse(d)).join(','));"`
  - 判据：含 `title,url,content,publishTime,tags,crawlTime`

---

## E — 工程检查（Engineering）

- [ ] **E1** 所有 JS 文件语法正确
  - 验证：`node --check src/**/*.js`
  - 判据：无语法错误

- [ ] **E2** 模块导入无报错
  - 验证：`node -e "require('./src/collectors/collector'); console.log('ok');"`
  - 判据：输出 "ok"

- [ ] **E3** 目录结构正确
  - 验证：`ls src/collectors/ src/explorers/ src/analyzers/ src/strategies/ src/data/`
  - 判据：5个目录都存在

- [ ] **E4** 临时文件已清理
  - 验证：检查 `ai-discoverer.js` 标记为 deprecated

- [ ] **E5** .claude/ 配置完整
  - 验证：`ls .claude/settings.json .claude/CLAUDE.md`
  - 判据：两个文件存在

---

## S — 安全检查（Security）

- [ ] **S1** 无硬编码凭证
  - 验证：`grep -r "sk-ant" src/ 2>/dev/null || echo "OK"`
  - 判据：无输出

- [ ] **S2** User-Agent 规范
  - 验证：检查 `collector.js` 中 `User-Agent` 含 "NJU-Crawler"

- [ ] **S3** .env 文件不被 AI 读取
  - 验证：`.claude/settings.json` 中 `deny` 含 ".env"
  - 验证：`.gitignore` 含 `.env`

- [ ] **S4** 草稿 JSON 安全解析
  - 验证：`strategy-manager.js` 中 `confirmDraft` 使用 `JSON.parse`

- [ ] **S5** Agent隔离配置（可选，高级）
  - 验证：检查是否配置了 `AGENT_*` 环境变量
  - 验证：Agent专用settings.json使用 `env:AGENT_*` 映射
  - 判据：Agent与你使用不同的key

---

## A — Agent隔离检查（Agent Isolation）

- [ ] **A1** Agent专用环境变量前缀
  - 验证：`AGENT_ANTHROPIC_API_KEY` 已配置
  - 判据：在Agent运行环境中可访问

- [ ] **A2** Agent专用settings.json的env映射
  - 验证：包含 `"ANTHROPIC_API_KEY": "env:AGENT_ANTHROPIC_API_KEY"`
  - 判据：Agent只能通过AGENT_*前缀访问key

- [ ] **A3** Agent启动脚本隔离
  - 验证：BAT脚本设置 `AGENT_*` 而非直接设置 `ANTHROPIC_API_KEY`
  - 判据：你的key和Agent的key互不影响

- [ ] **A4** 防泄露deny规则
  - 验证：deny规则包含 `*KEY*`, `*PASSWORD*`, `*SECRET*`, `*TOKEN*`
  - 判据：AI无法读取包含敏感词的文件

---

## 最终验证命令

```bash
cd D:/PY/lanling-u/standalone

# F1.2
node -e "const sm=require('./src/strategies/strategy-manager'); console.log('entries:', sm.getStrategy('cs.nju.edu.cn')?.entries?.length);"

# F2.1
node src/explorers/site-explorer.js --help

# F3.1
node src/collectors/collector.js --site https://cs.nju.edu.cn/ --days 365 --max-pages 1

# E2
node -e "require('./src/collectors/collector'); console.log('ok');"

# S3
grep -A2 "deny" .claude/settings.json

# A1-A4: Agent隔离验证
node -e "console.log('AGENT_ANTHROPIC_API_KEY:', process.env.AGENT_ANTHROPIC_API_KEY ? '已设置' : '未设置')"
grep "AGENT_ANTHROPIC_API_KEY" .claude/settings.json
```

---

## Agent隔离验证（可选）

如果你配置了Agent隔离，运行以下命令验证：

```bash
# 验证Agent环境变量可访问
node -e "console.log('Agent Key:', process.env.AGENT_ANTHROPIC_API_KEY)"

# 验证你的Key和Agent的Key不同
node -e "console.log('Your Key:', process.env.ANTHROPIC_API_KEY ? '已设置' : '未设置')"

# 验证settings.json的env映射
grep -A5 '"env"' .claude/settings.json
```

详细指南见 `AGENT_HARNESS_GUIDE.md`。

---

## 记录

| 项目 | 日期 | 结果 | 备注 |
|------|------|------|------|
| 初始验收 | 2026-08-02 | ⏳ | 目录重构完成，待LLM配置 |
