"""CAD 读取适配层——全项目唯一处理 DWG 的模块。

路线（2026-11-23 定案，详见 evals/go-cad验证报告.md）：
  文字提取：ODA File Converter（vendor/oda，免安装便携）DWG→DXF
            → ezdxf 递归遍历（模型空间+图纸空间+块/嵌套块/动态块）
            → \\M+ bigfont 逃逸序列按 GB2312 解码
  预览渲染：go-cad dwg2png（vendor/gocad，几何渲染质量高）

中间格式（上层只依赖本模块返回的 dict）：
cad_read(path) -> {
  "ok": bool, "error": str | None,
  "version": str,                 # DWG 版本号，如 AC1018
  "texts":  [{"text","layer"}],   # 全图文字清单（已解码中文）
  "sheets": [{"index","name"}],   # 图纸空间分幅（无布局时为"整图"兜底）
  "chars": int, "text_block": str,  # 拼接好的纯文本，供图纸校对直接消费
}
cad_render_full(path) -> {"ok","error","image": 文件名 | None}
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import config

_SK = Path(__file__).resolve().parent
_ODA = _SK / "vendor" / "oda" / "ODAFileConverter.app" / "Contents" / "MacOS" / "ODAFileConverter"
_GOCAD = _SK / "vendor" / "gocad" / "dwg2png"
_TIMEOUT_READ = 120
_TIMEOUT_RENDER = 120
_TEXT_BLOCK_MAX = 100_000
_MPLUS = re.compile(r"\\M\+([0-9A-Fa-f]{5})")
_FMT_CLEAN = re.compile(r"\\A\d;|\\P|\\~|%%[cCdDpP]")


def _decode_mplus(m: re.Match) -> str:
    """AutoCAD bigfont 逃逸 \\M+0XXXX 按 GB2312 解码（验证见 evals 报告）。"""
    code = int(m.group(1), 16)
    if 0xA1A1 <= code <= 0xF7FE:
        try:
            return bytes([code >> 8, code & 0xFF]).decode("gb2312")
        except UnicodeDecodeError:
            return m.group(0)
    return m.group(0)


def clean_text(s: str) -> str:
    t = _MPLUS.sub(_decode_mplus, s or "")
    return _FMT_CLEAN.sub(lambda m: " " if m.group(0) in ("\\P",) else m.group(0)[-1], t).strip()


def available() -> bool:
    return getattr(config, "CAD_BACKEND", "none") == "gocad" and _ODA.is_file()


def _run(args: list[str], timeout: int) -> tuple[bool, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"处理超时（>{timeout}秒），图纸可能过大"
    except Exception as e:
        return False, f"CAD 工具执行失败：{type(e).__name__}: {e}"
    if p.returncode != 0:
        tail = (p.stderr or "").strip()[-300:] or (p.stdout or "").strip()[-300:]
        return False, f"CAD 工具返回错误：{tail}"
    return True, p.stdout or ""


def _tmp(name: str) -> Path:
    d = config.LOGS / "cad_tmp" / name
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _dwg_to_dxf(src: Path) -> tuple[Path | None, str | None]:
    """ODA 转换 DWG→DXF，返回 (dxf路径, 错误)。"""
    work = _tmp(src.stem + "-oda")
    in_dir, out_dir = work / "in", work / "out"
    in_dir.mkdir(), out_dir.mkdir()
    (in_dir / src.name).write_bytes(src.read_bytes())
    ok, log = _run([str(_ODA), str(in_dir), str(out_dir), "ACAD2018", "DXF", "0", "0"], _TIMEOUT_READ)
    if not ok:
        return None, log
    dxfs = list(out_dir.glob("*.dxf"))
    if not dxfs:
        return None, f"转换未产出 DXF（{log[-200:]}）"
    return dxfs[0], None


def _extract_texts(dxf: Path) -> tuple[str, list[dict], list[dict]]:
    """ezdxf 递归提取：模型空间+图纸空间，块/嵌套块/动态块，bigfont 解码。"""
    import ezdxf  # 延迟导入，保持模块轻量

    doc = ezdxf.readfile(str(dxf))
    version = doc.acad_release if hasattr(doc, "acad_release") else doc.dxfversion
    texts: list[dict] = []

    def walk(entities, depth: int = 0):
        if depth > 8:
            return
        for e in entities:
            t = e.dxftype()
            if t in ("TEXT", "MTEXT"):
                s = clean_text(e.dxf.text if t == "TEXT" else e.text)
                if s:
                    texts.append({"text": s, "layer": str(getattr(e.dxf, "layer", ""))})
            elif t == "DIMENSION":
                s = clean_text(e.dxf.text)
                if s and s != "<>":
                    texts.append({"text": f"标注: {s}", "layer": str(getattr(e.dxf, "layer", ""))})
            elif t == "INSERT":
                try:
                    walk(e.virtual_entities(), depth + 1)
                except Exception:
                    pass

    try:
        walk(doc.modelspace())
    except Exception:
        pass
    sheets = []
    for i, layout in enumerate(doc.layouts):
        if layout.name.lower().startswith("model"):
            continue
        try:
            walk(layout)
        except Exception:
            pass
        sheets.append({"index": len(sheets) + 1, "name": f"图纸空间 {len(sheets) + 1}"})
    if not sheets:
        sheets = [{"index": 1, "name": "整图"}]
    return version, texts, sheets


def _dwg_version(src: Path) -> str:
    """读原 DWG 魔数（前 6 字节，如 AC1018）。"""
    try:
        magic = src.open("rb").read(6).decode("ascii", errors="ignore").strip()
        return magic if magic.startswith("AC") else ""
    except Exception:
        return ""


def cad_read(path: str) -> dict:
    src = Path(path).expanduser()
    if not src.is_file():
        return {"ok": False, "error": f"文件不存在（{path}）"}
    if src.suffix.lower() in (".dxf", ".dwg") and src.suffix.lower() == ".dxf":
        dxf, err = src, None
    elif not available():
        return {"ok": False, "error": "DWG 直读未启用（CAD_BACKEND=none）"}
    else:
        dxf, err = _dwg_to_dxf(src)
        if err:
            return {"ok": False, "error": err}
    try:
        version, texts, sheets = _extract_texts(dxf)
    except Exception as e:
        return {"ok": False, "error": f"DXF 解析失败：{type(e).__name__}: {e}"}
    version = _dwg_version(src) or version
    block = "\n".join(t["text"] for t in texts)
    if len(block) > _TEXT_BLOCK_MAX:
        block = block[:_TEXT_BLOCK_MAX] + "\n……（已截断）"
    return {"ok": True, "error": None, "version": version, "texts": texts,
            "sheets": sheets, "chars": sum(len(t["text"]) for t in texts),
            "text_block": block}


def _render_dxf(dxf: Path, out_png: Path) -> None:
    """ezdxf+matplotlib 渲染模型空间（go-cad 失败时的兜底）。"""
    import ezdxf
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    doc = ezdxf.readfile(str(dxf))
    fig = plt.figure()
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace(), finalize=True)
    fig.savefig(str(out_png), dpi=150, facecolor="white")
    plt.close(fig)


def cad_render_full(path: str) -> dict:
    """整图预览 PNG → output/。优先 go-cad，失败转 ezdxf 渲染转换后的 DXF。"""
    src = Path(path).expanduser()
    if not src.is_file():
        return {"ok": False, "error": f"文件不存在（{path}）"}
    out = _tmp(src.stem + "-render")
    png = out / "full.png"
    done, log = False, ""
    if _GOCAD.is_file():
        done, log = _run([str(_GOCAD), "-o", str(png), str(src)], _TIMEOUT_RENDER)
        done = done and png.is_file()
    if not done:
        dxf, err = _dwg_to_dxf(src)
        if err:
            return {"ok": False, "error": f"预览渲染失败（go-cad：{log[-120:]}；ODA：{err}）"}
        try:
            _render_dxf(dxf, png)
            done = True
        except Exception as e:
            return {"ok": False, "error": f"预览渲染失败：{type(e).__name__}: {e}"}
    dest = (config.OUTPUT / f"cad-{src.stem}-预览.png").resolve()
    if not config.is_safe_write(dest):
        return {"ok": False, "error": "输出路径越界"}
    shutil.copy2(png, dest)
    return {"ok": True, "error": None, "image": dest.name}
