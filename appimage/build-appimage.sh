#!/usr/bin/env bash
# Build Fallow as a portable AppImage.
#
#   appimage/build-appimage.sh
#
# Produces dist/Fallow-0.14.2-x86_64.AppImage - a single self-contained file:
#
#   chmod +x dist/Fallow-0.14.2-x86_64.AppImage
#   ./dist/Fallow-0.14.2-x86_64.AppImage /path/to/document.pdf
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
#
# The payload itself is staged by packaging/stage-payload.sh, which the portable
# tarball build shares - see tarball/build-tarball.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../packaging/stage-payload.sh
source "${SCRIPT_DIR}/../packaging/stage-payload.sh"

# Overridable so the release workflow can name the image after the git tag
# (FALLOW_VERSION=0.15.0). Local builds keep the pinned value.
VERSION="${FALLOW_VERSION:-0.14.2}"

APPDIR="${FALLOW_ROOT}/build/appimage/Fallow.AppDir"
DIST_DIR="${FALLOW_ROOT}/dist"
IMAGE="${DIST_DIR}/Fallow-${VERSION}-${ARCH}.AppImage"

echo "==> 1/2  Staging the payload (CPython ${PBS_PYTHON}, wheels, application)"
stage_payload "${APPDIR}"

echo "==> 2/2  Squashing the AppDir into ${IMAGE}"
mkdir -p "${DIST_DIR}"
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
