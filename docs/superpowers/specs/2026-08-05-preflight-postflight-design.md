# 设计：前导检查 + 后导保存 + 文件存储层

> 日期：2026-08-05
> 状态：已批准
> 关联：explorer-agent/main.py、agent_loop.py、src/preflight.py(新)、src/postflight.py(新)、src/filestore.py(新)

---

## 1. 背景与问题

当前流程是"输入域名 → Agent 跑 → 结束"，缺少以下能力：

- **无崩溃恢复**：Agent 中途退出，已生成的策略丢失
- **无已有策略感知**：用户爬过 cs.nju.edu.cn 后再爬同域名，Agent 不提示也不参考已有结果
- **无备份管理**：策略被覆盖后无法回溯
- **无暂存/断点续作**：不能中途暂停、改天续作
- **文件操作不可见**：所有策略写入由 Agent 工具触发，用户对文件层面无感知

## 2. 目标

把主流程拆为三段：

```
main.py
  ├── preflight(domain)         检查崩溃/暂存/备份/策略 → 决定是否跑、带什么上下文
  ├── AgentLoop.run(goal)       探索 + 生成策略 + 用户交互确认（保持不变）
  └── postflight(domain)        保存策略、备份/替换旧策略、清理崩溃文件
```

新增 `filestore.py` 统一管理所有文件路径和 CRUD，不散落各模块。

## 3. 非目标

- 不改 Agent 核心循环逻辑（探索生成 + 交互确认保持不变）
- 不引入多 Agent 协作
- 不为备份做差异对比或自动合并
- 不做 Web 界面

## 4. 目录结构

```
data/                                     ← 相对于 main.py 的 ../data
  strategies/
    <domain>.json                         标准策略（唯一，已有格式）
  backups/
    <domain>.bak1.json                    备份，每域名 ≤3
    <domain>.bak2.json
    <domain>.bak3.json
  checkpoints/
    <domain>.checkpoint.json              暂存（用户主动保存），0/1
    <domain>.crash.json                   特殊暂存（崩溃恢复），0/1
```

文件格式：

| 类型 | 格式 | 说明 |
|------|------|------|
| 策略 | 标准 JSON（meta/entries/pagination/extraction/notes） | 唯一激活策略 |
| 备份 | 标准 JSON + `_backup_of`(源域名) + `_backup_at`(ISO时间) | 每域名 ≤3 |
| 暂存 | 标准 JSON（策略格式） | 0 或 1 个 |
| 特殊暂存 | 标准 JSON（策略格式） | 0 或 1 个 |

确认规则：所有文件操作（策略写入、备份写入、备份管理读写）均通过 Guardrail `write_file` 确认，**crash 文件和 checkpoint 文件除外**（自动保存，不阻塞）。

## 5. 模块设计

### 5.1 `src/filestore.py` — 文件存储层

```python
class FileStore:
    def __init__(self, base_dir: str)  # base_dir 如 "../data"
    
    # 策略
    def strategy_exists(self, domain: str) -> bool
    def strategy_read(self, domain: str) -> dict | None
    def strategy_write(self, domain: str, data: dict)
    def strategy_delete(self, domain: str)
    
    # 备份 (每域名 ≤3)
    def backup_paths(self, domain: str) -> list[Path]    # 按时间排序
    def backup_count(self, domain: str) -> int
    def backup_write(self, domain: str, data: dict) -> int  # 返回 index (1-3)
    def backup_read(self, domain: str, index: int) -> dict
    def backup_delete(self, domain: str, index: int)
    def backup_swap(self, domain: str, index: int)        # 备份↔策略交换
    
    # 暂存 (0/1)
    def checkpoint_exists(self, domain: str) -> bool
    def checkpoint_write(self, domain: str, data: dict)
    def checkpoint_read(self, domain: str) -> dict
    def checkpoint_delete(self, domain: str)
    
    # 特殊暂存/崩溃 (0/1)
    def crash_exists(self, domain: str) -> bool
    def crash_write(self, domain: str, data: dict)    # 不需确认
    def crash_read(self, domain: str) -> dict
    def crash_delete(self, domain: str)               # 不需确认
```

`backup_write` 自动选最小可用编号（优先 `bak1`，若存在则 `bak2`，再 `bak3`；若都满则覆盖最旧的）。

### 5.2 `src/preflight.py` — 前导检查

按优先级从高到低检查六关：

