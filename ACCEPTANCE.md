# ACCEPTANCE.md — 端到端验收测试清单

> 对应作业 §4.8 测试要求 + SPEC §9 验收标准的**真实验收证据**。
> 这些是需要真实 LLM/网络/交互的手动验收（自动化单元测试见 `make test`，110 tests）。
> 关联：`无关文档/测试设计.md`（原始设计）、`explorer-agent/MANUAL_CHECKS.md`（explorer 专项）。
> 测试 6/7（需登录站点）在 Windows 上执行。

---

## 前置

- 已 `pip install -r` 三个 Agent 依赖
- 已配 key：`cd query-agent && python -m src.keys set`（或 `.env`）
- cs/jw/yzb 已有策略（`crawler/data/strategies/`）
- query-agent 为分发 Agent（工具：rag_search / run_crawler / check_strategy / run_explorer / read_file）

---

## 测试 1：策略 Agent 爬取无登录网站 cs.nju.edu.cn

```bash
cd explorer-agent
python main.py "探索 https://cs.nju.edu.cn/ 的通知公告入口"
```

**预期**：结构遍历 → 用户选择入口 → 生成 `crawler/data/strategies/cs.nju.edu.cn.json` → 自动 `--verify` 实测入口。
**通过**：策略 JSON 的 meta/entries 结构完整。

## 测试 2：爬虫按策略爬取 cs

```bash
cd crawler
node src/collectors/collector.js --site https://cs.nju.edu.cn/ --days 365 --max-pages 3
```

**预期**：显示"使用策略"，按 entries 逐入口爬取。
**通过**：`notices_*.jsonl` 含 title/url/publishTime/content。

## 测试 3：RAG 管理 Agent 分析有效期并入库（去重）

```bash
cd rag-manager
python rag_manager.py
```

**预期**：读取爬虫产出 → 判定 valid_from/until → 写回 → 重建 current 索引；同 dedup_hash 重复丢弃。
**通过**：`data/rag/docs/` 新增分片；重复 added=0；有效时间字段存在。

## 测试 4：RAG 管理 Agent 搜索 cs 来源全部信息

```bash
cd query-agent && python -c "
from shared.rag.ragstore import RAGStore
store = RAGStore('../data/rag'); store.refresh()
for h in store.search('cs', top_k=20):
    print(h['date'], h.get('valid_until','-'), h['title'], h['url'])
"
```

**预期**：命中 cs 来源多条，每条含 date/valid_until/url/content。
**通过**：字段齐全，可溯源到原 URL。

## 测试 5：分发 Agent 全链（software 无策略场景）

```bash
cd query-agent
python query.py "软件学院最近有什么通知"
```

**预期链路**：rag_search 无结果 → check_strategy 不存在 → run_explorer 唤起策略 Agent（交互）→ 策略生成 → run_crawler 抓取入库 → 触发 rag-manager 判有效期去重 → 再 rag_search 回答。
**兜底**：策略 Agent 被终止 → 分发 Agent 询问是否用已有 RAG 过期内容。
**通过**：回答含 software URL；`data/rag/docs/` 出现 software 分片；再 check_strategy 变"存在"。

## 测试 6：策略 Agent 爬取需登录网站 ndwy.nju.edu.cn（Windows）

```bash
# 1) 起浏览器服务（SSO 扫码）
cd crawler && node browser-start.js
# 2) 探索 ndwy
cd ../explorer-agent && python main.py "探索 https://ndwy.nju.edu.cn/ 的通知公告入口"
```

**预期**：访问登录后页面，生成 `ndwy.nju.edu.cn.json`。
**通过**：策略含 meta/entries；需登录页被正确识别。

## 测试 7：爬虫按策略爬取 ndwy（Windows）

```bash
cd crawler
node src/collectors/collector.js --site https://ndwy.nju.edu.cn/ --days 365 --browser
```

**预期**：浏览器模式复用登录态，按策略爬取。
**通过**：`notices_*.jsonl` 含登录后才可见的通知内容。

---

## 验收结果记录

| 测试 | 通过? | 日期 | 备注 |
|------|-------|------|------|
| 1 策略 Agent cs | | | |
| 2 爬虫按策略 cs | | | |
| 3 RAG 管理有效期/去重 | | | |
| 4 RAG 搜索 cs 全信息 | | | |
| 5 分发 Agent 全链 | | | |
| 6 策略 Agent ndwy (Win) | | | |
| 7 爬虫 ndwy (Win) | | | |
