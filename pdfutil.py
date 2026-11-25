"""PDF 处理：pypdf 提取文字，pypdfium2 渲染页面截图。"""
from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from pypdf import PdfReader

import config


def extract_text(path: Path) -> str:
    reader = PdfReader(str(path))
    parts = []
    for i, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        parts.append(f"--- 第{i}页 ---\n{text.strip()}")
    return "\n\n".join(parts)


def snapshot(path: Path, page_no: int, name: str | None = None) -> Path:
    doc = pdfium.PdfDocument(str(path))
    page = doc[page_no - 1]
    bitmap = page.render(scale=2).to_pil()
    out = config.OUTPUT / (name or f"{path.stem}-p{page_no}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    bitmap.save(out)
    return out
