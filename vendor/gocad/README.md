# go-cad 二进制（DWG 直读/渲染）

- 来源：https://github.com/unitedrhino/go-cad
- 版本 pin：ddd91eea9618cc1a2feec32ab6397239d1f9f315（2026-10-01）
- 构建：macOS arm64，Go 1.27.4 官方发行版编译
- 文件：
  - `caddocling`：DWG/DXF → manifest.json（图框/图号/图名/文本清单）+ 整图 PNG
  - `dwg2png`：DWG/DXF → PNG/SVG（-sheets 按图框拆图）
- 接入方式：Python subprocess 调用，唯一调用点 skeleton/tools_cad.py
- 移除方式：config.py 中 CAD_BACKEND 置 "none" + 删本目录
- 注意：二进制不入 git，重新构建用 build.sh
