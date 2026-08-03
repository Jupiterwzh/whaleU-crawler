# 蓝鲸U — 测试指南

> 本文档说明如何手动测试蓝鲸U爬虫项目。
> 包含AI自动测试和必须手动测试的项目。
>
> 版本：1.0.0
> 更新：2026-08-02

---

## 一、测试概览

### 1.1 测试分类

| 类型 | 说明 | 执行者 |
|------|------|--------|
| **自动测试** | 可通过命令行自动验证 | AI自动执行 |
| **手动测试** | 需要人工确认结果 | 你（用户） |
| **LLM相关** | 需要配置API Key | 你（用户） |

### 1.2 快速验证命令

```bash
cd D:\PY\lanling-u\standalone

# 一键验证所有自动测试项
node --check src/collectors/collector.js && echo "collector.js OK"
node --check src/explorers/site-explorer.js && echo "site-explorer.js OK"
node --check src/strategies/strategy-manager.js && echo "strategy-manager.js OK"
node --check src/analyzers/analyzer.js && echo "analyzer.js OK"

# 模块导入测试
node -e "require('./src/collectors/collector'); console.log('collector import OK')"
node -e "require('./src/strategies/strategy-manager'); console.log('strategy-manager import OK')"

# 策略列表
node src/collectors/collector.js --list-strategies
```

---

## 二、自动测试（AI可执行）

### 2.1 语法检查

```bash
# 检查所有JS文件语法
node --check src/collectors/collector.js
node --check src/explorers/site-explorer.js
node --check src/strategies/strategy-manager.js
node --check src/analyzers/analyzer.js
node --check src/analyzers/agent-analyzer.js
```

**预期结果**：无输出表示语法正确

### 2.2 模块导入测试

```bash
# 测试各模块能否正确导入
node -e "require('./src/collectors/collector'); console.log('OK')"
node -e "require('./src/strategies/strategy-manager'); console.log('OK')"
node -e "require('./src/analyzers/analyzer'); console.log('OK')"
```

**预期结果**：输出 `OK`

### 2.3 策略管理测试

```bash
# 测试策略读取
node -e "const sm=require('./src/strategies/strategy-manager'); console.log('cs.nju.edu.cn entries:', sm.getStrategy('cs.nju.edu.cn')?.entries?.length);"

# 测试策略列表
node -e "const sm=require('./src/strategies/strategy-manager'); console.log(sm.listStrategies());"
```

**预期结果**：
- cs.nju.edu.cn 返回 entries 数量
- jw.nju.edu.cn 返回 entries 数量

### 2.4 爬虫功能测试（HTTP模式，无需LLM）

```bash
cd D:\PY\lanling-u\standalone

# 测试1：爬取计算机学院通知（已有策略）
node src/collectors/collector.js --site https://cs.nju.edu.cn/ --max-pages 1 --days 365

# 测试2：爬取指定列表页
node src/collectors/collector.js --notices https://cs.nju.edu.cn/1702/list.htm --max-pages 1

# 测试3：爬取本科生院公告
node src/collectors/collector.js --notices https://jw.nju.edu.cn/ggtz/list.htm --max-pages 1
```

**预期结果**：
- 发现N条通知
- 保存M条到jsonl文件
- 输出类似：`共处理 X 条，保存 Y 条`

---

## 三、必须手动测试（需要你操作）

### 3.1 手动测试清单

| # | 测试项 | 操作步骤 | 预期结果 |
|---|--------|----------|----------|
| M1 | 双击启动脚本 | 双击 `启动爬虫.bat` | 窗口打开，无报错 |
| M2 | 查看爬取结果 | 打开 `data/notices_*.jsonl` | 有JSON格式数据 |
| M3 | 验证JSONL格式 | 检查文件内容格式 | 每行一个JSON对象 |
| M4 | 验证数据完整性 | 检查字段 | 包含 title, url, content, publishTime |
| M5 | 策略文件编辑 | 手动编辑策略文件 | 文件保存成功 |
| M6 | 浏览器模式（如需） | 启动浏览器服务 | Chrome窗口打开 |

### 3.2 手动测试详细步骤

#### M1: 双击启动脚本

1. 打开文件资源管理器
2. 导航到 `D:\PY\lanling-u\standalone\`
3. 双击 `启动爬虫.bat`
4. 观察窗口是否正常打开
5. 检查是否有红色错误信息

**如果出错**：
- 检查Node.js是否安装：`node --version`
- 检查路径是否正确

#### M2 & M3: 查看爬取结果

1. 打开 `D:\PY\lanling-u\standalone\data\` 目录
2. 找到最新的 `notices_*.jsonl` 文件
3. 右键 → 打开方式 → 选择记事本或VS Code
4. 检查文件内容

**预期格式**：
```json
{"title":"标题","url":"https://...","content":"正文...","publishTime":"2026-08-01","attachments":[],"hasVideo":false,"hasAudio":false,"source":{"author":"","department":"计算机学院","siteName":"计算机学院"},"tags":["通知公告"],"crawler":"nju-crawler","crawlTime":"2026-08-02T..."}
```

#### M4: 验证数据完整性

检查JSON对象是否包含必要字段：
- [ ] `title` - 通知标题
- [ ] `url` - 通知链接
- [ ] `content` - 正文内容
- [ ] `publishTime` - 发布时间
- [ ] `tags` - 标签数组
- [ ] `crawlTime` - 爬取时间

#### M5: 策略文件编辑

1. 打开 `data/strategies/cs.nju.edu.cn.json`
2. 修改 `name` 字段（如改为"测试名称"）
3. 保存文件
4. 运行：`node src/collectors/collector.js --list-strategies`
5. 确认修改生效

#### M6: 浏览器模式测试（可选）

仅当某些JS渲染站点无法用HTTP模式爬取时需要：

1. 双击 `启动浏览器.bat`
2. 等待Chrome窗口打开并登录
3. 保持浏览器窗口打开
4. 运行：`node src/collectors/collector.js --site https://xxx/ --browser`

