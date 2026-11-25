"""知识库（s07 目录先行）：四库 JSONL 条目 + 关键词检索。"""
from __future__ import annotations

import json
import re
from pathlib import Path

import config

_CJK = re.compile(r"[\u4e00-\u9fff]")


def _tokens(text: str) -> list[str]:
    text = text.lower()
    words = re.findall(r"[a-z0-9.\-]+", text)
    chars = _CJK.findall(text)
    return words + chars


def _entries_file(lib: str) -> Path:
    if lib not in config.LIBRARIES:
        raise ValueError(f"未知库名：{lib}。可选：{'、'.join(config.LIBRARIES)}")
    return config.KNOWLEDGE / lib / "entries.jsonl"


def _load(lib: str) -> list[dict]:
    f = _entries_file(lib)
    if not f.exists():
        return []
    rows = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _score(entry: dict, toks: list[str]) -> int:
    hay = " ".join(str(v) for v in entry.values() if isinstance(v, (str, list)))
    return sum(hay.count(t) for t in toks)


def search(lib: str, query: str, top: int = 5) -> list[dict]:
    toks = _tokens(query)
    rows = [r for r in _load(lib) if _score(r, toks) > 0]
    rows.sort(key=lambda r: _score(r, toks), reverse=True)
    return rows[:top]


def get(lib: str, eid: str) -> dict | None:
    for r in _load(lib):
        if r.get("id") == eid:
            return r
    return None


def add(lib: str, entry: dict) -> str:
    f = _entries_file(lib)
    eid = entry.get("id") or f"{lib}-{int(__import__('time').time())}"
    entry["id"] = eid
    with f.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return eid


def list_libs() -> dict[str, int]:
    return {lib: len(_load(lib)) for lib in config.LIBRARIES}


def all(lib: str, limit: int = 100) -> list[dict]:
    """全量列出（新→旧），供界面浏览。"""
    rows = _load(lib)
    return rows[::-1][:limit]
