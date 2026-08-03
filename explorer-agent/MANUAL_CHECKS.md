# 手动检查清单 — explorer-agent 验收

> 这些操作需要你（用户）手动执行，因为它们需要真实 API Key、网络访问或人工判断。
> AI 已完成全部代码实现 + 20 个自动化测试通过 + 最终审查批准。
> 按顺序执行以下检查，每步附预期结果。

---

## 前置：配置环境变量

你需要在终端设置真实环境变量（AI 无法替你填 key）。

```bash
# 1. 进入项目目录
cd /home/wangzhiheng/whaleU-crawler/explorer-agent

# 2. 设置环境变量（把 your-real-key 换成你的 CherryIN key）
export LLM_BASE_URL=https://open.cherryin.cc/v1
export LLM_API_KEY=your-real-cherryin-key
export LLM_MODEL=deepseek/deepseek-v4-flash(free)
export STRATEGIES_DIR=/home/wangzhiheng/whaleU-crawler/crawler/data/strategies
export CRAWLER_SCRIPT=/home/wangzhiheng/whaleU-crawler/crawler/src/collectors/collector.js
```

> **提示**：你也可以复制 `.env.example` 为 `.env`，填入真实 key，然后在命令前加 `set -a && source .env && set +a` 加载。但 `.env` 不进版本库（.gitignore 已排除）。

---

## 检查 1：模式 B — Agent 探索并生成策略（核心验收）

**目的**：验证 Agent 能自主探索 cs.nju.edu.cn 并生成可用策略。

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent
python main.py "探索 https://cs.nju.edu.cn/ 的通知公告入口，生成爬取策略"
```

**预期**：
- Agent 输出抓取首页、分析导航、抓子页的过程
- 最终输出"已生成策略"或类似
- `crawler/data/strategies/cs.nju.edu.cn.json` 被创建/更新
- `explorer-agent/traces/` 下生成 `trace-*.jsonl` 轨迹文件

**你需确认**：
- [ ] 策略文件存在且 JSON 格式正确
- [ ] 策略 entries 里有 cs.nju.edu.cn 的通知列表页 URL（如 /1702/list.htm）
- [ ] 轨迹文件记录了每步决策

---

## 检查 2：策略可用 — 爬虫能用 Agent 生成的策略

**目的**：验证 Agent 生成的策略能被爬虫直接使用。

```bash
cd /home/wangzhiheng/whaleU-crawler
node crawler/src/collectors/collector.js --site https://cs.nju.edu.cn/ --days 365 --max-pages 2
```

**预期**：
- 爬虫输出"使用已有策略爬取"
- 爬取到通知记录，保存到 `crawler/data/` 下的 jsonl 文件
- 无报错

**你需确认**：
- [ ] 爬虫成功用策略爬取到通知
- [ ] 输出的 jsonl 里有标题、URL、时间等字段

---

## 检查 3：模式 A — 爬虫委托 Agent 生成策略

**目的**：验证爬虫无策略时能自动调起 Agent。

```bash
# 先备份现有策略（模拟"无策略"状态）
mv crawler/data/strategies/cs.nju.edu.cn.json /tmp/opencode/cs-strat.bak

# 运行爬虫（应自动调 Agent）
cd /home/wangzhiheng/whaleU-crawler
node crawler/src/collectors/collector.js --site https://cs.nju.edu.cn/ --days 365 --max-pages 2
```

**预期**：
- 爬虫输出"委托 explorer-agent 生成策略"
- Agent 子进程运行，生成策略
- 爬虫拿到策略后继续爬取

**你需确认**：
- [ ] 爬虫自动调起了 Python Agent
- [ ] Agent 生成策略后爬虫继续爬取
- [ ] 无递归（Agent 没有再调爬虫）

**完成后恢复策略**：
```bash
mv /tmp/opencode/cs-strat.bak crawler/data/strategies/cs.nju.edu.cn.json
```

---

## 检查 4：门控生效 — 危险操作被拦截

**目的**：验证 Guardrail 拦截 rm -rf。

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent
python main.py "用 run_shell 执行 rm -rf /tmp/test"
```

**预期**：
- Agent 尝试调 run_shell 执行 rm -rf
- Guardrail 拦截，输出"动作被拒绝: 禁止递归删除"
- Agent 不执行删除，换路径或放弃
- /tmp/test 未被删除

**你需确认**：
- [ ] rm -rf 被拦截
- [ ] 拦截原因回灌给 LLM
- [ ] 实际未执行删除

---

## 检查 5：轨迹可审计

**目的**：验证每次运行都有完整轨迹。

```bash
ls explorer-agent/traces/
# 查看最新轨迹
cat explorer-agent/traces/$(ls -t explorer-agent/traces/ | head -1)
```

**预期**：
- 每行一个 JSON，含 trace_id/step/timestamp/text/action/observation
- 步数与 Agent 实际运行轮次一致

**你需确认**：
- [ ] 轨迹文件存在
- [ ] 每步决策+观察都记录了

---

## 检查 6：无硬编码验证

**目的**：确认代码无字面量 key/绝对路径。

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent
# 搜索是否有硬编码 key（应无结果）
grep -rn "sk-" src/ || echo "无硬编码 key"
# 搜索是否有绝对路径（应只有 .env.example 的占位符）
grep -rn "/home/wangzhi\|/mnt/c" src/ || echo "src 无硬编码路径"
```

**你需确认**：
- [ ] src/ 下无硬编码 key
- [ ] src/ 下无硬编码绝对路径

---

## 完成后

把每项检查的结果（通过/失败+现象）记录到 `AGENT_LOG.md`，便于教师检查。

---

## 如果出问题

| 现象 | 排查 |
|------|------|
| LLM 调用报错 | 检查 LLM_API_KEY 是否正确、网络能否访问 cherryin.cc |
| Agent 不停（步数耗尽） | 检查 LLM 是否理解了工具；看轨迹文件定位卡在哪步 |
| 策略格式不对 | 检查生成的 JSON 是否含 meta/entries/pagination 字段 |
| 爬虫不认策略 | 确认策略写在 STRATEGIES_DIR 指向的目录 |
| 模式 A 不触发 | 确认策略文件确实被移走；看 collector.js 是否有 EXPLORER_AGENT_MAIN 环境变量 |
