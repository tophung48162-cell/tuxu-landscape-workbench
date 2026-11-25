"""入口：CLI 对话 + 涉密确认（Q7 红线）+ --once 冒烟模式。"""
from __future__ import annotations

import sys

import config


def need_confirm(text: str) -> bool:
    return any(m in text for m in config.SENSITIVE_MARKERS)


def main() -> None:
    config.load_env()
    config.ensure_dirs()

    if "--once" in sys.argv:  # 冒烟测试：--once "一句话"
        from harness import Harness
        h = Harness()
        print(h.chat(sys.argv[sys.argv.index("--once") + 1]))
        return

    print("景观施工图工作台 · 输入问题开始（exit 退出，new 开新会话）")
    print("提示：粘贴项目图纸内容前，系统会先问你确认（涉密红线）\n")

    from harness import Harness
    h = Harness()
    while True:
        try:
            user = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break
        if not user:
            continue
        if user == "exit":
            break
        if user == "new":
            h = Harness()
            print("（已开新会话，记忆保留）")
            continue
        if need_confirm(user):
            ans = input("⚠️ 内容疑似涉密（含图纸/甲方等关键词），确认发送到云端模型？[y/N] ").strip().lower()
            if ans != "y":
                print("已取消发送。你可以改写掉敏感信息后再问，或先把内容存入本地库。")
                continue
            print("（已确认发送）")
        try:
            print("\n台 > " + h.chat(user) + "\n")
        except Exception as e:
            print(f"\n出错了：{e}\n")


if __name__ == "__main__":
    main()
