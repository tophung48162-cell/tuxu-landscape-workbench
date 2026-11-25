"""模型层：Anthropic 兼容端点（默认 DeepSeek），重试 + 用量留痕。"""
from __future__ import annotations

import json
import time

from anthropic import Anthropic, APIError

import config


class LLM:
    def __init__(self) -> None:
        config.load_env()
        self.client = Anthropic()  # 读 ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL
        self.model = __import__("os").environ.get("MODEL_ID", "deepseek-v4-pro")

    def call(self, messages: list, tools: list | None = None, max_tokens: int = 4096) -> object:
        last = None
        for attempt in range(3):
            try:
                kwargs = dict(model=self.model, max_tokens=max_tokens, messages=messages)
                if tools:
                    kwargs["tools"] = tools
                resp = self.client.messages.create(**kwargs)
                self._log(resp)
                return resp
            except APIError as e:
                last = e
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"模型调用失败（重试3次）: {last}")

    def _log(self, resp: object) -> None:
        rec = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": self.model,
            "stop_reason": resp.stop_reason,
            "usage": dict(resp.usage),
        }
        with (config.LOGS / "usage.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
