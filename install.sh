#!/usr/bin/env bash
set -euo pipefail

REPO_ZIP_URL="https://github.com/superagenta110y/hood-link/archive/refs/heads/main.zip"
INSTALL_DIR="${HOME}/.hoodlink"
WORK_DIR="${INSTALL_DIR}/hood-link-main"

mkdir -p "$INSTALL_DIR"
TMP_ZIP="$(mktemp -t hoodlink.XXXXXX).zip"

echo "Downloading Hood-link..."
curl -fsSL "$REPO_ZIP_URL" -o "$TMP_ZIP"

if [ -d "$WORK_DIR" ]; then
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti:7878 | xargs kill 2>/dev/null || true
  elif command -v fuser >/dev/null 2>&1; then
    fuser -k 7878/tcp 2>/dev/null || true
  fi
fi
rm -rf "$WORK_DIR"
unzip -q "$TMP_ZIP" -d "$INSTALL_DIR"
rm -f "$TMP_ZIP"

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

cd "$WORK_DIR/server"
uv sync
nohup uv run uvicorn hoodlink.main:app --host 127.0.0.1 --port 7878 >/tmp/hoodlink.log 2>&1 &

echo "Hood-link started. Open: http://127.0.0.1:7878"
