# 实训 1 软件测试报告

测试日期：2026-08-25  
构建平台：Linux x86-64 无桌面容器  
目标平台：Windows 10 1809+/Windows 11 x86-64；macOS 13+ x86-64/arm64

## 已安装环境

| 组件 | 实测版本 |
|---|---:|
| Python | 3.12.13 |
| OpenCV (`opencv-python-headless`) | 4.14.0 |
| NumPy | 2.5.2 |
| PySide6 | 6.11.2 |
| pytest | 9.1.1 |

OpenCL 已明确关闭，软件未调用 CUDA/GPU 或网络接口。依赖一致性检查结果为
`No broken requirements found`。

## 自动测试结果

最终命令：

```bash
python scripts/verify_project.py
python -m pip check
python -m pytest -q
```

结果：

```text
项目检查通过：17 个必要文件，17 个 Python 文件语法正确。
13 passed, 3 subtests passed in 46.73s
```

覆盖内容：

- GrabCut 初始化、掩码输出、前景 RGB、轮廓叠加；
- 状态快照、撤销与恢复；
- 九种绘图工具的掩码栅格化；
- 坐标夹取、反向矩形、正方形、正多边形等几何逻辑；
- 中文文件夹和中文文件名的图像读写；
- mask、foreground、overlay、JSON 元数据导出；
- `LENA.jpg`、`baymax.jpeg`、`cat.jpg` 全分辨率读取与真实 GrabCut；
- PySide6 主窗口创建、显示、载图、分割、截图、撤销、重置和关闭；
- macOS/Linux shell 脚本语法及项目结构检查。

## 跨平台保障

- 业务代码只使用 Python、NumPy、OpenCV 与 PySide6，不调用 Windows 或 macOS 私有 API。
- 文件路径统一使用 `pathlib.Path`；图像读写支持 Unicode 路径。
- Windows 提供 `setup_windows.bat`、`run_windows.bat`。
- macOS 提供 `setup_macos.command`、`run_macos.command`。
- 自动测试矩阵文件 `.github/workflows/cross-platform-tests.yml` 同时覆盖
  `windows-latest` 与 `macos-latest`、Python 3.12。

## 测试边界

当前构建容器没有物理显示器，且系统 Qt EGL 库不可写入安装。Qt GUI 测试使用软件渲染、
offscreen 平台和仅用于测试的本地 EGL 兼容层完成；窗口生命周期、交互逻辑和截图已实测，
但不能替代在真实 Windows 与 macOS 桌面上对字体、缩放和系统文件对话框的人工验收。
提交前请严格执行 `EXPERIMENT_CHECKLIST.md` 中的双平台复检步骤。
