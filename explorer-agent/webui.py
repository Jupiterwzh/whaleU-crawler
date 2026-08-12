# webui.py
"""单页表单 WebUI：输入问题 → 复用 query.answer() 查询 → 展示答案。零第三方依赖。"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from query import load_env, answer

_PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>📰 南京大学通知查询</title>
<style>
body {{ font-family: sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; }}
h1 {{ color: #1a3a6b; }}
input[type=text] {{ width: 100%; padding: 12px; font-size: 16px; border: 1px solid #ccc; border-radius: 6px; }}
button {{ margin-top: 12px; padding: 12px 28px; font-size: 16px; background: #1a3a6b; color: #fff; border: none; border-radius: 6px; cursor: pointer; }}
button:disabled {{ background: #888; }}
#answer {{ margin-top: 20px; white-space: pre-wrap; background: #f5f7fa; padding: 16px; border-radius: 6px; }}
#loading {{ display: none; color: #888; margin-top: 12px; }}
</style>
</head>
<body>
<h1>📰 南京大学通知查询</h1>
<form method="post">
  <input type="text" name="question" placeholder="例如：计算机学院最近有什么通知？" value="{q}" required>
  <br>
  <button type="submit" id="btn">🔍 查询</button>
</form>
<div id="loading">⏳ Agent 正在检索 RAG / 补充数据，请稍候（约 30-60 秒）…</div>
<div id="answer">{answer}</div>
<script>
document.querySelector('form').addEventListener('submit', function() {{
  document.getElementById('loading').style.display = 'block';
  document.getElementById('btn').disabled = true;
}});
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(_PAGE.format(q="", answer="").encode("utf-8"))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        params = parse_qs(body)
        q = params.get("question", [""])[0].strip()

        answer_html = ""
        if q:
            try:
                result = answer(q)
                import html as _h
                answer_html = _h.escape(result)
            except Exception as e:
                answer_html = f"❌ 查询失败: {_h.escape(str(e))}"

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(_PAGE.format(q=q, answer=answer_html).encode("utf-8"))

    def log_message(self, fmt, *args):
        pass  # 静默访问日志


def make_server(host: str, port: int) -> HTTPServer:
    load_env()
    return HTTPServer((host, port), Handler)


def main():
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = make_server("0.0.0.0", port)
    print(f"🌐 通知查询 WebUI 已启动: http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
