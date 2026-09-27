#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

if ! command -v python3.12 >/dev/null 2>&1; then
  echo "Python 3.12 is required. Install python3.12 and python3.12-venv, then rerun." >&2
  exit 1
fi

python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-v1.txt

if [[ ! -e .env ]]; then
  cp .env.example .env
  chmod 600 .env
  echo "Created .env; set BOT_TOKEN before starting."
fi
if [[ ! -e users.json ]]; then
  cp users.example.json users.json
  chmod 600 users.json
  echo "Created users.json; set chat ID and broker tokens before starting."
fi

echo "Setup complete. Run: .venv/bin/python -m unittest discover -q"
echo "Then start from this directory: .venv/bin/python app/run.py"
