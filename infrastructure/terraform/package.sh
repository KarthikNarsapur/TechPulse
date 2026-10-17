#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "\${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$ROOT_DIR/infrastructure/terraform"
BUILD_DIR="$TF_DIR/dist"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/api" "$BUILD_DIR/workers"

python3.12 -m pip install --upgrade pip
python3.12 -m pip install -r "$ROOT_DIR/backend/requirements.txt" -t "$BUILD_DIR/api"
cp -R "$ROOT_DIR/backend/app" "$BUILD_DIR/api/app"
cp -R "$ROOT_DIR/backend/app" "$BUILD_DIR/workers/app"

(
  cd "$BUILD_DIR/api"
  zip -qr "$BUILD_DIR/api.zip" .
)
(
  cd "$BUILD_DIR/workers"
  zip -qr "$BUILD_DIR/workers.zip" .
)

echo "Created:"
echo "  $BUILD_DIR/api.zip"
echo "  $BUILD_DIR/workers.zip"
echo "Note: build dependencies in a Linux-compatible environment matching Lambda's Python 3.12 runtime."
