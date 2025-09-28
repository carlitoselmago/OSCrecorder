#!/usr/bin/env bash
set -euo pipefail

# Config
ADDON_NAME="OSCrecorder"
BUILD_DIR="build"

# Extract version from blender_manifest.toml (ignore schema_version)
# Anchor to line start to match only 'version = "x.y.z"'
VERSION="$(grep -Po '^\s*version\s*=\s*"\K[^"]+' blender_manifest.toml | head -n1 || true)"

if [[ -z "${VERSION:-}" ]]; then
  echo "❌ Could not find 'version = \"...\"' in blender_manifest.toml"
  exit 1
fi

ZIP_NAME="${ADDON_NAME}-${VERSION}.zip"

echo "📦 Building ${ZIP_NAME} ..."

# Clean build dir
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

# Temp staging area
TMPDIR="$(mktemp -d)"
STAGE="${TMPDIR}/${ADDON_NAME}"
mkdir -p "${STAGE}"

# Prefer rsync to copy everything except dev artifacts; fallback to minimal cp
if command -v rsync >/dev/null 2>&1; then
  rsync -a \
    --exclude ".git" \
    --exclude ".gitignore" \
    --exclude "${BUILD_DIR}" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude "*.pyo" \
    --exclude "*.DS_Store" \
    --exclude "*.zip" \
    --exclude "build.sh" \
    ./ "${STAGE}/"
else
  echo "ℹ️  rsync not found; copying core files only."
  # Add any other files/dirs you need here if you don't use rsync
  cp -f __init__.py "${STAGE}/" 2>/dev/null || true
  cp -f main.py "${STAGE}/" 2>/dev/null || true
  cp -f blender_manifest.toml "${STAGE}/" 2>/dev/null || true
  cp -f README.md "${STAGE}/" 2>/dev/null || true
  cp -f LICENSE "${STAGE}/" 2>/dev/null || true
fi

# Create the zip (must include the top-level folder inside)
(
  cd "${TMPDIR}"
  zip -r "${OLDPWD}/${BUILD_DIR}/${ZIP_NAME}" "${ADDON_NAME}" \
    -x "*.git*" "*__pycache__*" "*.DS_Store*"
)

# Cleanup
rm -rf "${TMPDIR}"

echo "✅ Done: ${BUILD_DIR}/${ZIP_NAME}"
