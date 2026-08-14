"""内建工具：抓取页面 HTML + 浏览器模式（nju-browser 服务）。"""
import os

import httpx

from .registry import Tool


def _browser_base() -> str:
    """nju-browser 服务地址：BROWSER_PORT 环境变量，默认 4100。"""
    port = os.environ.get("BROWSER_PORT", "4100")
    return f"http://127.0.0.1:{port}"


def _fetch_url(url: str, timeout: float = 20.0) -> str:
    resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                     headers={"User-Agent": "Mozilla/5.0 (compatible; explorer-agent/0.1)"})
    resp.raise_for_status()
    return resp.text


def _browser_fetch(url: str, timeout: float = 30.0) -> str:
    """经 nju-browser 浏览器服务导航并提取页面（可访问需登录/JS 渲染页面）。

    浏览器服务需先手动启动（node nju-browser-server.js）并完成 SSO 扫码登录。
    """
    base = _browser_base()
    try:
        r = httpx.post(f"{base}/navigate", json={"url": url}, timeout=timeout)
        if r.status_code != 200:
            return f"浏览器服务 navigate 失败（HTTP {r.status_code}），请确认 nju-browser-server 已启动并登录"
        r = httpx.post(f"{base}/extract", json={}, timeout=timeout)
        if r.status_code != 200:
            return f"浏览器服务 extract 失败（HTTP {r.status_code}）"
        data = r.json()
    except Exception as e:
        return f"浏览器服务不可用（{e}）——需登录/JS 渲染的页面无法访问；请先启动 nju-browser-server（node nju-browser-server.js）并扫码登录，再用 browser_fetch"
    lines = [f"页面标题: {data.get('title', '')}", f"页面 URL: {data.get('url', '')}"]
    text = (data.get("text") or "").strip()
    if text:
        lines.append(f"页面文本:\n{text[:3000]}")
    links = data.get("links") or []
    if links:
        lines.append("页面链接:")
        for l in links[:20]:
            lines.append(f"  - {l.get('text', '')} ({l.get('href', '')})")
    return "\n".join(lines)


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
        Tool(
            name="browser_fetch",
            description=(
                "经 nju-browser 浏览器服务导航并提取页面（返回标题/文本/链接）。"
                "用于需登录（SSO）或 JS 动态渲染的页面——HTTP fetch_url 抓不到时用这个。"
                "需先启动 nju-browser-server（node nju-browser-server.js）并完成扫码登录。"
            ),
            parameters={
                "type": "object",
                "properties": {"url": {"type": "string", "description": "要访问的页面 URL"}},
                "required": ["url"],
            },
            handler=_browser_fetch,
            require_approval=False,
        ),
    ]
