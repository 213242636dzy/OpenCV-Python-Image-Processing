# 测试 1：交互式图像分割

这是依据课程第 5 讲和实训评分要求实现的桌面软件。程序使用 OpenCV GrabCut，在本地 CPU 上完成矩形初始化、前景/背景人工修正、多轮迭代、实验计时、交互计数和结果保存。

## 已实现功能

- 读取本地图像和规定测试图；兼容中文路径以及“扩展名与实际编码不一致”的图像。
- 选择工具：直线、矩形、正方形、圆、椭圆、五边形、六边形、任意多边形、涂抹。
- 四种标记：确定前景、确定背景、可能前景、可能背景。
- 第一次矩形选择使用 `GC_INIT_WITH_RECT`，后续标记使用 `GC_INIT_WITH_MASK`。
- 每次完成一个形状或一次涂抹，只调用一次 GrabCut，并将交互次数加 1。
- 显示从读取图片开始的总操作时间、真实算法调用次数和最近一次算法耗时。
- 显示原图与分割轮廓混合图、RGB 前景图和二值掩码。
- 撤销和重新开始；撤销不会抹去已经真实发生的算法调用次数。
- 一次保存界面截图、二值 mask、RGB 前景、轮廓叠加图和 JSON 实验记录。
- 启动时关闭 OpenCL，不使用 CUDA、GPU、云端模型或网络接口。
- OpenCV 使用 `opencv-python-headless` wheel；窗口完全由 PySide6 提供，避免两套 GUI 运行库冲突。
- 随软件加载精简的 Noto Sans CJK SC 界面字体子集，避免英文版 Windows 缺少中文字体时显示方框。

## 安装与运行

推荐使用 **64 位 Python 3.12**。程序依赖声明也支持 PySide6 当前支持的 Python 3.10～3.14，
但课程验收建议统一使用 3.12，减少不同电脑上的版本差异。

本项目明确支持的桌面目标为：

- Windows 10 1809 或更高版本、Windows 11（x86-64）；
- macOS 13 或更高版本（Intel x86-64、Apple Silicon arm64）。

### Windows 一键安装

双击 `setup_windows.bat`。脚本会创建 `.venv`、安装依赖并启动软件。安装依赖需要网络一次；安装完成后，软件运行不需要联网。

以后直接双击 `run_windows.bat`。

Windows 请优先安装 [python.org](https://www.python.org/downloads/windows/) 提供的 64 位 Python，
不要使用 Microsoft Store 版本。

### macOS 一键安装

首次运行双击 `setup_macos.command`；以后双击 `run_macos.command`。
若 macOS 首次下载后没有执行权限，在项目目录执行一次：

```bash
chmod +x setup_macos.command run_macos.command
./setup_macos.command
```

Apple Silicon（M 系列）和 Intel Mac 都由 pip 自动选择对应的 PySide6、OpenCV 和 NumPy wheel。

### 命令行安装

```bash
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

Linux/macOS：

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## 最短操作流程

1. 点击“打开规定测试图”，读取 `LENA.jpg`、`baymax.jpeg` 或 `cat.jpg`。
2. 使用矩形工具紧贴目标拖出初始框；松开后自动完成第 1 次分割。
3. 选择“确定前景”或“确定背景”，使用画笔或形状修正错误区域。
4. 每次松开鼠标都会自动完成一次 GrabCut 迭代并更新右侧结果。
5. 在右上方切换“轮廓叠加”“前景 RGB”“二值掩码”检查结果。
6. 点击“结束并保存全部”，选择保存目录。

任意多边形采用逐点单击；双击、右键或 Enter 完成，Esc 取消。圆和椭圆从中心向外拖动。

## 保存结果

以 `cat.jpg` 为例，程序会创建：

```text
cat/
├── cat_ui.png              # 带时间和交互次数的完整界面截图
├── cat_mask.png            # 0/255 单通道分割掩码
├── cat_foreground.png      # 黑色背景的三通道前景图
├── cat_overlay.png         # 原图与绿色分割轮廓的混合图
└── cat_experiment.json     # 尺寸、时间、次数、OpenCV版本和CPU记录
```

## 交互计数口径

- 初始矩形完成并成功调用 GrabCut：计 1 次。
- 一条直线、一个完整图形或一次完整涂抹结束并成功调用 GrabCut：计 1 次。
- 鼠标移动、切换工具、切换视图、撤销和保存：不计数。
- 调用失败会自动恢复上一状态，不计数。
- “重新开始”会将时间和次数清零；“撤销”只恢复图像状态，不改写历史调用次数。

## 自动检查

安装测试依赖并执行完整检查：

```bash
python -m pip install -r requirements-dev.txt
python scripts/verify_project.py
python -m unittest discover -s tests -v
```

测试覆盖项目结构、语法、九种工具、真实 GrabCut、中文路径、结果导出、三张规定图片和 Qt 窗口启动。
Windows/macOS 自动测试矩阵见 `.github/workflows/cross-platform-tests.yml`。
原生 CI 还会执行 `scripts/ci_smoke_capture.py`，生成窗口截图与环境 JSON 作为可下载证据。

Linux 构建容器若缺少 Qt 系统库，应先安装发行版提供的 `libegl1`；Windows 和 macOS wheel 不需要这一步。

字体子集基于 Noto Sans CJK SC，依据 SIL Open Font License 1.1 分发；许可文本位于
`assets/fonts/OFL-1.1.txt`。

完整人工验收步骤见 `EXPERIMENT_CHECKLIST.md`。
本次构建环境的测试记录见 `TEST_REPORT.md`。

## 无需 Python 的便携发行包

GitHub Actions 会在原生 Windows 和 macOS 运行器上使用 PyInstaller 构建成品，并在上传前实际启动一次：

- Windows：`InteractiveGrabCut-Windows-x86_64.zip`，解压后双击 `InteractiveGrabCut.exe`；
- macOS：`InteractiveGrabCut-macOS-<架构>.zip`，解压后打开 `InteractiveGrabCut.app`。

发行包已经包含 OpenCV、PySide6、中文界面字体和三张规定测试图，不需要另装 Python，运行时也不需要联网。
macOS 构建未使用 Apple 开发者证书签名；首次打开若被 Gatekeeper 阻止，请右键应用选择“打开”。

本地构建命令：

```bash
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean InteractiveGrabCut.spec
python scripts/verify_packaged_app.py
```
