# 2026-11-12 — Installable downloads: portable tarball, checksums, shared payload

Phase 17 of `TASKS.md`. The AppImage and the Flatpak were already downloadable
from GitHub Releases, but there was no tarball and therefore no way to install a
normal menu entry with a single downloaded file; the AppImage build also held the
payload staging that a second package would have had to duplicate.

---

## 15:43 — Ship a tarball with `install.sh`, pack both bundles from one payload

**Objective.** Make a download enough to install Fallow: a tarball that unpacks
and installs with one script (no root, no build tools, no Flatpak), an AppImage
that keeps working as the zero-install option, and `SHA256SUMS` so a download can
be checked. Build both Linux bundles from one staged payload instead of
duplicating the interpreter download and the pip step.

**Solution.**

- `packaging/stage-payload.sh` (new, sourced library) — one `stage_payload`
  function that lays out a relocatable AppDir: pinned python-build-standalone
  CPython, `packaging/requirements-runtime.txt`, `app/`, `AppRun`, desktop entry
  and icons, `__pycache__` removed. `FALLOW_ROOT` is derived from the library, so
  either build script can be run from anywhere.
- `appimage/build-appimage.sh` — reduced to two steps: stage through the shared
  function, then squash with `appimagetool`.
- `tarball/build-tarball.sh` (new) — stages the payload itself, or reuses one with
  `--payload build/appimage/Fallow.AppDir`, then adds `install.sh`,
  `uninstall.sh`, `README.txt` and a `fallow -> AppRun` link and packs
  `dist/Fallow-<version>-x86_64.tar.gz` with root-owned tar metadata.
- `tarball/install.sh` (new) — copies the payload to `<prefix>/lib/fallow`
  (default prefix `~/.local`), symlinks `<prefix>/bin/fallow`, rewrites the
  desktop entry's `Exec=` to the absolute launcher, installs both icons, and
  refreshes the desktop/icon caches when the helpers exist. Refuses to delete a
  `<prefix>/lib/fallow` that is not a Fallow install.
- `tarball/uninstall.sh` (new) — reverses exactly that, keeps
  `$XDG_DATA_HOME/linux-pdf-reader` and `$XDG_CONFIG_HOME/linux-pdf-reader`, and
  re-executes itself from a temporary copy because it deletes its own directory.
- `tarball/README.txt` (new) — the three commands a downloader needs.
- `.github/workflows/release.yml` — `appimage` job became `bundles`: AppImage,
  smoke test, tarball from the same AppDir, tarball smoke test (unpack, install
  into a throwaway prefix, check `Exec=`, import `app.main`), upload both; the
  release job writes `SHA256SUMS` and the release body lists all three packages.
- `README.md`, `flatpak_appimage_build.md`, `appimage_tarball.md`, `TASKS.md` —
  install instructions for three packages, a "Portable tarball" build section,
  the review/decision record, and the completed phase.
- `appimage/requirements-appimage.txt` → `packaging/requirements-runtime.txt`
  (git mv), because both bundles install that list, not just the AppImage.

**Actions Performed.**

1. Read the existing AppImage/Flatpak build scripts, release workflow, README and
   `flatpak_appimage_build.md` to keep the new package consistent with them.
2. Extracted the payload staging into `packaging/stage-payload.sh` and moved the
   runtime requirements file into `packaging/`.
3. Rewrote `appimage/build-appimage.sh` against the shared staging function.
4. Wrote `tarball/build-tarball.sh`, `tarball/install.sh`, `tarball/uninstall.sh`
   and `tarball/README.txt`.
5. Rebuilt the AppImage to prove the refactor did not change the result, then
   built the tarball standalone and from `--payload`.
6. Extracted the tarball into a temporary directory, installed it into throwaway
   prefixes (normal, with spaces, and with a foreign `lib/fallow` in the way),
   launched it offscreen, uninstalled it and checked for leftovers.
7. Updated the release workflow (tarball build + smoke test + `SHA256SUMS`) and
   the documentation.
8. Ran `shellcheck -x` on all five scripts and `actionlint` on the workflow.

**Verification Output.**

