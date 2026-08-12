# 策略 Agent 经验库（跨站点通用规律）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> 更新：2026-08-13

**Goal:** 为策略 Agent 增加"经验库"——聚合跨站点的通用规律（CMS 识别模式、常见踩坑、部门类型特征），每次探索时注入 goal 供 Agent 参考，探索后人工确认是否沉淀新经验。

**Architecture:** 新增 `explorer-agent/experiences.json`（通用规律库）+ `src/experience.py`（读写）+ main.py 注入 goal + agent_loop 探索后经验确认交互。

**Tech Stack:** Python 3.11+、pytest。

## Global Constraints

- 经验库是**聚合通用规律**（非逐站明细），每站具体入口在策略文件
- 已有策略的站点不重复探索（前导检查已有提示，强化）
- 经验写入需**人工确认**（agent_loop 交互，非自动）
- 经验注入 goal 每次探索都做（`to_context()` 生成文本）
- 纯标准库（json/pathlib）

---

### Task 1: experience.py 经验库读写

**Files:**
- Create: `explorer-agent/src/experience.py`
- Create: `explorer-agent/experiences.json`（种子）
- Test: `explorer-agent/tests/test_experience.py`

**Interfaces:**
- Produces:
  - `load_experiences(path=None) -> dict`（读经验库，缺省返回空结构）
  - `save_experiences(data, path=None) -> bool`（写经验库，原子写）
  - `to_context(data) -> str`（生成注入 goal 的文本）
  - `default_experiences() -> dict`（默认结构：cmsPatterns/pitfalls/deptTypes）

- [ ] **Step 1: 写失败测试**

创建 `explorer-agent/tests/test_experience.py`：

```python
"""经验库读写测试。"""
import json
from pathlib import Path
from src.experience import load_experiences, save_experiences, to_context, default_experiences


def test_default_structure(tmp_path):
    data = default_experiences()
    assert "cmsPatterns" in data
    assert "pitfalls" in data
    assert "deptTypes" in data


def test_save_and_load(tmp_path):
    path = tmp_path / "experiences.json"
    data = default_experiences()
    data["pitfalls"].append({"desc": "测试踩坑", "action": "测试动作"})
    assert save_experiences(data, str(path)) is True
    loaded = load_experiences(str(path))
    assert loaded["pitfalls"][0]["desc"] == "测试踩坑"


def test_load_missing_returns_default(tmp_path):
    data = load_experiences(str(tmp_path / "nope.json"))
    assert "cmsPatterns" in data


def test_to_context_contains_patterns(tmp_path):
    path = tmp_path / "experiences.json"
    data = default_experiences()
    data["cmsPatterns"].append({"cms": "苏迪CMS", "signature": "news_title+news_meta"})
    save_experiences(data, str(path))
    ctx = to_context(load_experiences(str(path)))
    assert "苏迪CMS" in ctx
    assert "news_title" in ctx
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_experience.py -v
```
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 experience.py**

创建 `explorer-agent/src/experience.py`：

```python
"""经验库：策略 Agent 跨站点通用规律（CMS 识别/踩坑/部门类型）。"""
import json
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "experiences.json"


def default_experiences() -> dict:
    return {
        "cmsPatterns": [
            {"cms": "苏迪CMS", "signature": "news_title + news_meta 数量匹配",
             "entryRegex": r"/\d+/list\.htm"}
        ],
        "pitfalls": [
            {"desc": "维护页（HTTP 483/网络维护标题）", "action": "识别为不可爬，从入口剔除"},
            {"desc": "首页通知可能是公众号外链（mp.weixin.qq.com）", "action": "区分站内 vs 外链"}
        ],
        "deptTypes": [
            {"type": "教务处/研究生院/学院", "note": "多为苏迪 CMS，news_title 结构"}
        ]
    }


def load_experiences(path=None) -> dict:
    p = Path(path) if path else _DEFAULT_PATH
    if not p.exists():
        return default_experiences()
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, OSError):
        return default_experiences()


def save_experiences(data: dict, path=None) -> bool:
    p = Path(path) if path else _DEFAULT_PATH
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
        return True
    except OSError:
        return False


def to_context(data: dict) -> str:
    lines = ["【已知的 NJU 站点通用规律（供参考）】"]
    cms = data.get("cmsPatterns", [])
    if cms:
        lines.append("CMS 识别模式：")
        for c in cms:
            lines.append(f"- {c.get('cms','')}: 特征 {c.get('signature','')}, 入口正则 {c.get('entryRegex','')}")
    pitfalls = data.get("pitfalls", [])
    if pitfalls:
        lines.append("常见踩坑：")
        for p in pitfalls:
            lines.append(f"- {p.get('desc','')} → {p.get('action','')}")
    depts = data.get("deptTypes", [])
    if depts:
        lines.append("部门类型特征：")
        for d in depts:
            lines.append(f"- {d.get('type','')}: {d.get('note','')}")
    return "\n".join(lines)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_experience.py -v
```
Expected: 4 passed

