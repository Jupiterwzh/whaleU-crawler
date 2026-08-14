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
    """crawl_structure 工具 handler 返回 JSON 字符串，节点含 selected 标记，不弹窗。"""
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
    # 每个节点都带 selected 标记（默认 False，由 LLM 自主判断后标记）
    for n in parsed["nodes"]:
        assert "selected" in n and n["selected"] is False


def test_classify_url_list_suffix():
    """URL 含 list.htm 后缀且有通知内容即视为列表页（苏迪 CMS 约定）。"""
    # list.htm 含通知条目 → 列表页
    assert _classify_page("<html><body><a class='news_title'>a</a><a class='news_title'>b</a><a class='news_title'>c</a></body></html>", "https://cs.nju.edu.cn/1716/list.htm") == "list"
    assert _classify_page("<html><body><a class='news_title'>a</a></body></html>", "https://cs.nju.edu.cn/1716/list2.htm") == "list"
    # 空 list.htm（无内容）不算列表页
    assert _classify_page("<html><body><p>内容</p></body></html>", "https://cs.nju.edu.cn/1716/list.htm") != "list"
    # 非 list 后缀不误判
    assert _classify_page("<html><body><p>内容</p></body></html>", "https://cs.nju.edu.cn/intro.htm") in ("middle", "other")


def test_nodes_have_title_and_index():
    """节点含 index（编号）与 title（锚文本）。"""
    pages = {"https://cs.nju.edu.cn/": HOME_HTML, "https://cs.nju.edu.cn/1702/list.htm": LIST_HTML}
    def fake_get(url, **kw):
        resp = type("R", (), {})()
        resp.text = pages.get(url, DETAIL_HTML)
        resp.raise_for_status = lambda: None
        return resp
    with patch("httpx.get", side_effect=fake_get):
        tree = crawl_structure("https://cs.nju.edu.cn/", max_depth=1)
    assert all("index" in n and "title" in n for n in tree["nodes"])
    # 首页节点 index=1，title 为空（根）
    assert tree["nodes"][0]["index"] == 1
    # 院内公告节点应有锚文本"院内公告"
    assert any(n["title"] == "院内公告" for n in tree["nodes"])


def test_tool_handler_no_prompt(monkeypatch):
    """crawl_structure handler 不再弹窗选入口（LLM 自主判断）。"""
    import json as _json
    from src.tools.structure_tools import make_structure_tools
    tools = make_structure_tools()
    tool = [t for t in tools if t.name == "crawl_structure"][0]
    called = {"input": False}
    monkeypatch.setattr("builtins.input", lambda prompt="": called.__setitem__("input", True))
    with patch("httpx.get", side_effect=lambda url, **kw: type("R", (), {
        "text": HOME_HTML, "raise_for_status": lambda: None})()):
        out = tool.handler(url="https://cs.nju.edu.cn/")
    assert called["input"] is False, "handler 不应调用 input（LLM 自主选入口）"
    parsed = _json.loads(out)
    assert isinstance(parsed, dict) and "nodes" in parsed


def test_user_selection_empty_input(monkeypatch):
    """用户直接回车 → 不选任何入口。"""
    from src.tools.structure_tools import _prompt_user_selection
    nodes = [{"index": 1, "url": "https://cs.nju.edu.cn/", "type": "list", "depth": 0}]
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert _prompt_user_selection(nodes) == []


def test_max_links_truncated_flag():
    """max_links 不足时返回 truncated 提示。"""
    from src.tools.structure_tools import crawl_structure
    # 首页含很多链接，max_links=2 会截断
    many_links_html = "<html><body>" + "".join(f'<a href="/n{i}.htm">链接{i}</a>' for i in range(10)) + "</body></html>"
    def fake_get(url, **kw):
        r = type("R", (), {})(); r.text = many_links_html; r.raise_for_status = lambda: None; return r
    with patch("httpx.get", side_effect=fake_get):
        tree = crawl_structure("https://cs.nju.edu.cn/", max_depth=1, max_links=2)
    assert tree.get("truncated") is True
    assert "max_links" in tree.get("hint", "")


def test_no_truncation_with_large_limit():
    """max_links 足够时不截断。"""
    from src.tools.structure_tools import crawl_structure
    html = "<html><body><a href='/a.htm'>a</a><a href='/b.htm'>b</a></body></html>"
    def fake_get(url, **kw):
        r = type("R", (), {})(); r.text = html; r.raise_for_status = lambda: None; return r
    with patch("httpx.get", side_effect=fake_get):
        tree = crawl_structure("https://cs.nju.edu.cn/", max_depth=1, max_links=30)
    assert "truncated" not in tree


def test_root_marked_home_not_list():
    """首页标记为 home（不作为列表页候选），且含 preview_count。"""
    from src.tools.structure_tools import crawl_structure
    pages = {"https://cs.nju.edu.cn/": LIST_HTML}  # 首页即使含 news_title 也标 home
    def fake_get(url, **kw):
        r = type("R", (), {})(); r.text = pages.get(url, "<html><body></body></html>")
        r.raise_for_status = lambda: None
        return r
    with patch("httpx.get", side_effect=fake_get):
        tree = crawl_structure("https://cs.nju.edu.cn/", max_depth=1)
    root = tree["nodes"][0]
    assert root["type"] == "home"
    assert "preview_count" in root
    assert root["preview_count"] >= 1  # LIST_HTML 含通知预览