---

## 四、LLM相关测试（需要配置API Key）

### 4.1 配置LLM

**方式一：系统环境变量**
```
Windows → 控制面板 → 系统 → 高级 → 环境变量 → 新建系统变量
LLM_MODE = claude
ANTHROPIC_API_KEY = sk-ant-your-key
```

**方式二：BAT脚本临时设置**
编辑 `启动爬虫.bat`，在 `node` 命令前添加：
```bat
set LLM_MODE=claude
set ANTHROPIC_API_KEY=sk-ant-your-key
```

### 4.2 LLM测试项

| # | 测试项 | 操作步骤 | 预期结果 |
|---|--------|----------|----------|
| L1 | LLM连接测试 | 配置Key后运行探索 | 能成功调用LLM |
| L2 | 交互式探索 | `node src/explorers/site-explorer.js --url https://新站点/` | AI分析网站结构 |
| L3 | 草稿生成 | 完成探索后 | 生成 `.draft.json` 文件 |
| L4 | 草稿确认 | `node src/collectors/collector.js --confirm domain` | 草稿转正式策略 |

### 4.3 LLM测试命令

```bash
# L1: 验证LLM配置
node -e "const llm=require('../../src/agent/llm'); console.log('LLM mode:', process.env.LLM_MODE);"

# L2: 交互式探索（需要新站点）
node src/explorers/site-explorer.js --url https://xxx.nju.edu.cn/

# L3: 查看生成的草稿
ls data/strategies/*.draft.json

# L4: 确认草稿
node src/collectors/collector.js --confirm xxx.nju.edu.cn --days 30
```

---

## 五、agent-harness测试

### 5.1 OOP模块测试

```bash
cd D:\PY\lanling-u\agent-harness

# 语法检查
node --check src/agents/base-agent.js
node --check src/agents/crawler-agent.js
node --check src/agents/explorer-agent.js
node --check src/agents/index.js

# 导入测试
node -e "const agents = require('./src/agents'); console.log('Available:', Object.keys(agents));"

# Agent实例化测试
node -e "
const {CrawlerAgent, ExplorerAgent} = require('./src/agents');
const c = new CrawlerAgent();
const e = new ExplorerAgent();
console.log('Crawler LLM:', c.getLLMMode(), 'Prefix:', c.envPrefix);
console.log('Explorer LLM:', e.getLLMMode(), 'Prefix:', e.envPrefix);
"
```

**预期结果**：
```
Available: ['BaseAgent', 'TaskAgent', 'CrawlerAgent', 'ExplorerAgent', ...]
Crawler LLM: local Prefix: CRAWLER_
Explorer LLM: local Prefix: EXPLORER_
```

### 5.2 agent-harness手动测试

| # | 测试项 | 操作步骤 | 预期结果 |
|---|--------|----------|----------|
| AH1 | 双击启动 | 双击 `agent-harness/启动Agent.bat` | Claude Code启动 |
| AH2 | 环境变量 | 检查BAT脚本中的CRAWLER_*变量 | 变量已设置 |
| AH3 | Agent实例化 | 运行上述node命令 | 无报错 |

---

## 六、问题排查

### 6.1 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| `node: command not found` | Node.js未安装 | 安装Node.js 18+ |
| `HTTP 403` | 网站禁止爬取 | 检查User-Agent设置 |
| `HTTP 410` | 页面不存在 | 检查URL是否正确 |
| `找不到模块` | 路径问题 | 检查工作目录 |
| `timeout` | 网络超时 | 增加timeout或检查网络 |

### 6.2 调试命令

```bash
# 查看详细错误
node src/collectors/collector.js --site https://cs.nju.edu.cn/ --max-pages 1 --verbose 2>&1

# 查看环境变量
node -e "console.log(process.env)"

# 查看Node版本
node --version

# 查看npm版本
npm --version
```

---

## 七、测试记录表

完成手动测试后，请在下方记录：

| 日期 | 测试项 | 结果 | 备注 |
|------|--------|------|------|
| | M1 双击启动脚本 | | |
| | M2 查看爬取结果 | | |
| | M3 JSONL格式验证 | | |
| | M4 数据完整性验证 | | |
| | M5 策略文件编辑 | | |
| | LLM配置 | ⏳ 待配置 | |

---

## 八、验收清单核对

根据 `CHECKLIST.md`，核心功能检查项：

### 功能检查（F）

- [ ] F1.1 策略管理器目录存储
- [ ] F1.2 `getStrategy()` 正确读取
- [ ] F2.1 site-explorer --help
- [ ] F3.1 `--site` 有策略时直接爬取
- [ ] F3.3 `--notices` 爬取列表页

### 工程检查（E）

- [ ] E1 所有JS语法正确
- [ ] E2 模块导入无报错
- [ ] E3 目录结构正确

### 安全检查（S）

- [ ] S1 无硬编码凭证
- [ ] S3 .env文件不被AI读取

### Agent隔离检查（A）

- [ ] A1 Agent专用环境变量前缀
- [ ] A2 settings.json的env映射
- [ ] A3 BAT脚本隔离
- [ ] A4 防泄露deny规则
