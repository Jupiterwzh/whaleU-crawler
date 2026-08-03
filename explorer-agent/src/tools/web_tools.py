"""内建工具：抓取页面 HTML。"""
import httpx

from .registry import Tool


def _fetch_url(url: str, timeout: float = 15.0) -> str:
    resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                     headers={"User-Agent": "Mozilla/5.0 (compatible; explorer-agent/0.1)"})
    resp.raise_for_status()
    return resp.text


def make_web_tools() -> list[Tool]:
    return [
        Tool(
            name="fetch_url",
            description="抓取指定 URL 的页面 HTML 内容。用于探索网站结构。",
            parameters={
                "type": "object",
                "properties": {"url": {"type": "string", "description": "要抓取的页面 URL"}},
                "required": ["url"],
            },
            handler=_fetch_url,
            require_approval=False,
        ),
    ]