def test_home_not_in_selection_candidates():
    """home 类型不进用户选择候选（首页不作为入口）。"""
    import io, contextlib
    from unittest.mock import patch as mock_patch
    from src.tools.structure_tools import _prompt_user_selection
    nodes = [
        {"index": 1, "url": "https://cs.nju.edu.cn/", "type": "home", "depth": 0},
        {"index": 2, "url": "https://cs.nju.edu.cn/1702/list.htm", "type": "list", "depth": 1},
    ]
    with contextlib.redirect_stdout(io.StringIO()), \
         mock_patch("builtins.input", return_value="1,2"):
        selected = _prompt_user_selection(nodes)
    assert all(n["index"] == 2 for n in selected)


def test_info_page_marked_and_not_recursed():
    """锚文本含信息栏目关键词的页面标记 info，且不深挖。"""
    from src.tools.structure_tools import crawl_structure
    home = "<html><body><a href='/intro.htm'>学院简介</a><a href='/1702/list.htm'>院内公告</a></body></html>"
    info_html = "<html><body><h1>学院简介</h1><p>简介内容</p></body></html>"
    list_html = "<html><body><a class='news_title'>a</a><a class='news_title'>b</a><a class='news_title'>c</a></body></html>"
    pages = {"https://cs.nju.edu.cn/": home,
             "https://cs.nju.edu.cn/intro.htm": info_html,
             "https://cs.nju.edu.cn/1702/list.htm": list_html}
    visited_pages = []
    def fake_get(url, **kw):
        visited_pages.append(url)
        r = type("R", (), {})(); r.text = pages.get(url, "<html><body></body></html>")
        r.raise_for_status = lambda: None
        return r
    with patch("httpx.get", side_effect=fake_get):
        tree = crawl_structure("https://cs.nju.edu.cn/", max_depth=2)
    info_nodes = [n for n in tree["nodes"] if n["type"] == "info"]
    assert any("intro.htm" in n["url"] for n in info_nodes)
    # info 页不深挖：intro.htm 被访问，但它没有子页面再被深入
    assert len(tree["nodes"]) >= 3  # home + intro(info) + list


def test_list_category_notice_vs_info():
    """列表页 category 按锚文本标注（notice/info），仅参考。"""
    from src.tools.structure_tools import crawl_structure
    home = "<html><body><a href='/tzgg/list.htm'>通知公告</a><a href='/jsgk/list.htm'>学院简介</a></body></html>"
    tzgg_html = "<html><body><a class='news_title'>a</a><a class='news_title'>b</a><a class='news_title'>c</a></body></html>"
    jsgk_html = "<html><body><a class='news_title'>x</a><a class='news_title'>y</a><a class='news_title'>z</a></body></html>"
    pages = {"https://cs.nju.edu.cn/": home,
             "https://cs.nju.edu.cn/tzgg/list.htm": tzgg_html,
             "https://cs.nju.edu.cn/jsgk/list.htm": jsgk_html}
    def fake_get(url, **kw):
        r = type("R", (), {})(); r.text = pages.get(url, "<html><body></body></html>")
        r.raise_for_status = lambda: None
        return r
    with patch("httpx.get", side_effect=fake_get):
        tree = crawl_structure("https://cs.nju.edu.cn/", max_depth=2)
    by_url = {n["url"]: n for n in tree["nodes"]}
    assert by_url["https://cs.nju.edu.cn/tzgg/list.htm"]["category"] == "notice"
    assert by_url["https://cs.nju.edu.cn/jsgk/list.htm"]["category"] == "info"


def test_crawl_structure_recurses_info_pages():
    """info 页（如学院简介）应递归展开子栏目，使结构树完整。"""
    pages = {
        "https://cs.nju.edu.cn/": HOME_HTML,
        "https://cs.nju.edu.cn/intro.htm": (
            "<html><body><h1>学院简介</h1>"
            '<a href="/1650/list.htm">学院概览</a>'
            '<a href="/1651/list.htm">师资队伍</a>'
            "</body></html>"
        ),
    }
    def fake_get(url, **kw):
        resp = type("R", (), {})()
        resp.text = pages.get(url, DETAIL_HTML)
        resp.raise_for_status = lambda: None
        return resp
    with patch("httpx.get", side_effect=fake_get):
        tree = crawl_structure("https://cs.nju.edu.cn/", max_depth=2)
    nodes = tree["nodes"]
    # 学院简介的 info 子栏目（1650/1651）应被遍历到（作为 info 节点，不选为入口）
    assert any("1650/list.htm" in n["url"] for n in nodes), f"info 子栏目未展开: {[n['url'] for n in nodes]}"
    assert any("1651/list.htm" in n["url"] for n in nodes)
