#!/bin/sh
# Launcher installed as /app/bin/fallow inside the Flatpak.
#
# The application code does not live in site-packages (that path is Python
# version specific, and the Flatpak runtime moves between Python releases), so
# PYTHONPATH points at the folder that contains the "app" package instead.
set -eu

export PYTHONPATH="/app/lib/fallow${PYTHONPATH:+:$PYTHONPATH}"
# The sandbox root filesystem is read-only for the application, so writing .pyc
# files would only produce warnings on every start.
export PYTHONDONTWRITEBYTECODE=1

# ``-P`` keeps the current working directory off sys.path. Without it, launching
# the Flatpak from inside a source checkout makes Python import the *host* copy
# of ``app`` (the checkout's own directory is sys.path[0]) instead of the
# installed one. PYTHONPATH is unaffected, so the bundled code still wins.
exec python3 -P -m app.main "$@"
