#!/bin/bash
# 双击启动「景观施工图工作台 · 网页界面」
cd "$(dirname "$0")" || exit 1
echo "正在启动网页界面… 浏览器将自动打开 http://127.0.0.1:8620"
( sleep 2 && open "http://127.0.0.1:8620" ) &
exec .venv/bin/python webui.py
