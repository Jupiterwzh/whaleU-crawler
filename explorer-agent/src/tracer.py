# src/tracer.py
"""轨迹记录：每轮决策+观察，会话末落盘。"""
import json
import time
from pathlib import Path


class Tracer:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.trace_id = f"trace-{int(time.time())}"
        self._records: list[dict] = []
        self._start = time.time()

    def record(self, step: int, text: str, action: dict, observation: str = ""):
        self._records.append({
            "trace_id": self.trace_id,
            "step": step,
            "timestamp": time.time() - self._start,
            "text": text,
            "action": action,
            "observation": observation,
        })

    def flush(self):
        path = self.output_dir / f"{self.trace_id}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for r in self._records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"📊 轨迹已保存: {path} ({len(self._records)} 步)")
