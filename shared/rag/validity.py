"""有效时间判定纯函数：无 LLM 依赖，供 RAG 管理 Agent 作确定性底座。"""
import re

_DATE_RE = re.compile(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}(?:日)?")
_MONTH_DAY_RE = re.compile(r"(\d{1,2})月(\d{1,2})日")
_RANGE_WORDS = ("至", "截止", "结束", "期间")
_IMPACT_MAP = (
    (("改造", "工程"), 180),
    (("搬迁", "停用"), 90),
    (("通知", "公示"), 60),
    (("活动", "安排"), 30),
)
_DEFAULT_DAYS = 15


def _norm_date(match: str) -> str:
    s = match.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
    y, m, d = s.split("-")
    return f"{y}-{int(m):02d}-{int(d):02d}"


def extract_dates(text: str) -> list[str]:
    """提取文本中所有完整日期（yyyy-mm-dd / yyyy/mm/dd / yyyy年m月d日），归一为 ISO。"""
    if not text:
        return []
    return [_norm_date(m) for m in _DATE_RE.findall(text)]


def _month_day_dates(text: str, year: str) -> list[str]:
    return [f"{year}-{int(m):02d}-{int(d):02d}" for m, d in _MONTH_DAY_RE.findall(text)]


def _map_impact(text: str) -> tuple[int, str]:
    for keywords, days in _IMPACT_MAP:
        if any(k in text for k in keywords):
            return days, f"无明确时间戳，按影响程度关键词映射为 {days} 天"
    return _DEFAULT_DAYS, f"无明确时间戳与影响词，取默认档位 {_DEFAULT_DAYS} 天"


def judge_validity(text: str, date: str = None, related=None) -> dict:
    """判定文本有效时间。返回 {valid_from, valid_until|effective_days, reason}。

    - 有"至/截止/结束/期间"等时间范围词且含日期 → 取最晚日期为 valid_until
    - 无明确时间戳 → 按影响程度关键词映射 effective_days 档位
    - valid_from 默认 = 发布日 date
    """
    if not text:
        return {"valid_from": date, "effective_days": _DEFAULT_DAYS,
                "reason": "空文本，取默认档位"}
    dates = extract_dates(text)
    if date and _MONTH_DAY_RE.search(text):
        dates += _month_day_dates(text, date.split("-")[0])
    has_range = any(w in text for w in _RANGE_WORDS)
    if has_range and dates:
        latest = max(dates)
        return {"valid_from": date, "valid_until": latest,
                "reason": f"检测到时间范围词，取最晚日期 {latest} 为有效期止"}
    days, reason = _map_impact(text)
    return {"valid_from": date, "effective_days": days, "reason": reason}
