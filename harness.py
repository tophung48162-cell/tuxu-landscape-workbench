"""集成 Harness（s15）：单一循环 = s01 loop + 工具分派 + s05 计划 + s07 知识 + s09 记忆。"""
from __future__ import annotations

import json

import kb
import memory
import prompts
import tools
from llm import LLM


class Harness:
    def __init__(self) -> None:
        self.llm = LLM()
        self.messages: list = []

    def _system(self) -> str:
        return prompts.TEMPLATE.format(
            memory=memory.summary(),
            libs="、".join(f"{k}（{v}条）" for k, v in kb.list_libs().items()),
        )

    def chat(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})
        for _ in range(20):  # 循环上限，防失控
            resp = self.llm.call(self.messages, tools=tools.SCHEMAS)
            self.messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason == "end_turn":
                return "".join(b.text for b in resp.content if b.type == "text")
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            results = []
            for tu in tool_uses:
                out = tools.dispatch(tu.name, tu.input)
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": out})
            self.messages.append({"role": "user", "content": results})
        return "（达到循环上限，请把问题拆小或重试）"
