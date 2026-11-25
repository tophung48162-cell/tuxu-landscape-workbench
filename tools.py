"""工具系统（s02）：JSON schema 声明 + 分派。每个工具有明确副作用与权限。"""
from __future__ import annotations

import csv
from pathlib import Path

import config
import kb
import memory
import pdfutil
import plans

MAX_CHARS = 12000  # 单次工具结果上限，超出截断


def _ok(text) -> str:
    s = str(text)
    return s if len(s) <= MAX_CHARS else s[:MAX_CHARS] + "\n……（已截断）"


def t_kb_search(lib: str, query: str) -> str:
    rows = kb.search(lib, query)
    if not rows:
        return f"库「{lib}」未检索到相关内容（如实告知用户，不要编造）。"
    return "\n\n".join(f"[{r.get('id')}]\n" + "\n".join(f"{k}: {v}" for k, v in r.items() if k != "id") for r in rows)


def t_doc_parse(path: str) -> str:
    p = Path(path).expanduser()
    if not config.is_safe_read(p):
        return f"错误：路径不在读取白名单内或属于敏感文件（{path}）"
    if not p.exists():
        return f"错误：文件不存在（{path}）"
    ext = p.suffix.lower()
    if ext == ".pdf":
        return _ok(pdfutil.extract_text(p))
    if ext == ".dxf":
        return _ok(_dxf_text(p))
    if ext == ".dwg":
        return "错误：DWG 为私有格式不能直读。请在 CAD 里「另存为 → DXF」后重试（或安装免费的 ODA File Converter 自动转换）。"
    if ext in {".txt", ".md", ".csv"}:
        return _ok(p.read_text(encoding="utf-8", errors="ignore"))
    return f"错误：暂不支持 {ext}（支持 PDF / DXF / TXT / MD / CSV）"


def _dxf_text(p: Path) -> str:
    import ezdxf
    doc = ezdxf.readfile(str(p))
    msp = doc.modelspace()
    lines = [f"# DXF 文字提取：{p.name}（图层: 文字内容）"]
    n = 0
    for e in msp:
        t = e.dxftype()
        if t == "TEXT":
            lines.append(f"[{e.dxf.layer}] {e.dxf.text}")
            n += 1
        elif t == "MTEXT":
            lines.append(f"[{e.dxf.layer}] {e.text}")
            n += 1
        elif t == "DIMENSION":
            txt = e.dxf.text
            if txt and txt != "<>":
                lines.append(f"[{e.dxf.layer}] 标注: {txt}")
                n += 1
    if not n:
        lines.append("（未提取到文字实体；可能是纯图形块，可尝试在 CAD 中炸开块后再存 DXF）")
    return "\n".join(lines)


def t_page_snapshot(pdf_path: str, page_no: int) -> str:
    p = Path(pdf_path).expanduser()
    if not config.is_safe_read(p):
        return f"错误：路径不在读取白名单内（{pdf_path}）"
    out = pdfutil.snapshot(p, int(page_no))
    return f"截图已保存：{out}（告诉用户可用 open 命令查看）"


