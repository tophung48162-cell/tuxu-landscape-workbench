# ODA File Converter（DWG→DXF 转换器）

- 来源：https://www.opendesign.com/guestfiles/oda_file_converter （免费，闭源）
- 版本：ODAFileConverter_QT6_macOsX_arm64_15.0dll（2026-11 下载）
- 部署：pkg 经 pkgutil --expand-full 展开后取出 .app，免管理员安装、随工作台走
- 调用：仅 skeleton/tools_cad.py；无界面批量模式
  ODAFileConverter <输入目录> <输出目录> ACAD2018 DXF 0 0
  （注意审计标志传 0：传 1 会产生 $TD_AUDIT_GENERATED_ 修复残留块）
- 已知噪音：天正代理对象警告（ACAD_PROXY_OBJECT ignored）输出在 stderr，调用方忽略
- 移除方式：删本目录即可，工作台自动降级
