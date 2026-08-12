# tests/test_structure_tools.py
"""crawl_structure 工具测试（BFS 网站结构遍历）。"""
from unittest.mock import patch
from src.tools.structure_tools import crawl_structure, _classify_page, _normalize_url


LIST_HTML = """
<html><body>
<ul class="news_list">
  <li class="news"><span class="news_title"><a href="/a/list.htm">通知一</a></span><span class="news_meta">2026-01-01</span></li>
  <li class="news"><span class="news_title"><a href="/b/page.htm">通知二</a></span><span class="news_meta">2026-01-02</span></li>
  <li class="news"><span class="news_title"><a href="/c/page.htm">通知三</a></span><span class="news_meta">2026-01-03</span></li>
  <li class="news"><span class="news_title"><a href="/d/page.htm">通知四</a></span><span class="news_meta">2026-01-04</span></li>
</ul>
</body></html>
"""

DETAIL_HTML = """
<html><body><div class="article">
  <h1>关于考试安排的通知</h1>
  <p>这是一段很长的正文内容。</p>
  <p>第二段正文。</p>
</div></body></html>
"""

HOME_HTML = """
<html><body>
<div class="nav">
  <a href="/">首页</a>
  <a href="/1702/list.htm">院内公告</a>
  <a href="/intro.htm">学院简介</a>
  <a href="https://mp.weixin.qq.com/s/abc">微信公众号</a>
</div>
</body></html>
"""


def test_normalize_url():
    assert _normalize_url("https://cs.nju.edu.cn/") == "https://cs.nju.edu.cn/"
    assert _normalize_url("https://cs.nju.edu.cn/a#frag") == "https://cs.nju.edu.cn/a"
    assert _normalize_url("http://cs.nju.edu.cn/a") == "https://cs.nju.edu.cn/a"


def test_classify_list_page():
    assert _classify_page(LIST_HTML, "https://cs.nju.edu.cn/1702/list.htm") == "list"


def test_classify_detail_page():
    assert _classify_page(DETAIL_HTML, "https://cs.nju.edu.cn/a/page.htm") == "detail"


def test_crawl_structure_bfs():
    """BFS 遍历：首页列出链接，识别列表页与中间页，外链标记停止。"""
    pages = {
        "https://cs.nju.edu.cn/": HOME_HTML,
        "https://cs.nju.edu.cn/1702/list.htm": LIST_HTML,
        "https://cs.nju.edu.cn/intro.htm": "<html><body><h1>简介</h1><p>学院简介内容</p></body></html>",
    }
    def fake_get(url, **kw):
        resp = type("R", (), {})()
        resp.text = pages.get(url, DETAIL_HTML)
        resp.raise_for_status = lambda: None
        return resp
    with patch("httpx.get", side_effect=fake_get):
        tree = crawl_structure("https://cs.nju.edu.cn/", max_depth=2)
    assert tree["domain"] == "cs.nju.edu.cn"
    nodes = tree["nodes"]
    assert len(nodes) >= 3
    # 院内公告应识别为列表页
    list_nodes = [n for n in nodes if n["type"] == "list"]
    assert any("1702/list.htm" in n["url"] for n in list_nodes)


def test_crawl_structure_external_stops():
    """外链（mp.weixin）被记录但不深入抓取。"""
    calls = []
    def fake_get(url, **kw):
        calls.append(url)
        resp = type("R", (), {})()
        resp.text = HOME_HTML
        resp.raise_for_status = lambda: None
        return resp
    with patch("httpx.get", side_effect=fake_get):
        crawl_structure("https://cs.nju.edu.cn/", max_depth=2)
    # 只抓了首页（外链和内部页可能也抓，但外链 mp.weixin 不应被深入）
    assert not any("mp.weixin" in c for c in calls)


def test_tool_handler_returns_json_string():
    """crawl_structure 工具 handler 返回 JSON 字符串（Agent 友好）。"""
    import json as _json
    from src.tools.structure_tools import make_structure_tools
    tools = make_structure_tools()
    tool = [t for t in tools if t.name == "crawl_structure"][0]
    with patch("httpx.get", side_effect=lambda url, **kw: type("R", (), {
        "text": HOME_HTML, "raise_for_status": lambda: None})()):
        out = tool.handler(url="https://cs.nju.edu.cn/")
    assert isinstance(out, str)
    parsed = _json.loads(out)
    assert parsed["domain"] == "cs.nju.edu.cn"
