#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")" && pwd)"
cd "$project_dir"

if [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python main.py
fi

echo "尚未完成依赖安装，请先双击 setup_macos.command。"
read -r -p "按 Enter 关闭窗口..." _
exit 1
