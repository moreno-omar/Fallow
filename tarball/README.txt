Fallow - portable Linux build
=============================

A one-page-at-a-time PDF reader. Everything it needs - the Python interpreter,
Qt, PyMuPDF, numpy and the application - is inside this directory. The only
runtime dependencies are glibc and the X11/Wayland client libraries.

Run it without installing anything:

    ./fallow
    ./fallow document.pdf

Install it for the current user (adds a menu entry, an icon and a `fallow`
command; no root, no build):

    ./install.sh

Install it system-wide instead:

    sudo ./install.sh --prefix /usr/local

Remove it again (your library, bookmarks and notes are kept):

    ~/.local/lib/fallow/uninstall.sh

Your data lives under $XDG_DATA_HOME/linux-pdf-reader (default
~/.local/share/linux-pdf-reader) and $XDG_CONFIG_HOME/linux-pdf-reader.

Keep the whole directory together: the launcher finds the bundled interpreter
relative to itself, so moving or installing a single file out of it will not
work.
