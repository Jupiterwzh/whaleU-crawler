# tests/test_tracer.py
import json
from pathlib import Path
from src.tracer import Tracer

def test_record_and_flush(tmp_path):
    t = Tracer(output_dir=str(tmp_path))
    t.record(step=1, text="思考", action={"type": "call_tool", "tool": "fetch_url"}, observation="<html>")
    t.flush()
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").strip().split("\n")
    rec = json.loads(lines[0])
    assert rec["step"] == 1
    assert rec["action"]["tool"] == "fetch_url"
    assert rec["observation"] == "<html>"