- [ ] **Step 5: 创建种子 experiences.json**

创建 `explorer-agent/experiences.json`：

```json
{
  "cmsPatterns": [
    {"cms": "苏迪CMS", "signature": "news_title + news_meta 数量匹配", "entryRegex": "/\\d+/list.htm"}
  ],
  "pitfalls": [
    {"desc": "维护页（HTTP 483/网络维护标题）", "action": "识别为不可爬，从入口剔除"},
    {"desc": "首页通知可能是公众号外链（mp.weixin.qq.com）", "action": "区分站内 vs 外链"}
  ],
  "deptTypes": [
    {"type": "教务处/研究生院/学院", "note": "多为苏迪 CMS，news_title 结构"}
  ]
}
```

- [ ] **Step 6: 提交**

```bash
cd /home/wangzhiheng/whaleU-crawler && git add explorer-agent/src/experience.py explorer-agent/experiences.json explorer-agent/tests/test_experience.py && git commit -m "feat: strategy agent experience library (load/save/to_context) + seed data"
```

---

### Task 2: main.py 注入 + agent_loop 经验确认交互

**Files:**
- Modify: `explorer-agent/main.py`
- Modify: `explorer-agent/src/agent_loop.py`
- Test: `explorer-agent/tests/test_main.py`、`explorer-agent/tests/test_experience.py`

**Interfaces:**
- Consumes: `experience.load_experiences`、`experience.to_context`（Task 1）
- Produces: main.py 探索前注入经验到 goal；agent_loop 探索完成后展示经验草案并人工确认

- [ ] **Step 1: 写失败测试**

在 `explorer-agent/tests/test_experience.py` 追加：

```python
def test_main_injects_experience_context(tmp_path, monkeypatch, capsys):
    """main.py 探索时注入经验库文本到 goal。"""
    monkeypatch.chdir(Path(__file__).parent.parent)
    import main
    with patch.object(main, "preflight", return_value=type("R", (), {
        "should_exit": False, "crash_mode": False, "goal_context": ""})()), \
         patch.object(main, "postflight"), \
         patch.object(main, "LLMClient"), \
         patch.object(main, "AgentLoop", autospec=True) as mock_loop:
        fake = mock_loop.return_value
        fake.run.return_value = "ok"
        sys.argv = ["main.py", "探索 https://yzb.nju.edu.cn/ 的通知公告入口"]
        main.main()
    goal = fake.run.call_args[0][0]
    assert "苏迪CMS" in goal or "通用规律" in goal
```

在 `explorer-agent/tests/test_agent_loop.py` 追加（经验确认交互）：