```
$ bash appimage/build-appimage.sh
==> 2/2  Squashing the AppDir into .../dist/Fallow-0.14.0-x86_64.AppImage
Built: /home/redram/python/Fallow/dist/Fallow-0.14.0-x86_64.AppImage (135M)

$ ./dist/Fallow-0.14.0-x86_64.AppImage --appimage-extract
$ squashfs-root/usr/python/bin/python3 -P -c "import PySide6, pymupdf, numpy; ..."
bundled interpreters ok 6.11.2 1.28.2 2.2.6

$ bash tarball/build-tarball.sh
Built: /home/redram/python/Fallow/dist/Fallow-0.14.0-x86_64.tar.gz (149M)

$ bash tarball/build-tarball.sh --payload build/appimage/Fallow.AppDir
Built: /home/redram/python/Fallow/dist/Fallow-0.14.0-x86_64.tar.gz (149M)

$ diff -r --exclude=__pycache__ app Fallow-0.14.0-x86_64/usr/share/fallow/app
app/ identical

$ Fallow-0.14.0-x86_64/install.sh --prefix /tmp/fallow-fresh.XXXX/prefix
==> Copying Fallow into /tmp/fallow-fresh.XXXX/prefix/lib/fallow
==> Linking /tmp/fallow-fresh.XXXX/prefix/bin/fallow
==> Installing the desktop entry and icons
Fallow installed.

$ readlink -f /tmp/fallow-fresh.XXXX/prefix/bin/fallow
/tmp/fallow-fresh.XXXX/prefix/lib/fallow/AppRun
$ grep '^Exec=' .../share/applications/org.fallow.PdfReader.desktop
Exec="/tmp/fallow-fresh.XXXX/prefix/bin/fallow" %U

$ QT_QPA_PLATFORM=offscreen timeout 10 /tmp/fallow-fresh.XXXX/prefix/bin/fallow
This plugin does not support propagateSizeHints()      # exit=124, so it ran
$ (cd /tmp && QT_QPA_PLATFORM=offscreen timeout 10 \
      /tmp/fallow-fresh.XXXX/Fallow-0.14.0-x86_64/fallow)
exit=124                                               # runs in place too

$ .../uninstall.sh --prefix /tmp/fallow-fresh.XXXX/prefix
==> Removed .../prefix/bin/fallow
==> Removed the desktop entry and icons
==> Removed .../prefix/lib/fallow
removed cleanly

$ ./install.sh --prefix "/tmp/fallow edge/pre fix"
Exec="/tmp/fallow edge/pre fix/bin/fallow" %U
launch exit=124                                        # quoted path still works

$ ./install.sh --prefix /tmp/p     # where lib/fallow belongs to something else
install.sh: /tmp/p/lib/fallow already exists and is not a Fallow install; move it aside first
exit=1; keepme untouched

$ shellcheck -x packaging/stage-payload.sh appimage/build-appimage.sh \
      tarball/build-tarball.sh tarball/install.sh tarball/uninstall.sh
exit=0
$ actionlint .github/workflows/release.yml
exit=0; jobs: prepare, bundles, flatpak, release
```

The temporary prefixes, the extracted archives and the scratch
`build/tarball/stage` tree were deleted afterwards; `dist/` holds the rebuilt
`Fallow-0.14.0-x86_64.AppImage` (135 MB) and `Fallow-0.14.0-x86_64.tar.gz`
(149 MB).

**References Used.**

1. Desktop Entry Specification, the `Exec` key:
   <https://specifications.freedesktop.org/desktop-entry-spec/latest/exec-variables.html>
   — the quoting rules behind `Exec="<prefix>/bin/fallow" %U`.
2. GNU tar manual, `--owner` / `--group` / `--numeric-owner`:
   <https://www.gnu.org/software/tar/manual/html_node/Attributes.html>
   — keeping the build account's uid out of the archive.
3. python-build-standalone releases:
   <https://github.com/astral-sh/python-build-standalone/releases>
   — the relocatable CPython both bundles unpack.

**Optional steps.**

- Sign the release assets (minisign or `gpg --detach-sign` on `SHA256SUMS`) so a
  download proves who built it, not only that it is intact.
- Add a `pull_request` job that builds the AppImage + tarball without publishing,
  so the shared staging change is exercised before a tag.
- Publish a `.zsync` next to the AppImage for delta updates.
- Register Fallow as the default PDF handler in `install.sh` (`xdg-mime default`)
  behind an opt-in flag, instead of only adding the menu entry.
- Cache `build/cache/` (the CPython tarball) and the pip wheels in CI to shorten
  the bundle job.

**Possible problems.**

- The workflow has not run on GitHub since the tarball was added; `actionlint`
  and every command were exercised locally, but the runner itself is unproven.
- `install.sh` rewrites `Exec=` with `sed "s|...|...|"`, so a prefix containing a
  literal `|` would break the entry. Paths with spaces are verified.
- Icons installed into `~/.local/share/icons/hicolor` are picked up by most
  desktops immediately; some sessions need a re-login before the menu icon
  appears. `gtk-update-icon-cache` failing on `~/.local` is expected and ignored.
- `SHA256SUMS` is unsigned, so it detects a corrupted download but not a replaced
  artifact.
- The tarball is gzip (149 MB) versus the AppImage's squashfs (135 MB); zstd
  would shrink it, at the cost of requiring `tar --zstd` on the target.
- `install.sh` and `uninstall.sh` assume a POSIX host (they use `readlink -f`,
  `cp -a`, GNU-ish `install`); fine for the supported Linux-only target, but it
  would need work before any broader packaging.
