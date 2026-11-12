#!/usr/bin/env bash
# Install this unpacked Fallow build for the current user.
#
#   ./install.sh                        # into ~/.local, no root needed
#   sudo ./install.sh --prefix /usr/local
#
# Unpacked, the archive already runs in place (./fallow). Install only copies it
# somewhere stable and adds a menu entry and icons:
#
#   <prefix>/lib/fallow/                the payload (interpreter, app, launcher)
#   <prefix>/bin/fallow                 symlink to <prefix>/lib/fallow/AppRun
#   <prefix>/share/applications/org.fallow.PdfReader.desktop
#   <prefix>/share/icons/hicolor/{256x256,scalable}/apps/org.fallow.PdfReader.*
#
# Everything is user-local by default, so it works without root and without
# touching the system installation. Re-running upgrades in place.

set -euo pipefail

APP_ID="org.fallow.PdfReader"
PREFIX="${HOME}/.local"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'EOF'
Install the unpacked Fallow build.

Usage: ./install.sh [--prefix DIR]

  --prefix DIR   Install under DIR (default: ~/.local).
                 Use /usr/local for a system-wide install, with sudo.
  -h, --help     Show this message.

Run ./uninstall.sh with the same --prefix to remove it again.
EOF
}

fail() {
    echo "install.sh: $*" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prefix)
            [[ $# -ge 2 ]] || fail "--prefix needs a directory"
            PREFIX="$2"
            shift 2
            ;;
        --prefix=*)
            PREFIX="${1#*=}"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "install.sh: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

[[ -n "${PREFIX}" ]] || fail "--prefix cannot be empty"

# The payload has to be beside this script: installing copies it, it is not a
# downloader, so an incomplete extraction is caught here rather than at launch.
[[ -x "${SCRIPT_DIR}/AppRun" ]] \
    || fail "AppRun is missing next to this script - extract the archive first, then run ./install.sh from inside it"
[[ -x "${SCRIPT_DIR}/usr/python/bin/python3" ]] \
    || fail "the bundled Python is missing - the archive was not extracted completely"

mkdir -p "${PREFIX}"
PREFIX="$(cd "${PREFIX}" && pwd)"
[[ -w "${PREFIX}" ]] \
    || fail "${PREFIX} is not writable; install into ~/.local or re-run with sudo"

LIB_DIR="${PREFIX}/lib/fallow"
BIN_DIR="${PREFIX}/bin"
APPS_DIR="${PREFIX}/share/applications"
ICON_ROOT="${PREFIX}/share/icons/hicolor"

# Replace an earlier install, but never delete a directory that is not ours.
if [[ -e "${LIB_DIR}" ]]; then
    [[ -f "${LIB_DIR}/AppRun" ]] \
        || fail "${LIB_DIR} already exists and is not a Fallow install; move it aside first"
    rm -rf "${LIB_DIR}"
fi

echo "==> Copying Fallow into ${LIB_DIR}"
mkdir -p "${LIB_DIR}"
# -a keeps the bundled interpreter's permissions, and the launcher's symlink
# (fallow -> AppRun) inside the archive.
cp -a "${SCRIPT_DIR}/." "${LIB_DIR}/"

echo "==> Linking ${BIN_DIR}/fallow"
mkdir -p "${BIN_DIR}"
# AppRun resolves its own real path, so a symlink into another directory still
# finds the bundled interpreter.
ln -sfn "${LIB_DIR}/AppRun" "${BIN_DIR}/fallow"

echo "==> Installing the desktop entry and icons"
mkdir -p "${APPS_DIR}"
# The menu entry ships with "Exec=fallow %U", which relies on the launcher being
# on PATH. A desktop session does not necessarily have ~/.local/bin there, so
# point it at this install's absolute launcher instead.
sed "s|^Exec=.*|Exec=\"${BIN_DIR}/fallow\" %U|" \
    "${SCRIPT_DIR}/${APP_ID}.desktop" > "${APPS_DIR}/${APP_ID}.desktop"
chmod 0644 "${APPS_DIR}/${APP_ID}.desktop"
install -Dm644 "${SCRIPT_DIR}/${APP_ID}.png" \
    "${ICON_ROOT}/256x256/apps/${APP_ID}.png"
install -Dm644 "${SCRIPT_DIR}/${APP_ID}.svg" \
    "${ICON_ROOT}/scalable/apps/${APP_ID}.svg"

# Refresh the caches when the tools exist. ~/.local/share/icons usually has no
# index.theme, so gtk-update-icon-cache failing is expected and harmless.
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APPS_DIR}" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache --force --quiet "${ICON_ROOT}" >/dev/null 2>&1 || true
fi

echo
echo "Fallow installed."
echo
echo "  start it:      ${BIN_DIR}/fallow"
echo "  open a file:   ${BIN_DIR}/fallow document.pdf"
echo "  uninstall:     ${LIB_DIR}/uninstall.sh --prefix ${PREFIX}"
echo
case ":${PATH}:" in
    *":${BIN_DIR}:"*) echo "  ${BIN_DIR} is on PATH, so 'fallow' works too." ;;
    *) echo "  ${BIN_DIR} is not on PATH; use the full path above or add it to PATH." ;;
esac
