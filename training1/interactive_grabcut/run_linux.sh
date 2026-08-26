#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")" && pwd)"
cd "$project_dir"
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python main.py
else
  python3 main.py
fi
