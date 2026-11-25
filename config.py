"""配置与路径：环境变量、白名单、四库目录。"""
from __future__ import annotations

import os
from pathlib import Path

BASE = Path(__file__).resolve().parent          # skeleton/
WORKSPACE = BASE.parent                          # out/景观施工图工作台/
ENGINE_ROOT = BASE.parents[2]                    # agent-workshop/

KNOWLEDGE = WORKSPACE / "knowledge"
OUTPUT = WORKSPACE / "output"
LOGS = WORKSPACE / "logs"
MEMORY_FILE = WORKSPACE / "MEMORY.md"
PLAN_FILE = WORKSPACE / "plan.json"

LIBRARIES = ["图集条文库", "大样库", "材料价表库", "说明模板库"]

# CAD 读取后端：gocad=go-cad 直读 DWG；none=不支持（提示另存 DXF）
CAD_BACKEND = "gocad"

# 读取白名单：用户的工作区 + 常用资料目录
SAFE_READ_ROOTS = [WORKSPACE, Path.home() / "Downloads", Path.home() / "Desktop", Path.home() / "Documents"]

# 涉密关键词（Q7 红线：命中则发送云端前必须确认）
SENSITIVE_MARKERS = ["图纸", "甲方", "项目名称", "工程名称", "业主", "用地红线", "总平面", "施工图"]


def load_env() -> None:
    for cand in (BASE / ".env", ENGINE_ROOT / ".env"):
        if cand.exists():
            for line in cand.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            return


def ensure_dirs() -> None:
    for d in [KNOWLEDGE, OUTPUT, LOGS, *[KNOWLEDGE / lib for lib in LIBRARIES]]:
        d.mkdir(parents=True, exist_ok=True)


def is_safe_read(path: Path) -> bool:
    p = path.resolve()
    if p.name in {".env", ".envrc"} or p.suffix in {".pem", ".key"}:
        return False
    return any(p.is_relative_to(root) for root in SAFE_READ_ROOTS)


def is_safe_write(path: Path) -> bool:
    p = path.resolve()
    return p.is_relative_to(OUTPUT) or p.is_relative_to(KNOWLEDGE)
