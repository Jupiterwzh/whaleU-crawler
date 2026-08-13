# src/tools/structure_tools.py
"""策略 Agent 工具：crawl_structure —— BFS 网站结构遍历，确定性返回结构树。

替代 Agent 用 LLM 逐页判断页面类型，省 token 且可靠。
"""
import re
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from .registry import Tool

_LIST_SIGNS = (
    re.compile(r'class=["\']news_title["\']', re.I),
    re.compile(r'class=["\']link-title["\']', re.I),
    re.compile(r'class=["\']news_date["\']', re.I),
    re.compile(r'class=["\']news_meta["\']', re.I),
)
_DETAIL_SIGNS = (
    re.compile(r'class=["\']article["\']', re.I),
    re.compile(r'<h1[^>]*>[^<]{4,}</h1>', re.I),
)
_UA = "Mozilla/5.0 (compatible; explorer-agent/0.1)"


def _normalize_url(url: str) -> str:
    """URL 规范化：去 fragment、统一 https、保留 path 层级。"""
    if not url:
        return url
    p = urlparse(url)
    host = p.hostname or ""
    scheme = "https" if p.scheme in ("http", "https") else p.scheme
    path = p.path.rstrip("/") or "/"
    return urlunparse((scheme, host, path, "", "", ""))


def _same_domain(url: str, domain: str) -> bool:
    try:
        return urlparse(url).hostname == domain
    except Exception:
        return False


def _count_notice_links(html: str) -> int:
    """统计页内通知条目数：news_title / link-title / li+日期 / dataList 等模式。"""
    count = 0
    count += len(re.findall(r'class=["\']news_title["\']', html, re.I))
    count += len(re.findall(r'class=["\']link-title["\']', html, re.I))
    count += len(re.findall(r'class=["\'][^"\']*news_date[^"\']*["\']', html, re.I))
    count += len(re.findall(r'class=["\'][^"\']*news_meta[^"\']*["\']', html, re.I))
    count += len(re.findall(r'dataList\s*=\s*\[', html, re.I))
    count += len(re.findall(r'<li[^>]*>[\s\S]{1,200}?href=["\'][^"\']+["\']', html, re.I))
    return count


def _classify_page(html: str, url: str) -> str:
    """页面分类：list（列表页）/ detail（详情页）/ middle（中间页）/ other（功能页）。

    升级：复用爬虫 isNotificationListPage 的多模式判定（news_title/link-title/news_date/
    news_meta/dataList/li+date），降低误判；URL 含 list 后缀也算列表页。
    """
    if not html:
        return "other"

    notice_count = _count_notice_links(html)

    # 列表页：通知条目数达到阈值（多信号合计）
    if notice_count >= 3:
        return "list"
    # URL 约定：苏迪 CMS 的 list.htm / listN.htm 都是列表页
    path = urlparse(url).path.lower()
    if re.search(r"(^|/)list\d*\.htm$", path) and notice_count >= 1:
        return "list"

    # 详情页：article/h1 + 少量链接
    detail_hits = sum(1 for s in _DETAIL_SIGNS if s.search(html))
    links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', html)
    if detail_hits >= 1 and len(links) <= 5:
        return "detail"
    if len(links) >= 3:
        return "middle"
    return "other"


def _extract_links(html: str, base_url: str, domain: str) -> list[tuple[str, str]]:
    """提取页内同域链接（规范化 + 去重），返回 (URL, 锚文本) 列表。"""
    links: dict[str, str] = {}
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>', html, re.I):
        href, inner = m.group(1), m.group(2)
        if href.startswith(("javascript:", "#", "mailto:", "tel:")):
            continue
        abs_url = urljoin(base_url, href)
        if not _same_domain(abs_url, domain):
            continue
        norm = _normalize_url(abs_url)
        if norm in links:
            continue
        # 提取锚文本：去标签、去空白
        text = re.sub(r"<[^>]+>", "", inner)
        text = re.sub(r"\s+", " ", text).strip()
        links[norm] = text[:40]
    return list(links.items())


def crawl_structure(root_url: str, max_depth: int = 4, max_links: int = 30) -> dict:
    """BFS 遍历站点，返回结构树。

    - visited 规范化去重防循环
    - domain 白名单（外链停止）
    - 页面分类：list/detail/middle/other
    - 节点含 index（全局编号）与 title（锚文本，首页来源）
    - max_depth/max_links 防爆炸
    """
    root = _normalize_url(root_url)
    domain = urlparse(root).hostname
    visited: set[str] = set()
    nodes: list[dict] = []
    queue: deque[tuple[str, int, str]] = deque([(root, 0, "")])

    while queue:
        url, depth, anchor = queue.popleft()
        if url in visited or depth > max_depth:
            continue
        visited.add(url)
        try:
            resp = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": _UA})
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            nodes.append({"index": len(nodes) + 1, "url": url, "title": anchor,
                          "type": "error", "depth": depth, "error": str(e)[:80]})
            continue

        page_type = _classify_page(html, url)
        nodes.append({"index": len(nodes) + 1, "url": url, "title": anchor,
                      "type": page_type, "depth": depth})

        # 列表页/详情页/other 不递归；外链不深入。
        # 例外：根页（depth 0）即使判为 list 也递归，因为首页通常兼作导航入口。
        if depth == 0 or page_type not in ("list", "detail", "other"):
            if depth < max_depth:
                for link, text in _extract_links(html, url, domain)[:max_links]:
                    if link not in visited:
                        queue.append((link, depth + 1, text))

    return {"domain": domain, "root": root, "nodes": nodes}


def make_structure_tools() -> list[Tool]:
    def handler(url, max_depth=4, max_links=30):
        import json as _json
        return _json.dumps(crawl_structure(url, max_depth, max_links), ensure_ascii=False, indent=2)

    return [
        Tool(
            name="crawl_structure",
            description=(
                "BFS 遍历指定站点，返回网站结构树（JSON，节点含 URL/type/depth）。"
                "type 取值：list=通知列表页✅ / middle=中间页 / detail=详情页 / other=功能页 / error=抓取失败。"
                "自动防循环、外链停止。用于理解整站结构后选择要爬取的列表页入口。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "站点根 URL"},
                    "max_depth": {"type": "integer", "description": "最大遍历深度，默认 4"},
                    "max_links": {"type": "integer", "description": "每页最多检查链接数，默认 30"},
                },
                "required": ["url"],
            },
            handler=handler,
            require_approval=False,
        ),
    ]
