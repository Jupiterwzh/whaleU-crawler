"""RAGStore：JSONL 文档库 + 倒排索引 + 新鲜度刷新 + 有效时间管理（纯标准库）。"""
import hashlib
import json
import math
import re
import time
from datetime import date as _date, timedelta
from pathlib import Path

_CJK = r"[\u4e00-\u9fff]"


class RAGStore:
    """倒排索引存储：按 domain+date 分片存 JSONL，建 current/archive 两级索引。"""

    def __init__(self, base_dir: str, refresh_interval_min: int = 30):
        self._base = Path(base_dir)
        self._docs = self._base / "docs"
        self._current = self._base / "index" / "current"
        self._archive = self._base / "index" / "archive"
        self._meta_path = self._base / "meta.json"
        self._refresh_interval_min = refresh_interval_min
        for d in [self._docs, self._current, self._archive]:
            d.mkdir(parents=True, exist_ok=True)

    # ---- 分词：连续中文 2-gram，英文单词单个 term ----
    @staticmethod
    def _tokenize(text: str) -> list[str]:
        if not text:
            return []
        tokens = []
        for ch in re.findall(_CJK + r"|[\w]+", text):
            if re.fullmatch(_CJK, ch):
                tokens.append(ch)
            else:
                tokens.append(ch.lower())
        # 连续中文做 2-gram（"考试" 独立成词也保留，兼容单字查询）
        bigrams = []
        prev = ""
        for tok in tokens:
            if re.fullmatch(_CJK, tok):
                if prev:
                    bigrams.append(prev + tok)
                prev = tok
            else:
                prev = ""
        return tokens + bigrams

    # ---- 分片路径 ----
    def _slice_path(self, domain: str, date: str) -> Path:
        return self._docs / f"{domain}.{date}.jsonl"

    def _id(self, domain: str, date: str, seq: int) -> str:
        return f"{domain}.{date}.{seq}"

    # ---- 摄取 ----
    def ingest(self, records: list[dict]) -> int:
        added = 0
        for rec in records:
            domain = rec.get("domain", "")
            date = rec.get("date", "")
            if not domain or not date:
                continue
            dedup = rec.get("dedup_hash") or self._dedup_key(rec)
            if self._has_dedup(dedup):
                continue
            # 相似度去重：同 domain 内容相似度 ≥ 0.99 视为重复（content 空则比标题）
            if self._has_similar_content(domain, rec):
                continue
            doc = dict(rec)
            doc["id"] = self._id(domain, date, self._next_seq(domain, date))
            doc["dedup_hash"] = dedup
            doc["crawled_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._append(self._slice_path(domain, date), doc)
            added += 1
        return added

    @staticmethod
    def _sha(url: str, title: str) -> str:
        return hashlib.sha256(f"{url}|{title}".encode("utf-8")).hexdigest()

    @staticmethod
    def _dedup_key(rec: dict) -> str:
        """内容优先的判重键：content 非空且足够长用内容；否则退回 url+title。

        content 过短（<20 字符，如仅"发布时间/浏览次数"元数据）视为无正文，避免短内容误判。
        """
        content = (rec.get("content") or "").strip()
        domain = rec.get("domain", "")
        if len(content) >= 20:
            return hashlib.sha256(f"{domain}|{content}".encode("utf-8")).hexdigest()
        return hashlib.sha256(f"{domain}|{rec.get('url','')}|{rec.get('title','')}".encode("utf-8")).hexdigest()

    @staticmethod
    def _content_similarity(a: str, b: str) -> float:
        """内容相似度：difflib SequenceMatcher ratio（0~1）。"""
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        try:
            from difflib import SequenceMatcher
            return SequenceMatcher(None, a, b).ratio()
        except Exception:
            return 0.0

    def _has_similar_content(self, domain: str, rec: dict, threshold: float = 0.99) -> bool:
        """同 domain 内容相似度 ≥ threshold 视为重复；content 过短（<20）则比标题。"""
        new_content = (rec.get("content") or "").strip()
        new_title = rec.get("title", "")
        use_content = len(new_content) >= 20
        for p in self._docs.glob(f"{domain}.*.jsonl"):
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                doc = json.loads(line)
                if use_content:
                    if self._content_similarity(doc.get("content", ""), new_content) >= threshold:
                        return True
                else:
                    if self._content_similarity(doc.get("title", ""), new_title) >= threshold:
                        return True
        return False

    @staticmethod
    def _sha(url: str, title: str) -> str:
        return hashlib.sha256(f"{url}|{title}".encode("utf-8")).hexdigest()

    def _has_dedup(self, dedup: str) -> bool:
        for p in self._docs.glob("*.jsonl"):
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                if json.loads(line).get("dedup_hash") == dedup:
                    return True
        return False

    def _next_seq(self, domain: str, date: str) -> int:
        p = self._slice_path(domain, date)
        if not p.exists():
            return 1
        seq = 0
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                seq += 1
        return seq + 1

    def _append(self, path: Path, doc: dict):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    # ---- 建索引 ----
    def _load_all(self) -> list[dict]:
        docs = []
        for p in self._docs.glob("*.jsonl"):
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    docs.append(json.loads(line))
        return docs

    def build_index(self):
        all_docs = self._load_all()
        cutoff = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 365 * 86400))
        current_docs = [
            d for d in all_docs
            if d.get("valid", True)
            and d.get("date", "") >= cutoff
            and self._is_valid(d)
        ]
        self._write_index(self._current, current_docs)
        self._write_index(self._archive, all_docs)

    @staticmethod
    def _is_valid(doc: dict) -> bool:
        """有效时间判定：valid_until > 今天；否则 valid_from + effective_days > 今天。无有效时间信息则默认有效。"""
        today = time.strftime("%Y-%m-%d", time.gmtime())
        valid_until = doc.get("valid_until") or ""
        if valid_until:
            return valid_until > today
        valid_from = doc.get("valid_from") or doc.get("date") or ""
        days = doc.get("effective_days")
        if valid_from and days:
            until = (_date.fromisoformat(valid_from) + timedelta(days=int(days))).isoformat()
            return until > today
        return True

    def _write_index(self, index_dir: Path, docs: list[dict]):
        terms: dict[str, dict[str, int]] = {}
        for doc in docs:
            text = " ".join([doc.get("title", ""), doc.get("content", "")])
            for term in set(self._tokenize(text)):
                postings = terms.setdefault(term, {})
                postings[doc["id"]] = postings.get(doc["id"], 0) + 1
        (index_dir / "index.json").write_text(
            json.dumps({"terms": terms, "docs": docs}, ensure_ascii=False, indent=2)
        )

    # ---- 检索（BM25 简化：tf × idf）----
    def search(self, query: str, top_k: int = 5, date_from: str = None,
               date_to: str = None, domain: str = None, scope: str = "current") -> list[dict]:
        index_dir = self._current if scope == "current" else self._archive
        data = self._load_index(index_dir)
        if not data:
            return []
        terms, docs = data["terms"], data["docs"]
        doc_id_to_doc = {d["id"]: d for d in docs}
        n = len(docs)
        if n == 0:
            return []
        query_terms = self._tokenize(query)
        if not query_terms:
            return []
        scores: dict[str, float] = {}
        for term in set(query_terms):
            postings = terms.get(term)
            if not postings:
                continue
            df = len(postings)
            idf = math.log(n / df)
            for doc_id, tf in postings.items():
                scores[doc_id] = scores.get(doc_id, 0.0) + tf * idf
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        result = []
        for doc_id, score in ranked:
            doc = doc_id_to_doc[doc_id]
            d = doc.get("date", "")
            dom = doc.get("domain", "")
            if domain and dom != domain:
                continue
            if date_from and d < date_from:
                continue
            if date_to and d > date_to:
                continue
            result.append({
                "title": doc.get("title", ""),
                "url": doc.get("url", ""),
                "date": d,
                "content": doc.get("content", ""),
                "domain": dom,
                "valid_from": doc.get("valid_from"),
                "valid_until": doc.get("valid_until"),
                "effective_days": doc.get("effective_days"),
                "score": round(score, 4),
                "snippet": self._make_snippet(doc.get("content", ""), query),
            })
        return result

    def list_by_domain(self, domain: str, limit: int = 50) -> list[dict]:
        """列出某 domain 的**有效期内**文档（不依赖关键词），按日期降序，每条含有效期字段。"""
        docs = []
        for p in self._docs.glob(f"{domain}.*.jsonl"):
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    doc = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if doc.get("domain") != domain:
                    continue
                if not self._is_valid(doc):
                    continue  # 只列有效期内
                docs.append({
                    "title": doc.get("title", ""),
                    "url": doc.get("url", ""),
                    "date": doc.get("date", ""),
                    "content": doc.get("content", ""),
                    "domain": doc.get("domain", ""),
                    "valid_from": doc.get("valid_from"),
                    "valid_until": doc.get("valid_until"),
                    "effective_days": doc.get("effective_days"),
                })
        docs.sort(key=lambda d: d.get("date", ""), reverse=True)
        return docs[:limit]

    def _make_snippet(self, content: str, query: str, window: int = 60) -> str:
        """返回 query 首个命中词附近的片段（前后 window 字）。内容短或未命中则返回截断。"""
        content = (content or "").strip()
        if not content:
            return ""
        if len(content) <= window * 2:
            return content
        for term in self._tokenize(query):
            idx = content.find(term)
            if idx >= 0:
                start = max(0, idx - window)
                end = min(len(content), idx + len(term) + window)
                return content[start:end]
        return content[: window * 2]

    def pending_validity(self) -> list[dict]:
        """返回缺有效时间字段的文档。"""
        out = []
        for p in self._docs.glob("*.jsonl"):
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                doc = json.loads(line)
                if not doc.get("valid_until") and not doc.get("effective_days"):
                    out.append(doc)
        return out

    def apply_validity(self, doc_id: str, valid_from: str = None,
                       valid_until: str = None, effective_days: int = None) -> bool:
        """按 doc_id 找到文档所在分片，重写该行的有效时间字段。"""
        for p in self._docs.glob("*.jsonl"):
            lines = p.read_text(encoding="utf-8").splitlines()
            found = False
            new_lines = []
            for line in lines:
                if not line.strip():
                    new_lines.append(line)
                    continue
                doc = json.loads(line)
                if doc.get("id") == doc_id:
                    if valid_from:
                        doc["valid_from"] = valid_from
                    if valid_until:
                        doc["valid_until"] = valid_until
                    if effective_days:
                        doc["effective_days"] = effective_days
                    found = True
                new_lines.append(json.dumps(doc, ensure_ascii=False))
            if found:
                p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                return True
        return False

    def _load_index(self, index_dir: Path) -> dict | None:
        p = index_dir / "index.json"
        if not p.exists():
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    # ---- 新鲜度 ----
    def _load_meta(self) -> dict:
        if self._meta_path.exists():
            with open(self._meta_path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _write_meta(self, meta: dict):
        self._meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    def is_stale(self) -> bool:
        last = self._load_meta().get("last_refresh", 0)
        return time.time() - last > self._refresh_interval_min * 60

    def refresh(self):
        self.build_index()
        slices = sorted(p.name for p in self._docs.glob("*.jsonl"))
        self._write_meta({
            "last_refresh": time.time(),
            "indexed_slices": slices,
            "refresh_interval_min": self._refresh_interval_min,
        })

    def _doc_count(self) -> int:
        return len(self._load_all())
