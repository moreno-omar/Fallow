#!/usr/bin/env bash
# Remove an installation made by install.sh.
#
#   ~/.local/lib/fallow/uninstall.sh
#   ~/.local/lib/fallow/uninstall.sh --prefix /usr/local     # system-wide, sudo
#
# Your documents, library, bookmarks and notes are left alone: they live under
# $XDG_DATA_HOME/linux-pdf-reader and $XDG_CONFIG_HOME/linux-pdf-reader, which
# this script never touches.

set -euo pipefail

APP_ID="org.fallow.PdfReader"
PREFIX="${HOME}/.local"

# Bash reads a script from disk as it runs, and the last step deletes the
# directory this file lives in. Continuing from a copy keeps the script readable
# to the end; FALLOW_UNINSTALL_TMP marks the copy so it does not copy again.
if [[ -z "${FALLOW_UNINSTALL_TMP:-}" ]]; then
    FALLOW_UNINSTALL_TMP="$(mktemp "${TMPDIR:-/tmp}/fallow-uninstall.XXXXXX")"
    export FALLOW_UNINSTALL_TMP
    cp "${BASH_SOURCE[0]}" "${FALLOW_UNINSTALL_TMP}"
    exec bash "${FALLOW_UNINSTALL_TMP}" "$@"
fi
trap 'rm -f "${FALLOW_UNINSTALL_TMP}"' EXIT

usage() {
    cat <<'EOF'
Remove a Fallow install created by install.sh.

Usage: uninstall.sh [--prefix DIR]

  --prefix DIR   The prefix the install used (default: ~/.local).
  -h, --help     Show this message.

Your library, bookmarks and notes are kept.
EOF
}

fail() {
    echo "uninstall.sh: $*" >&2
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
            echo "uninstall.sh: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

[[ -d "${PREFIX}" ]] || fail "${PREFIX} does not exist"
PREFIX="$(cd "${PREFIX}" && pwd)"

LIB_DIR="${PREFIX}/lib/fallow"
BIN_DIR="${PREFIX}/bin"
APPS_DIR="${PREFIX}/share/applications"
ICON_ROOT="${PREFIX}/share/icons/hicolor"

if [[ ! -d "${LIB_DIR}" && ! -f "${APPS_DIR}/${APP_ID}.desktop" ]]; then
    echo "uninstall.sh: no Fallow install found under ${PREFIX}; nothing to do"
    exit 0
fi

# Only the symlink this installer created is removed. A real file named "fallow"
# belongs to something else and is reported rather than deleted.
if [[ -L "${BIN_DIR}/fallow" ]]; then
    rm -f "${BIN_DIR}/fallow"
    echo "==> Removed ${BIN_DIR}/fallow"
elif [[ -e "${BIN_DIR}/fallow" ]]; then
    echo "uninstall.sh: ${BIN_DIR}/fallow is not a symlink; leaving it in place" >&2
fi

rm -f "${APPS_DIR}/${APP_ID}.desktop"
rm -f "${ICON_ROOT}/256x256/apps/${APP_ID}.png"
rm -f "${ICON_ROOT}/scalable/apps/${APP_ID}.svg"
echo "==> Removed the desktop entry and icons"

if [[ -d "${LIB_DIR}" ]]; then
    rm -rf "${LIB_DIR}"
    echo "==> Removed ${LIB_DIR}"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APPS_DIR}" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache --force --quiet "${ICON_ROOT}" >/dev/null 2>&1 || true
fi

echo
echo "Fallow removed. Your library, bookmarks and notes were left in place under"
echo "\${XDG_DATA_HOME:-~/.local/share}/linux-pdf-reader and"
echo "\${XDG_CONFIG_HOME:-~/.config}/linux-pdf-reader."
