"""任务规划（s05）：plan.json 持久化，中断可续。"""
from __future__ import annotations

import json

import config

STATES = ("pending", "in_progress", "done")


def create(steps: list[str]) -> dict:
    plan = {"steps": [{"name": s, "state": "pending"} for s in steps]}
    _write(plan)
    return plan


def update(name: str, state: str) -> dict:
    plan = read()
    for s in plan["steps"]:
        if s["name"] == name:
            s["state"] = state
    _write(plan)
    return plan


def read() -> dict:
    if not config.PLAN_FILE.exists():
        return {"steps": []}
    return json.loads(config.PLAN_FILE.read_text(encoding="utf-8"))


def clear() -> None:
    _write({"steps": []})


def _write(plan: dict) -> None:
    config.PLAN_FILE.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")


def render(plan: dict) -> str:
    if not plan["steps"]:
        return "（无计划）"
    icon = {"pending": "⬜", "in_progress": "🔵", "done": "✅"}
    return "\n".join(f"{icon.get(s['state'], '⬜')} {s['name']}" for s in plan["steps"])