def t_draft_create(filename: str, content: str) -> str:
    p = (config.OUTPUT / filename).resolve()
    if not config.is_safe_write(p):
        return "错误：只能写入 output/ 目录"
    if p.exists():
        return f"错误：{p.name} 已存在。覆盖前必须经用户确认，请换一个文件名。"
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix == ".csv":
        rows = [r for r in csv.reader(content.splitlines()) if r]
        with p.open("w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerows(rows)
    else:
        p.write_text(content, encoding="utf-8")
    return f"已生成：{p}（提醒用户：初稿，需人工复核后使用）"


def t_library_add(lib: str, entry_json: str) -> str:
    import json
    try:
        entry = json.loads(entry_json)
    except json.JSONDecodeError as e:
        return f"错误：entry_json 不是合法 JSON：{e}"
    eid = kb.add(lib, entry)
    return f"已入库（{lib}）：{eid}"


def t_memory_save(fact: str) -> str:
    return "已记住：" + memory.save(fact)


def t_memory_search(query: str) -> str:
    hits = memory.search(query)
    return "\n".join(hits) if hits else "没有相关记忆。"


def t_plan_create(steps: list) -> str:
    return "计划已建立：\n" + plans.render(plans.create([str(s) for s in steps]))


def t_plan_update(name: str, state: str) -> str:
    if state not in plans.STATES:
        return f"错误：state 只能是 {plans.STATES}"
    return "计划已更新：\n" + plans.render(plans.update(name, state))


def t_plan_read(_: str = "") -> str:
    return plans.render(plans.read())


def t_read_text(path: str) -> str:
    p = Path(path).expanduser()
    if not config.is_safe_read(p):
        return f"错误：路径不在读取白名单内或属于敏感文件（{path}）"
    return _ok(p.read_text(encoding="utf-8", errors="ignore"))


def t_libs(_: str = "") -> str:
    counts = kb.list_libs()
    return "四库条目数：" + "，".join(f"{k} {v} 条" for k, v in counts.items())


SCHEMAS = [
    {"name": "kb_search", "description": "检索知识库（图集条文/大样/材料/模板），返回条目与出处。引用条文必须用此工具核实。",
     "input_schema": {"type": "object", "properties": {
         "lib": {"type": "string", "enum": config.LIBRARIES},
         "query": {"type": "string", "description": "检索词，如「无障碍坡道」"}},
         "required": ["lib", "query"]}},
    {"name": "doc_parse", "description": "解析 PDF/文本文件为文字（只读，路径白名单内）",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "page_snapshot", "description": "把 PDF 指定页渲染成截图存到 output/，供用户查看",
     "input_schema": {"type": "object", "properties": {
         "pdf_path": {"type": "string"}, "page_no": {"type": "integer"}}, "required": ["pdf_path", "page_no"]}},
    {"name": "draft_create", "description": "生成交付文档到 output/（只写新文件；已存在则拒绝）",
     "input_schema": {"type": "object", "properties": {
         "filename": {"type": "string", "description": "如 材料表初稿.md 或 .csv"},
         "content": {"type": "string"}}, "required": ["filename", "content"]}},
    {"name": "library_add", "description": "把条目写入指定库（JSON 字符串，含出处字段）",
     "input_schema": {"type": "object", "properties": {
         "lib": {"type": "string", "enum": config.LIBRARIES},
         "entry_json": {"type": "string"}}, "required": ["lib", "entry_json"]}},
    {"name": "memory_save", "description": "记住一条事实（公司标准/材料供应商/偏好/项目上下文）",
     "input_schema": {"type": "object", "properties": {"fact": {"type": "string"}}, "required": ["fact"]}},
    {"name": "memory_search", "description": "检索记忆",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "plan_create", "description": "建立任务计划（多步骤任务先列计划再执行）",
     "input_schema": {"type": "object", "properties": {
         "steps": {"type": "array", "items": {"type": "string"}}}, "required": ["steps"]}},
    {"name": "plan_update", "description": "更新计划步骤状态 pending/in_progress/done",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string"}, "state": {"type": "string"}}, "required": ["name", "state"]}},
    {"name": "plan_read", "description": "查看当前计划",
     "input_schema": {"type": "object", "properties": {"_": {"type": "string"}}, "required": []}},
    {"name": "read_text", "description": "读取白名单内文本文件",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "libs", "description": "查看四库条目数",
     "input_schema": {"type": "object", "properties": {"_": {"type": "string"}}, "required": []}},
]

HANDLERS = {
    "kb_search": lambda a: t_kb_search(a["lib"], a["query"]),
    "doc_parse": lambda a: t_doc_parse(a["path"]),
    "page_snapshot": lambda a: t_page_snapshot(a["pdf_path"], a["page_no"]),
    "draft_create": lambda a: t_draft_create(a["filename"], a["content"]),
    "library_add": lambda a: t_library_add(a["lib"], a["entry_json"]),
    "memory_save": lambda a: t_memory_save(a["fact"]),
    "memory_search": lambda a: t_memory_search(a["query"]),
    "plan_create": lambda a: t_plan_create(a["steps"]),
    "plan_update": lambda a: t_plan_update(a["name"], a["state"]),
    "plan_read": lambda a: t_plan_read(),
    "read_text": lambda a: t_read_text(a["path"]),
    "libs": lambda a: t_libs(),
}


def dispatch(name: str, args: dict) -> str:
    h = HANDLERS.get(name)
    if not h:
        return f"错误：未知工具 {name}"
    try:
        return h(args)
    except Exception as e:  # 错误统一回传格式，让模型可自纠
        return f"工具执行出错：{type(e).__name__}: {e}"
