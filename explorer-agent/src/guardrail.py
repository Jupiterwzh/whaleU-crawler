"""权限门控：危险动作拦截。"""
import os

import yaml


class Guardrail:
    def __init__(self, rules: list[dict], context: dict | None = None):
        self.rules = rules
        self.context = context or {}

    @classmethod
    def from_yaml(cls, path: str, context: dict | None = None) -> "Guardrail":
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(data.get("rules", []), context=context)

    def _path_in_dir(self, path: str, directory: str) -> bool:
        if not path or not directory:
            return False
        real_path = os.path.realpath(path)
        real_dir = os.path.realpath(directory)
        return real_path == real_dir or real_path.startswith(real_dir + os.sep)

    def _scope_match(self, scope: str, args: dict) -> bool:
        path = args.get("path", "")
        if scope == "outside_strategies":
            return not self._path_in_dir(path, self.context.get("strategies_dir", ""))
        if scope == "inside_strategies":
            return self._path_in_dir(path, self.context.get("strategies_dir", ""))
        if scope == "outside_project":
            return not self._path_in_dir(path, self.context.get("project_root", ""))
        return True

    def allow(self, action: dict) -> tuple[bool, str]:
        tool = action.get("tool", "")
        args = action.get("args", {})
        args_text = " ".join(str(v) for v in args.values())
        for rule in self.rules:
            if rule.get("tools") and tool not in rule["tools"]:
                continue
            pat = rule.get("pattern")
            if pat and pat not in args_text:
                continue
            scope = rule.get("scope")
            if scope and not self._scope_match(scope, args):
                continue
            verdict = rule["action"]
            reason = rule.get("reason", "")
            if verdict == "deny":
                return False, f"动作被拒绝: {reason}"
            if verdict == "ask_user":
                args_preview = ", ".join(
                    f"{k}={v[:80] if isinstance(v, str) and len(v) > 80 else v}"
                    for k, v in args.items()
                )
                ans = input(f"⚠️ [{tool}] {reason}\n  参数: {args_preview}\n  允许吗? (y/n): ")
                if ans.lower() == "y":
                    return True, f"用户批准: {reason}"
                return False, f"用户拒绝: {reason}"
            return True, ""
        return True, ""
