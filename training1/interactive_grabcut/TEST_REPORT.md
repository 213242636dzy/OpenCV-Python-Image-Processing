# OpenCV 交互实训套件 v2 测试报告

## v2 本地完整验证（2026-09-02）

本版本在测试 1 GrabCut 软件上新增测试 2“路径文字”和测试 3“平/柱面贴图”，并保留 Windows/macOS 便携打包流程。

本地环境为 Linux 6.18 x86-64 无物理显示器容器，Python 3.12.13、OpenCV 4.14.0、PySide6/Qt 6.11.2、NumPy 2.5.2；Qt 使用 offscreen 软件渲染，OpenCL 关闭且未使用 GPU。

```text
项目检查通过：39 个必要文件，29 个 Python 文件语法正确
19 passed, 8 subtests passed in 21.44s
PyInstaller 6.22.2 构建成功
发行包结构、规定素材、五套字体与 --ci-smoke 启动检查通过
```

新增测试覆盖 4–10 字校验、逐字切线角度、5 个真实中文字体家族、6 种艺术效果、透明文字层、用户位置与缩放、平面/柱面变换、alpha 融合、颜色协调、计时计数、撤销重置、测试 1/2 前景传入测试 3，以及三个页签的显示和截图。

Windows/macOS 原生验证将在 v2 分支提交后由根目录 GitHub Actions 执行；最终原生截图、架构、成品启动结果与 SHA-256 以对应工作流和 v2 Release 为准。

---

## v1 历史记录

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
项目检查通过：21 个必要文件，18 个 Python 文件语法正确。
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
