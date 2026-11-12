#!/usr/bin/env bash
# Shared payload staging for the AppImage and the portable tarball.
#
# Sourced by the two build scripts, never executed on its own:
#
#   source packaging/stage-payload.sh
#   stage_payload build/appimage/Fallow.AppDir
#
# Both packages contain the same thing - a standalone CPython, the runtime
# wheels, and the application - so it is assembled here once. Only the container
# differs: the AppImage wraps the directory in squashfs, the tarball compresses
# it and adds install.sh. Staging once is also why the release workflow can build
# both packages from a single download-and-pip pass.
#
# Callers own `set -euo pipefail` and must set VERSION and ARCH before they call
# stage_payload. FALLOW_ROOT is derived from this file, so it stays correct no
# matter which directory the caller is run from.

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "stage-payload.sh is a library; source it from a build script" >&2
    exit 64
fi

# shellcheck disable=SC2034  # read by the sourcing build scripts
FALLOW_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APP_ID="org.fallow.PdfReader"
# Pinned standalone CPython. Any 3.10-3.13 works: PySide6, PyMuPDF, and numpy all
# publish abi3 wheels. Change both values together; release tags are listed at
# https://github.com/astral-sh/python-build-standalone/releases
PBS_RELEASE="20260924"
PBS_PYTHON="3.13.15"

ARCH="${ARCH:-x86_64}"
# Shared by both builds so a machine that produced an AppImage does not download
# the interpreter again to produce the tarball.
CACHE_DIR="${FALLOW_ROOT}/build/cache"

PYTHON_TARBALL="cpython-${PBS_PYTHON}+${PBS_RELEASE}-${ARCH}-unknown-linux-gnu-install_only_stripped.tar.gz"
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_RELEASE}/${PYTHON_TARBALL}"

# Lay out a complete, relocatable AppDir at $1.
#
# The result is what both packages ship: usr/python (the interpreter and the
# wheels), usr/share/fallow/app (the code), AppRun, and the desktop integration
# files. It deliberately knows nothing about appimagetool or tar, so either
# caller can use it.
stage_payload() {
    local appdir="${1:?stage_payload needs a target directory}"
    local python_tarball_path="${CACHE_DIR}/${PYTHON_TARBALL}"

    rm -rf "${appdir}"
    mkdir -p "${appdir}/usr/share/fallow" "${CACHE_DIR}"

    if [[ ! -f "${python_tarball_path}" ]]; then
        curl --fail --location --output "${python_tarball_path}" "${PYTHON_URL}"
    fi
    # The tarball holds a single "python/" directory, so the interpreter lands at
    # usr/python/bin/python3 - a path AppRun can find relative to its own
    # directory, which is what makes the payload relocatable.
    tar -xzf "${python_tarball_path}" -C "${appdir}/usr"

    local python="${appdir}/usr/python/bin/python3"
    "${python}" --version

    "${python}" -m pip install \
        --no-cache-dir \
        --disable-pip-version-check \
        --quiet \
        -r "${FALLOW_ROOT}/packaging/requirements-runtime.txt"

    cp -r "${FALLOW_ROOT}/app" "${appdir}/usr/share/fallow/app"
    install -Dm755 "${FALLOW_ROOT}/appimage/AppRun" "${appdir}/AppRun"
    install -Dm644 "${FALLOW_ROOT}/packaging/${APP_ID}.desktop" "${appdir}/${APP_ID}.desktop"
    install -Dm644 "${FALLOW_ROOT}/packaging/${APP_ID}-256.png" "${appdir}/${APP_ID}.png"
    install -Dm644 "${FALLOW_ROOT}/packaging/${APP_ID}.svg" "${appdir}/${APP_ID}.svg"
    # appimagetool wants .DirIcon to be the icon shown by file managers; the
    # tarball ignores it.
    ln -sf "${APP_ID}.png" "${appdir}/.DirIcon"

    # Byte-compiled files are useless in a read-only image, carry build paths,
    # and would be stale the moment the payload is copied elsewhere.
    find "${appdir}" -name '__pycache__' -prune -exec rm -rf {} +
    find "${appdir}" -name '*.pyc' -delete
}
