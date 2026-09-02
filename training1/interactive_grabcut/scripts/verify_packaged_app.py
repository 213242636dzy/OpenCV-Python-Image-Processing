"""检查 PyInstaller 发行包的结构，并实际启动一次。"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def _configure_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _target() -> tuple[Path, Path]:
    system = platform.system()
    if system == "Windows":
        root = DIST / "InteractiveVisionTraining"
        return root, root / "InteractiveVisionTraining.exe"
    if system == "Darwin":
        root = DIST / "InteractiveVisionTraining.app"
        return root, root / "Contents" / "MacOS" / "InteractiveVisionTraining"
    root = DIST / "InteractiveVisionTraining"
    return root, root / "InteractiveVisionTraining"


def main() -> int:
    _configure_utf8_console()
    package_root, executable = _target()
    errors: list[str] = []
    if not package_root.exists():
        errors.append(f"缺少发行包：{package_root}")
    if not executable.is_file():
        errors.append(f"缺少可执行入口：{executable}")
    packaged_files = {path.name for path in package_root.rglob("*") if path.is_file()}
    for required_name in (
        "NotoSansCJKsc-Regular.otf",
        "NotoSerifSC-VF.ttf",
        "MaShanZheng-Regular.ttf",
        "ZCOOLXiaoWei-Regular.ttf",
        "LongCang-Regular.ttf",
        "LENA.jpg",
        "baymax.jpeg",
        "cat.jpg",
        "rainbow_reference.jpg",
        "planar_foreground.jpg",
        "planar_source_reference.jpg",
        "TEST2_3_CHECKLIST.md",
    ):
        if required_name not in packaged_files:
            errors.append(f"发行包缺少资源：{required_name}")
    if errors:
        print("发行包结构检查失败：")
        for error in errors:
            print(f"- {error}")
        return 1

    environment = os.environ.copy()
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    environment.setdefault("QT_QUICK_BACKEND", "software")
    completed = subprocess.run(
        [str(executable), "--ci-smoke"],
        cwd=package_root,
        env=environment,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        print(f"发行包启动检查失败，退出码：{completed.returncode}")
        return completed.returncode or 1

    total_bytes = sum(path.stat().st_size for path in package_root.rglob("*") if path.is_file())
    print(f"发行包检查通过：{platform.system()}，入口可启动，总大小 {total_bytes / 1024 / 1024:.1f} MiB。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
