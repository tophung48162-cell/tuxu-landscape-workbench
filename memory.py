"""记忆（s09）：MEMORY.md 追加 + 检索 + 注入提示词的摘要。"""
from __future__ import annotations

import time

import config

HEAD = "# 记忆 —— 景观施工图工作台\n\n（工作台自动维护：公司制图标准、常用材料与供应商、个人偏好、项目上下文。）\n"


def _ensure() -> None:
    if not config.MEMORY_FILE.exists():
        config.MEMORY_FILE.write_text(HEAD, encoding="utf-8")


def save(fact: str) -> str:
    _ensure()
    line = f"- {time.strftime('%Y-%m-%d')} {fact.strip()}"
    with config.MEMORY_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return line


def search(query: str, top: int = 5) -> list[str]:
    _ensure()
    hits = []
    for line in config.MEMORY_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("- ") and all(q in line for q in query.split()):
            hits.append(line)
    return hits[:top]


def summary(max_chars: int = 800) -> str:
    _ensure()
    text = config.MEMORY_FILE.read_text(encoding="utf-8")
    lines = [l for l in text.splitlines() if l.startswith("- ")]
    if not lines:
        return "（暂无记忆）"
    joined = "\n".join(lines)
    return joined if len(joined) <= max_chars else joined[:max_chars] + "……"
