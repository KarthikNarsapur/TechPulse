#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "\${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$ROOT_DIR/infrastructure/terraform"
BUILD_DIR="$TF_DIR/dist"
API_BUILD="$BUILD_DIR/api"
WORKER_BUILD="$BUILD_DIR/workers"

rm -rf "$BUILD_DIR"
mkdir -p "$API_BUILD" "$WORKER_BUILD"

python3.12 -m pip install -r "$ROOT_DIR/backend/requirements.txt" -t "$API_BUILD"
cp -R "$ROOT_DIR/backend/app" "$API_BUILD/app"
cp -R "$ROOT_DIR/backend/app" "$WORKER_BUILD/app"

(
  cd "$API_BUILD"
  zip -qr "$BUILD_DIR/api.zip" .
)
(
  cd "$WORKER_BUILD"
  zip -qr "$BUILD_DIR/workers.zip" .
)

echo "Created $BUILD_DIR/api.zip and $BUILD_DIR/workers.zip"
echo "Use a Linux-compatible Python 3.12 build environment for repeatable deployment artifacts."
