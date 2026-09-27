#!/usr/bin/env bash
# Build Fallow as a single-file Flatpak bundle.
#
#   flatpak/build-flatpak.sh
#
# Produces build/flatpak/org.fallow.PdfReader.flatpak, which installs on any
# machine with Flatpak - no source checkout or Python needed there:
#
#   flatpak install --user build/flatpak/org.fallow.PdfReader.flatpak
#   flatpak run org.fallow.PdfReader
#
# Requires: flatpak, flatpak-builder, and the flathub remote (see
# flatpak_appimage_build.md). Everything is installed for the current user, so
# no root password is needed and nothing outside the home directory changes.

set -euo pipefail

APP_ID="org.fallow.PdfReader"
# The BaseApp branch in the manifest must equal the runtime branch below; both
# ship the same PySide6 and Python, which is what makes the wheels compatible.
RUNTIME_VERSION="6.11"
BASE_APP="io.qt.PySide.BaseApp"
BRANCH="stable"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT}/build/flatpak"
BUNDLE="${BUILD_DIR}/${APP_ID}.flatpak"

# Returns 0 when the host carries the flatpak/ostree xattr regression of flatpak
# issue #6818, by running the very command that trips over it. The output is
# captured before matching because ``pipefail`` would otherwise report the
# probe's own failure as the result of the pipeline and hide the match.
host_has_xattr_regression() {
    local probe output
    probe="$(mktemp -d)"
    output="$(flatpak build-init \
        --base="${BASE_APP}" \
        --base-version="${RUNTIME_VERSION}" \
        --arch=x86_64 \
        "${probe}/init" \
        org.fallow.Probe \
        org.kde.Sdk \
        org.kde.Platform \
        "${RUNTIME_VERSION}" 2>&1 || true)"
    rm -rf "${probe}"
    grep -q "lsetxattr(security.selinux)" <<<"${output}"
}

# Compiles flatpak/lsetxattr-shim.c and echoes the path of the shared object.
build_xattr_shim() {
    local shim="${BUILD_DIR}/lsetxattr-shim.so"
    cc -shared -fPIC -O2 -o "${shim}" "${ROOT}/flatpak/lsetxattr-shim.c" -ldl
    echo "${shim}"
}

echo "==> 1/4  Installing the runtime, SDK, and PySide6 BaseApp (skipped when present)"
flatpak install --user -y --noninteractive flathub \
    "org.kde.Platform//${RUNTIME_VERSION}" \
    "org.kde.Sdk//${RUNTIME_VERSION}" \
    "${BASE_APP}//${RUNTIME_VERSION}"

mkdir -p "${BUILD_DIR}"

echo "==> 2/4  Checking for the flatpak/ostree xattr regression (flatpak#6818)"
PRELOAD=""
if host_has_xattr_regression; then
    echo "    Host is affected: flatpak < 1.18.3 on a SELinux-enabled kernel."
    echo "    Building flatpak/lsetxattr-shim.c to work around it."
    echo "    Upgrading flatpak and ostree makes this step unnecessary."
    PRELOAD="$(build_xattr_shim)"
else
    echo "    Not affected - building without the shim."
fi

echo "==> 3/4  Building the application into ${BUILD_DIR}"
LD_PRELOAD="${PRELOAD}" flatpak-builder \
    --user \
    --force-clean \
    --default-branch="${BRANCH}" \
    --repo="${BUILD_DIR}/repo" \
    "${BUILD_DIR}/build-dir" \
    "${ROOT}/flatpak/${APP_ID}.yml"

echo "==> 4/4  Bundling ${BUNDLE}"
rm -f "${BUNDLE}"
flatpak build-bundle "${BUILD_DIR}/repo" "${BUNDLE}" "${APP_ID}" "${BRANCH}"

echo
echo "Built: ${BUNDLE} ($(du -h "${BUNDLE}" | cut -f1))"
echo
echo "Install and run:"
echo "  flatpak install --user -y ${BUNDLE}"
echo "  flatpak run ${APP_ID} /path/to/document.pdf"
