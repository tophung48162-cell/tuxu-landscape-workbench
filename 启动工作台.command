#!/bin/bash
# 双击启动「景观施工图工作台」
cd "$(dirname "$0")" || exit 1
if [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python main.py
elif command -v uv >/dev/null 2>&1; then
  exec uv run --python 3.12 python main.py
else
  echo "没有找到 .venv 或 uv，请先运行: uv venv --python 3.12 .venv && uv pip install -r requirements.txt"
  read -r -p "按回车退出..."
fi
