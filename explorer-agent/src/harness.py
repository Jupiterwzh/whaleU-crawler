# src/harness.py
"""Harness：从 agent.yaml 装配所有零件。"""
import importlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .guardrail import Guardrail
from .tools.rag_tools import make_rag_tools
from .tools.registry import ToolRegistry
from .tracer import Tracer


def _resolve_env(value):
    """把 ${VAR} 替换为环境变量值。"""
    if isinstance(value, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(v) for v in value]
    return value


@dataclass
class Harness:
    system_prompt: str
    rules: str
    tools: ToolRegistry
    guardrail: Guardrail
    tracer: Tracer
    config: dict

    @classmethod
    def from_yaml(cls, path: str, rag_store=None, entry: str = "main") -> "Harness":
        base = Path(path).resolve().parent
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        cfg = _resolve_env(cfg)

        # 规则（按入口选）
        rules_text = ""
        rules_cfg = cfg["query"]["rules"] if entry == "query" else cfg.get("rules", [])
        for r in rules_cfg:
            rules_text += (base / r["path"]).read_text(encoding="utf-8") + "\n"

        # 工具（按入口选工具子集）
        reg = ToolRegistry()
        paths = cfg.get("paths", {})
        tool_cfg = cfg["query"]["tools"]["builtin"] if entry == "query" else cfg["tools"]["builtin"]
        for t in tool_cfg:
            mod = importlib.import_module(t["module"])
            factory = getattr(mod, t["factory"])
            tools = factory(strategies_dir=paths.get("strategies_dir", ".")) if t["factory"] == "make_file_tools" else factory()
            for tool in tools:
                if tool.name == t["name"]:
                    if t.get("require_approval"):
                        tool.require_approval = True
                    reg.register(tool)

        # RAG 工具（query-agent 装配，rag_store 可选）
        if rag_store is not None:
            for tool in make_rag_tools(rag_store, paths.get("crawler_script", "")):
                reg.register(tool)

        # 门控
        project_root = str(base.parent)
        guardrail = Guardrail.from_yaml(
            str(base / cfg["guardrail"]["policy"]),
            context={
                "strategies_dir": str(Path(paths.get("strategies_dir", ".")).resolve()) if paths.get("strategies_dir") else "",
                "project_root": project_root,
            },
        )

        # 轨迹
        tracer = Tracer(output_dir=str(base / cfg["tracer"]["output"]))

        if rag_store is not None:
            system_prompt = f"你是 {cfg['agent']['name']}，一个南京大学通知查询 Agent，先用 RAG 检索，不足时调用爬虫补充。"
        else:
            system_prompt = f"你是 {cfg['agent']['name']}，一个南京大学网站探索 Agent。"

        return cls(system_prompt=system_prompt, rules=rules_text, tools=reg,
                   guardrail=guardrail, tracer=tracer, config=cfg)
