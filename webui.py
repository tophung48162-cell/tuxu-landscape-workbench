"""网页界面入口（V2 起，与 CLI 并存；V3 功能化）：FastAPI + 单页前端。

- 对话：POST /api/chat（涉密内容先返回 need_confirm，确认后带 confirmed=true 重发）
- 知识库：GET /api/kb 检索/浏览；POST /api/kb/add 录入
- 模板：GET /api/templates 列表+参数；POST /api/render 本地填充出稿（不调模型）
- 文件：PDF 上传解析、output/ 文件展示
"""
from __future__ import annotations

import re
import threading
from pathlib import Path

import markdown as md_lib
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

import config
import kb
import tools
import tools_cad
from harness import Harness

config.load_env()
config.ensure_dirs()
UPLOADS = config.WORKSPACE / "uploads"
UPLOADS.mkdir(exist_ok=True)

app = FastAPI(title="景观施工图工作台")
_lock = threading.Lock()
_harness = Harness()

WEB = Path(__file__).parent / "web"
FILE_REF = re.compile(r"(output[/\\][\w\-./\u4e00-\u9fff()]+\.(?:png|jpg|jpeg|md|csv|xlsx))", re.I)
PARAM_REF = re.compile(r"\{\{([\w\u4e00-\u9fff、/（）()]+)\}\}")


class ChatReq(BaseModel):
    message: str
    confirmed: bool = False


class KbAddReq(BaseModel):
    lib: str
    entry: dict


class RenderReq(BaseModel):
    template: str
    params: dict


def render(text: str) -> str:
    def repl(m: re.Match) -> str:
        p = Path(m.group(1)).name
        if m.group(1).lower().endswith((".png", ".jpg", ".jpeg")):
            return f'<img src="/api/file/{p}" style="max-width:100%;border-radius:8px;margin:6px 0">'
        return f'<a href="/api/file/{p}" target="_blank">📄 {p}</a>'
    text = FILE_REF.sub(repl, text)
    return md_lib.markdown(text, extensions=["tables", "fenced_code"])


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return HTMLResponse(
        content=(WEB / "index.html").read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/chat")
def chat(req: ChatReq) -> dict:
    if any(m in req.message for m in config.SENSITIVE_MARKERS) and not req.confirmed:
        return {"need_confirm": True}
    with _lock:
        reply = _harness.chat(req.message)
    return {"need_confirm": False, "reply_html": render(reply), "raw": reply}


@app.post("/api/new")
def new_chat() -> dict:
    global _harness
    with _lock:
        _harness = Harness()
    return {"ok": True}


@app.get("/api/kb")
def kb_query(lib: str, q: str = "") -> dict:
    if lib not in config.LIBRARIES:
        raise HTTPException(400, "未知库名")
    rows = kb.search(lib, q) if q.strip() else kb.all(lib)
    return {"entries": rows}


@app.post("/api/kb/add")
def kb_add(req: KbAddReq) -> dict:
    if req.lib not in config.LIBRARIES:
        raise HTTPException(400, "未知库名")
    eid = kb.add(req.lib, {k: v for k, v in req.entry.items() if str(v).strip()})
    return {"id": eid}


@app.get("/api/templates")
def templates() -> dict:
    tdir = config.KNOWLEDGE / "说明模板库"
    out = []
    for f in sorted(tdir.glob("*.md")):
        if f.name.startswith("README"):
            continue
        params = sorted(set(PARAM_REF.findall(f.read_text(encoding="utf-8"))))
        out.append({"name": f.name, "params": params})
    return {"templates": out}


@app.post("/api/render")
def render_doc(req: RenderReq) -> dict:
    tdir = (config.KNOWLEDGE / "说明模板库").resolve()
    p = (tdir / Path(req.template).name).resolve()
    if not p.is_file() or not p.is_relative_to(tdir) or p.suffix != ".md":
        raise HTTPException(404, "模板不存在")
    text = p.read_text(encoding="utf-8")
    for k, v in req.params.items():
        text = text.replace("{{" + k + "}}", str(v).strip() or f"{{{{{k}}}}}（待填）")
    return {"content": text}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    ext = Path(file.filename).suffix.lower()
    if ext not in (".pdf", ".dxf", ".dwg"):
        raise HTTPException(400, "支持 PDF / DXF / DWG")
    dest = UPLOADS / Path(file.filename).name
    dest.write_bytes(await file.read())
    if ext == ".dwg":
        if not tools_cad.available():
            raise HTTPException(400, "DWG 直读未启用，请在 CAD 里「另存为 → DXF」后重试")
        info = tools_cad.cad_read(str(dest))
        if not info["ok"]:
            raise HTTPException(400, f"DWG 解析失败：{info['error']}")
        preview = tools_cad.cad_render_full(str(dest))
        return {"path": str(dest), "kind": "dwg", "version": info["version"],
                "sheets": info["sheets"], "chars": info["chars"],
                "text_head": info["text_block"][:4000], "text": info["text_block"],
                "preview": f"/api/file/{preview['image']}" if preview["ok"] else None}
    text = tools.t_doc_parse(str(dest))
    if text.startswith("错误"):
        raise HTTPException(400, text)
    return {"path": str(dest), "kind": ext.lstrip("."), "text_head": text[:4000], "chars": len(text)}


@app.get("/logo.png")
def logo():
    p = WEB / "logo.png"
    if not p.is_file():
        raise HTTPException(404, "logo 未放置")
    return FileResponse(p)


@app.get("/api/file/{name}")
def get_file(name: str):
    p = (config.OUTPUT / name).resolve()
    if not p.is_file() or not config.is_safe_write(p):
        raise HTTPException(404, "文件不存在")
    return FileResponse(p)


@app.get("/api/state")
def state() -> dict:
    import plans as plans_mod
    libs = kb.list_libs()
    tdir = config.KNOWLEDGE / "说明模板库"
    libs["说明模板库"] = len([f for f in tdir.glob("*.md") if not f.name.startswith("README")])
    return {"libs": libs, "plan": plans_mod.render(plans_mod.read())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8620, log_level="warning")
