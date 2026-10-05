#!/usr/bin/env bash
# Build Fallow as a portable AppImage.
#
#   appimage/build-appimage.sh
#
# Produces dist/Fallow-0.14.0-x86_64.AppImage - a single self-contained file:
#
#   chmod +x dist/Fallow-0.14.0-x86_64.AppImage
#   ./dist/Fallow-0.14.0-x86_64.AppImage /path/to/document.pdf
#
# Set FALLOW_VERSION to name the image after a different version; the release
# workflow uses the git tag so the file matches the release it belongs to.
#
# Requires: curl, tar, and appimagetool on PATH. No root access, no Flatpak, and
# no system Python: the interpreter comes from python-build-standalone and is
# unpacked straight into the AppDir, so the result does not care which Python,
# Qt, or pip the host has.
#
# Only glibc and the X11/Wayland client libraries remain host dependencies, which
# is the usual floor for a PySide6 application in an AppImage.

set -euo pipefail

APP_ID="org.fallow.PdfReader"
# Overridable so the release workflow can name the image after the git tag
# (FALLOW_VERSION=0.15.0). Local builds keep the pinned value.
VERSION="${FALLOW_VERSION:-0.14.0}"
ARCH="x86_64"
# Pinned standalone CPython. Any 3.10-3.13 works: PySide6, PyMuPDF, and numpy all
# publish abi3 wheels. Change both values together; release tags are listed at
# https://github.com/astral-sh/python-build-standalone/releases
PBS_RELEASE="20260924"
PBS_PYTHON="3.13.15"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT}/build/appimage"
APPDIR="${BUILD_DIR}/Fallow.AppDir"
CACHE_DIR="${BUILD_DIR}/cache"
DIST_DIR="${ROOT}/dist"
IMAGE="${DIST_DIR}/Fallow-${VERSION}-${ARCH}.AppImage"

TARBALL="cpython-${PBS_PYTHON}+${PBS_RELEASE}-${ARCH}-unknown-linux-gnu-install_only_stripped.tar.gz"
TARBALL_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_RELEASE}/${TARBALL}"

echo "==> 1/5  Creating the AppDir skeleton"
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/share/fallow" "${CACHE_DIR}" "${DIST_DIR}"

echo "==> 2/5  Unpacking CPython ${PBS_PYTHON} into the AppDir"
if [[ ! -f "${CACHE_DIR}/${TARBALL}" ]]; then
    curl --fail --location --output "${CACHE_DIR}/${TARBALL}" "${TARBALL_URL}"
fi
# The tarball holds a single "python/" directory, so the interpreter lands at
# usr/python/bin/python3 - a path AppRun can find relative to the mount point.
tar -xzf "${CACHE_DIR}/${TARBALL}" -C "${APPDIR}/usr"
PYTHON="${APPDIR}/usr/python/bin/python3"
"${PYTHON}" --version

echo "==> 3/5  Installing the runtime dependencies (this is the slow part)"
"${PYTHON}" -m pip install \
    --no-cache-dir \
    --disable-pip-version-check \
    --quiet \
    -r "${ROOT}/appimage/requirements-appimage.txt"

echo "==> 4/5  Copying the application and its desktop integration files"
cp -r "${ROOT}/app" "${APPDIR}/usr/share/fallow/app"
install -Dm755 "${ROOT}/appimage/AppRun" "${APPDIR}/AppRun"
install -Dm644 "${ROOT}/packaging/${APP_ID}.desktop" "${APPDIR}/${APP_ID}.desktop"
install -Dm644 "${ROOT}/packaging/${APP_ID}-256.png" "${APPDIR}/${APP_ID}.png"
install -Dm644 "${ROOT}/packaging/${APP_ID}.svg" "${APPDIR}/${APP_ID}.svg"
# appimagetool wants .DirIcon to be the icon shown by file managers.
ln -sf "${APP_ID}.png" "${APPDIR}/.DirIcon"

# Byte-compiled files are useless in a read-only image and carry build paths.
find "${APPDIR}" -name '__pycache__' -prune -exec rm -rf {} +
find "${APPDIR}" -name '*.pyc' -delete

echo "==> 5/5  Squashing the AppDir into ${IMAGE}"
rm -f "${IMAGE}"
ARCH="${ARCH}" appimagetool "${APPDIR}" "${IMAGE}"

echo
echo "Built: ${IMAGE} ($(du -h "${IMAGE}" | cut -f1))"
echo
echo "Run it:"
echo "  ${IMAGE} /path/to/document.pdf"
echo
echo "Optional desktop integration (adds a menu entry and an icon):"
echo "  ${IMAGE} --appimage-extract-and-run  # or install it with AppImageLauncher"
