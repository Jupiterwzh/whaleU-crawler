"""权限门控：危险动作拦截。"""
import yaml


class Guardrail:
    def __init__(self, rules: list[dict]):
        self.rules = rules

    @classmethod
    def from_yaml(cls, path: str) -> "Guardrail":
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(data.get("rules", []))

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
            verdict = rule["action"]
            reason = rule.get("reason", "")
            if verdict == "deny":
                return False, f"动作被拒绝: {reason}"
            if verdict == "ask_user":
                ans = input(f"⚠️ {reason}。允许吗? (y/n): ")
                if ans.lower() == "y":
                    return True, f"用户批准: {reason}"
                return False, f"用户拒绝: {reason}"
            return True, ""
        return True, ""
