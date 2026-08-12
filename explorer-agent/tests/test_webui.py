# tests/test_webui.py
from unittest.mock import patch
import threading
import http.client
import time


def _start_server(port):
    import webui
    server = webui.make_server("127.0.0.1", port)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, t


def test_get_returns_form_page():
    import webui
    server, t = _start_server(0)
    port = server.server_address[1]
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = resp.read().decode()
        assert resp.status == 200
        assert "通知" in body
        assert "form" in body
        conn.close()
    finally:
        server.shutdown()


def test_post_returns_answer(monkeypatch):
    import webui
    server, t = _start_server(0)
    port = server.server_address[1]
    try:
        with patch.object(webui, "answer", return_value="mock 答案") as mock_ans:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            body = "question=%E6%9C%80%E8%BF%91%E6%9C%89%E4%BB%80%E4%B9%88%E9%80%9A%E7%9F%A5"  # 最近有什么通知
            conn.request("POST", "/", body=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
            resp = conn.getresponse()
            html = resp.read().decode()
            assert resp.status == 200
            assert "mock 答案" in html
            assert mock_ans.called
            conn.close()
    finally:
        server.shutdown()