```
preflight(domain, store) -> PreflightResult

1. crash_exists?
   → 是：提示"发现意外退出前的暂存策略"，直接返回 crash_mode=True（跳到 postflight）

2. checkpoint_exists?
   → 是：input("是否参考上次暂存？（y/否）")
     → y: 标记 mark_read_checkpoint=True（不读，到 C 处读），文件不删
     → 其他: 删除暂存文件

3. A: backup_count > 0?
   → 是：提示"检测到 N 个备份（上限 3），是否管理备份？（y/否）"
     → y: 进入备份管理交互。Agent 读取所有备份+策略，输出自然语言介绍。用户以自然语言交互（删除/交换/启用），最多 5 轮（第 3 轮输出提示上限 5 次）。用户主动说"结束/exit/done"或达轮次上限时退出。操作直接作用于文件（通过 FileStore）。
     → 否: 跳过

4. B: strategy_exists?
   → 是：提示"已有策略，是否仍要爬取？（y/否）"
     → 否: 输出结束提示，return should_exit=True
     → 是: input("是否参考已有策略？（y/否）")
       → y: 读取策略，塞入 goal_context
       → 否: input("是否删除已有策略？（y/否）")
         → y: 删除
         → 否: 不动

5. C: mark_read_checkpoint?
   → 是: 读取暂存文件，塞入 goal_context
   → 否: 跳过
```

返回 `PreflightResult(crash_mode, should_exit, goal_context)`。

### 5.3 `src/postflight.py` — 后导保存

```
postflight(domain, store) -> None

前提：Agent 已完成探索，已验证策略 JSON 已写入 strategies_dir

1. 读取刚生成的策略 strategy_data
2. crash_write(domain, strategy_data)           # 防丢
3. 检查 strategy_exists(domain)?
   → 否: crash→strategy 直接落盘，删除 crash          # 新增策略
   → 是: input("已有策略，删除还是备份？（删除/备份）")
     → 删除: 旧策略删除，crash→strategy，删除 crash
     → 备份: 检查 backup_count(domain)
       → <3: 旧策略→backup, crash→strategy, 删除 crash
       → ≥3: 进入备份管理交互
         Agent 读取所有备份，给出处理建议（相似度、时间顺序）。
         用户以自然语言交互（最多 5 轮，第 6 轮仅 3 个选项）：
           a) 按时间保留最后 3 个，放弃备份 ← 直接执行
           b) 备份新旧策略 ← 需等备份数降到 ≤2
           c) 按时间保留最后 2 个，备份旧策略 ← 直接执行
         备选：用户随时可"放弃备份"（Agent 先确认，然后执行 a）
         备份数降到 ≤2 时：Agent 提示"已可以备份"，询问是否备份→执行 b/c 或放弃
```

### 5.4 main.py 改动

```python
def main():
    load_env()
    args = sys.argv[1:]
    explore_only = "--explore-only" in args
    
    # 提取域名
    if explore_only:
        domain = extract_domain(url)
    else:
        user_input = " ".join(args) or input("🎯 任务: ")
        domain = extract_domain_from_text(user_input)
        # mode B 的目标仍自动注入策略路径（已有逻辑）
    
    store = FileStore(base_dir=os.environ.get("DATA_DIR", "../data"))
    
    # --- 前导 ---
    result = preflight(domain, store)
    if result.should_exit:
        return
    if result.crash_mode:
        postflight(domain, store)
        return
    
    # --- Agent ---
    goal = build_goal(args, explore_only, result.goal_context)
    harness = Harness.from_yaml("agent.yaml")
    llm = LLMClient()
    loop = AgentLoop(harness, llm)
    loop.run(goal)
    
    # --- 后导 ---
    postflight(domain, store)
```

### 5.5 agent_loop.py

不改逻辑。现有的交互确认（y/调整建议）、步数重置、备份输出格式已满足需求。

## 6. 确认规则

| 操作 | 是否需要确认 |
|------|-------------|
| 策略写入 (strategy_write) | ✅ Guardrail ask_user（已有） |
| 备份写入 (backup_write) | ✅ Guardrail ask_user |
| 备份删除 (backup_delete) | ✅ Guardrail ask_user |
| 备份交换 (backup_swap) | ✅ Guardrail ask_user |
| 策略删除 (strategy_delete) | ✅ Guardrail ask_user |
| 暂存写入 (checkpoint_write) | ✅ preflight/postflight 内 input 确认 |
| **crash 写入 (crash_write)** | ❌ 不透传 Guardrail，直接写磁盘 |
| **crash 删除 (crash_delete)** | ❌ 直接删 |
| **暂存删除 (checkpoint_delete)** | ✅ preflight 内 input("是否删除？") |

crash 文件走 `store.crash_write()` 直接写，不经过 Guardrail（`use_guardrail=False` 参数控制）。

## 7. 受影响文件

| 文件 | 改动 |
|------|------|
| `src/filestore.py` | 新建 |
| `src/preflight.py` | 新建 |
| `src/postflight.py` | 新建 |
| `main.py` | 重构：加入三段式流程 |
| `src/filestore.py` | 新建 |
| `.env.example` | 加 `DATA_DIR` |
| `agent.yaml` | 加 `paths.data_dir: "${DATA_DIR}"` |
| `guardrails/policy.yaml` | 加备份/checkpoint 目录的 write_file 规则 |
| `AGENT_LOG.md` | 记录 |
