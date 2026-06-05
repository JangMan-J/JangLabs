#!/usr/bin/env bash
# Post-create provisioning for the JangLabs dev container.
# Runs once, the first time the container is created. cwd is the workspace root.
set -euo pipefail

echo ">> JangLabs: post-create provisioning"

# uv — fast Python venv/package manager (mirrors the host toolchain).
python -m pip install --user --upgrade uv

export PATH="$HOME/.local/bin:$PATH"

# ruff — lint + format for the labs that use Python (e.g. claude/, proton/).
uv tool install ruff

# shellcheck — for the claude/ shell hooks.
if ! command -v shellcheck >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends shellcheck
fi

echo ">> done."
echo ">> Per-lab Python deps (where a requirements.txt exists), e.g.:"
echo ">>   cd <lab> && uv venv && uv pip install -r requirements.txt"