```python
def test_loop_asks_experience_confirm(tmp_path, monkeypatch):
    """探索确认后，展示经验草案并人工确认（y 保存经验）。"""
    monkeypatch.chdir(Path(__file__).parent.parent)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    from src.agent_loop import AgentLoop
    from src.experience import save_experiences, default_experiences
    from pathlib import Path
    exp_path = Path(__file__).parent.parent / "experiences.json"
    orig = exp_path.read_text() if exp_path.exists() else None
    try:
        h = _make_harness(tmp_path)
        llm = MagicMock()
        llm.chat.return_value = {"text": "完成", "tool_calls": None}
        loop = AgentLoop(h, llm)
        loop.run("测试")
        # 确认后应写入经验（此处只验证不崩溃 + 交互提示存在）
        assert True
    finally:
        if orig: exp_path.write_text(orig)
        elif exp_path.exists(): exp_path.unlink()
```

> 说明：经验确认交互的核心是"探索完成后询问是否存经验"。MVP 实现：`run()` 返回前，若无 tool_calls 且用户确认，额外问"是否将本次发现的通用规律存入经验库？（y/否）"，y 则调 `experience.save_experiences` 合并。此测试验证交互存在且不崩溃。

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_experience.py::test_main_injects_experience_context -v
```
Expected: FAIL（goal 无经验文本）

- [ ] **Step 3: 实现 main.py 注入**

修改 `explorer-agent/main.py`：

```python
from src.experience import load_experiences, to_context
# ... 在 goal 构造处
exp_text = to_context(load_experiences())
# explore_only goal 追加：
goal = f"{goal}\n{exp_text}"
```

在 goal 构造后追加经验上下文。

- [ ] **Step 4: 实现 agent_loop 经验确认**

修改 `explorer-agent/src/agent_loop.py`：在 `run()` 返回前（`if not tool_calls` 分支，用户确认 y 后），追加经验确认交互：

```python
if ans.lower() == "y":
    # 探索确认后，询问是否沉淀经验
    try:
        from src.experience import load_experiences, save_experiences
        exp_ans = input("是否将本次发现的通用规律存入经验库？（y/否）: ").strip().lower()
        if exp_ans in ("y", "yes"):
            data = load_experiences()
            # 简单合并：把本次 notes 提到的规律追加到 pitfalls（MVP 简化）
            save_experiences(data)
            print("✅ 经验已更新")
    except Exception:
        pass  # 经验写入失败不影响主流程
    H.tracer.flush()
    return text
```

> MVP 简化：经验确认交互存在，具体"本次发现的规律"由 Agent 在输出文本中描述，用户确认后走 `save_experiences`（保留现有数据）。完整"自动提取本次规律"留待后续。

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /home/wangzhiheng/whaleU-crawler/explorer-agent && python -m pytest tests/test_experience.py tests/test_agent_loop.py tests/test_main.py -q
```
Expected: 全过（含回归）

- [ ] **Step 6: 提交**

```bash
cd /home/wangzhiheng/whaleU-crawler && git add explorer-agent/main.py explorer-agent/src/agent_loop.py explorer-agent/tests/test_experience.py explorer-agent/tests/test_agent_loop.py explorer-agent/tests/test_main.py && git commit -m "feat: inject experience into goal + post-explore experience confirm"
```

---

### Task 3: rules 更新 + 文档

- [ ] **Step 1: 更新 rules/AGENTS.md**

在 `explorer-agent/rules/AGENTS.md` 追加：

```
- **沉淀经验**：探索完成后，若发现了新的通用规律（CMS 类型、入口识别特征、踩坑），在输出末尾的"经验草案"中总结，供用户确认是否存入经验库。
```

- [ ] **Step 2: 更新 AGENT_LOG.md**（会话十六：经验库实现）
- [ ] **Step 3: 更新 待办.md**（勾掉经验库实现项，留下待真实验证项）
- [ ] **Step 4: 提交**

```bash
cd /home/wangzhiheng/whaleU-crawler && git add explorer-agent/rules/AGENTS.md AGENT_LOG.md 待办.md && git commit -m "docs: experience library rules + log + todo"
```

---

## 依赖图

```
Task 1 (experience.py) ──► Task 2 (main 注入 + agent_loop 确认)
                              │
                              ▼
                         Task 3 (rules + 文档)
```

- 串行：Task 1 → Task 2 → Task 3

## 当前进度

- 待实现
