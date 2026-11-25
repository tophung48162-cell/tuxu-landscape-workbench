#!/bin/bash
# 重新构建 go-cad 二进制（需要 Go 1.24+）
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
TMP=$(mktemp -d)
git clone https://github.com/unitedrhino/go-cad "$TMP/go-cad"
cd "$TMP/go-cad"
git checkout ddd91eea9618cc1a2feec32ab6397239d1f9f315
go build -o "$DIR/dwg2png" ./cmd/dwg2png
go build -o "$DIR/caddocling" ./cmd/caddocling
rm -rf "$TMP"
echo "构建完成"
