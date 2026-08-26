"""无需 GUI 依赖的项目完整性和 Python 语法检查。"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "venv",
}
REQUIRED = [
    "main.py",
    "requirements.txt",
    "README.md",
    "TEST_REPORT.md",
    "EXPERIMENT_CHECKLIST.md",
    "app/main_window.py",
    "app/canvas.py",
    "app/grabcut_engine.py",
    "app/exporter.py",
    "scripts/ci_smoke_capture.py",
    "setup_windows.bat",
    "run_windows.bat",
    "setup_macos.command",
    "run_macos.command",
    "test_images/LENA.jpg",
    "test_images/baymax.jpeg",
    "test_images/cat.jpg",
]


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"缺失或为空：{relative}")

    # 只检查项目源码；安装依赖后 .venv 中可能包含扩展模板或生成文件，
    # 它们不是本项目源码，也不一定是可独立解析的 Python 文件。
    python_files = sorted(
        path for path in ROOT.rglob("*.py") if not IGNORED_PARTS.intersection(path.relative_to(ROOT).parts)
    )
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeError) as exc:
            errors.append(f"Python 语法错误：{path.relative_to(ROOT)}：{exc}")

    image_magic = {
        "test_images/LENA.jpg": b"\x89PNG\r\n\x1a\n",  # 仓库原文件扩展名为 jpg，内容实际为 PNG
        "test_images/baymax.jpeg": b"\xff\xd8\xff",
        "test_images/cat.jpg": b"\xff\xd8\xff",
    }
    for relative, magic in image_magic.items():
        path = ROOT / relative
        if path.is_file() and not path.read_bytes().startswith(magic):
            errors.append(f"图像文件头不正确：{relative}")

    if errors:
        print("项目检查失败：")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"项目检查通过：{len(REQUIRED)} 个必要文件，{len(python_files)} 个 Python 文件语法正确。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
