"""经验库：策略 Agent 跨站点通用规律（CMS 识别/踩坑/部门类型）。"""
import json
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "experiences.json"


def default_experiences() -> dict:
    return {"cmsPatterns": [], "pitfalls": [], "deptTypes": []}


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
