#!/usr/bin/env bash
# Build Fallow as a portable tarball that can be installed without building
# anything on the machine that downloads it.
#
#   bash tarball/build-tarball.sh
#   bash tarball/build-tarball.sh --payload build/appimage/Fallow.AppDir
#
# Produces dist/Fallow-<version>-<arch>.tar.gz. Unpacked it looks like:
#
#   Fallow-0.14.1-x86_64/
#   ├── fallow -> AppRun            launcher, runs in place
#   ├── install.sh                  installs into ~/.local (or --prefix)
#   ├── uninstall.sh                removes that install, keeps your data
#   ├── README.txt
#   ├── AppRun
#   ├── usr/python/                 standalone CPython + wheels
#   └── usr/share/fallow/app/       the application
#
# --payload reuses an AppDir that appimage/build-appimage.sh already staged. The
# release workflow uses it so both packages come from one download-and-pip pass
# instead of two. Without it, this script stages its own payload and does not
# need appimagetool at all.
#
# Requires: curl and tar. Set FALLOW_VERSION to name the archive after a version.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../packaging/stage-payload.sh
source "${SCRIPT_DIR}/../packaging/stage-payload.sh"

# Matches appimage/build-appimage.sh: the release workflow passes the git tag.
VERSION="${FALLOW_VERSION:-0.14.1}"

BUNDLE="Fallow-${VERSION}-${ARCH}"
BUILD_DIR="${FALLOW_ROOT}/build/tarball"
STAGE_DIR="${BUILD_DIR}/stage"
BUNDLE_DIR="${STAGE_DIR}/${BUNDLE}"
DIST_DIR="${FALLOW_ROOT}/dist"
ARCHIVE="${DIST_DIR}/${BUNDLE}.tar.gz"
PAYLOAD_SOURCE=""

usage() {
    cat <<'EOF'
Build dist/Fallow-<version>-<arch>.tar.gz, a portable build with install.sh.

Usage: tarball/build-tarball.sh [--payload APPDIR]

  --payload APPDIR  Reuse an already staged AppDir (for example
                    build/appimage/Fallow.AppDir) instead of building one.
  -h, --help        Show this message.

Set FALLOW_VERSION to change the version in the archive name.
EOF
}

fail() {
    echo "build-tarball.sh: $*" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --payload)
            [[ $# -ge 2 ]] || fail "--payload needs a directory"
            PAYLOAD_SOURCE="$2"
            shift 2
            ;;
        --payload=*)
            PAYLOAD_SOURCE="${1#*=}"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "build-tarball.sh: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

mkdir -p "${BUILD_DIR}" "${DIST_DIR}"
rm -rf "${STAGE_DIR}"

if [[ -n "${PAYLOAD_SOURCE}" ]]; then
    echo "==> 1/2  Reusing the payload at ${PAYLOAD_SOURCE}"
    [[ -x "${PAYLOAD_SOURCE}/AppRun" ]] \
        || fail "${PAYLOAD_SOURCE} is not a staged AppDir (no AppRun)"
    [[ -x "${PAYLOAD_SOURCE}/usr/python/bin/python3" ]] \
        || fail "${PAYLOAD_SOURCE} has no bundled Python"
    mkdir -p "${STAGE_DIR}"
    cp -a "${PAYLOAD_SOURCE}" "${BUNDLE_DIR}"
else
    echo "==> 1/2  Staging the payload (CPython ${PBS_PYTHON}, wheels, application)"
    stage_payload "${BUNDLE_DIR}"
fi

echo "==> 2/2  Adding the installer and packing ${ARCHIVE}"
install -Dm755 "${SCRIPT_DIR}/install.sh" "${BUNDLE_DIR}/install.sh"
install -Dm755 "${SCRIPT_DIR}/uninstall.sh" "${BUNDLE_DIR}/uninstall.sh"
install -Dm644 "${SCRIPT_DIR}/README.txt" "${BUNDLE_DIR}/README.txt"
# Lets the archive run in place: ./fallow needs no install step at all.
ln -sfn AppRun "${BUNDLE_DIR}/fallow"

rm -f "${ARCHIVE}"
# --owner/--group/--numeric-owner keep the archive free of the build account's
# uid, which would otherwise unpack as an unknown user on the target machine.
tar --create --gzip --file "${ARCHIVE}" \
    --directory "${STAGE_DIR}" \
    --owner=0 --group=0 --numeric-owner \
    "${BUNDLE}"

echo
echo "Built: ${ARCHIVE} ($(du -h "${ARCHIVE}" | cut -f1))"
echo
echo "Install it:"
echo "  tar -xzf ${ARCHIVE##*/}"
echo "  cd ${BUNDLE} && ./install.sh"
echo
echo "Or just run it in place:"
echo "  ./${BUNDLE}/fallow /path/to/document.pdf"
