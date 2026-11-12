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

---

## 17:01 — The v0.14.1 release run failed; fixing the CI, cutting v0.14.2

**Objective.** Publish the tags' release. The run for `v0.14.1` failed in both
build jobs and the release job was skipped, so the tag existed with no assets.

**Solution.** Three separate environment gaps, each reproduced in a container
that matches the runner:

1. **The tarball smoke test** imported `app.main`, i.e. `PySide6.QtWidgets`, on a
   bare runner. Reproduced in `ubuntu:22.04`:
   `ImportError: libGL.so.1: cannot open shared object file`. The packaging was
   fine - the runner has no desktop libraries. The job now installs
   `libgl1 libegl1 libxkbcommon0 libglib2.0-0 libfontconfig1 libdbus-1-3`
   and the remaining X libraries before the import.
2. **The Flatpak build** died in `flatpak-builder` with
   `Failed to execute child process 'eu-strip'`: `eu-strip` (elfutils) is not in
   the Ubuntu image. The job installs `elfutils` now.
3. **After that**, `appstreamcli compose` failed with `file-read-error` and
   `filters-but-no-output`. Reproduced with a *minimal* metainfo, so it is not
   this app's data: Ubuntu 24.04 ships AppStream 1.0.2, which mis-resolves the
   unit paths when `flatpak-builder` passes `--prefix=/`; the identical command
   on Fedora's AppStream 1.1.3 prints `Success!`. Ubuntu has no newer package.

   A `fedora:44` container was tried for the Flatpak job, but this machine cannot
   run Flatpak's FUSE/rofiles path (`fusermount3: mount failed: Operation not
   permitted`, and `btrfs`+`podman` produced `Invalid cross-device link` during
   locale migration), so that variant could not be verified here. Since the
   Flatpak has never shipped and the task is the tarball/AppImage, the Flatpak
   job is now `continue-on-error: true`: it still runs and reports, but cannot
   hold back the packages that do build. Documented in the build guide's
   troubleshooting section.

The release job now tolerates an absent Flatpak and generates the release body
from the assets that actually arrived, so a release never advertises a package
it does not carry. Version bumped to 0.14.2 (0.14.1 was tagged but never
released).

**Actions Performed.**

1. Read the failed run's check-runs through the public API (job logs need a
   token): both build jobs failed, release skipped.
2. Reproduced the tarball failure and the fix in `ubuntu:22.04` with podman;
   verified the smoke-test commands again against the packaged archive.
3. Reproduced the Flatpak failures in `ubuntu:24.04` (eu-strip, then AppStream)
   and isolated the AppStream failure with a minimal metainfo and with
   Fedora 1.1.3 as the control.
4. Added the desktop-library step, `elfutils`, `continue-on-error` for the
   Flatpak job, and the generated release body/checksums.
5. Bumped the version to 0.14.2 in the scripts, metainfo, README and workflow.

**Verification Output.**

```
$ podman run ... ubuntu:22.04 ... import app.main
ImportError: libGL.so.1: cannot open shared object file: No such file or directory

$ podman run ... ubuntu:22.04 ... apt-get install libgl1 libegl1 libxkbcommon0 ...
packaged application ok
launch exit=124                          # offscreen window stayed up

$ podman run ... ubuntu:24.04 ... bash flatpak/build-flatpak.sh
Error: module python3-pymupdf: Failed to execute child process ?eu-strip? (No such file or directory)

$ ... after installing elfutils
Running appstreamcli compose
  E: file-read-error
  E: filters-but-no-output

$ appstreamcli compose --prefix=/ ... (same command, Fedora host, AppStream 1.1.3)
Success!

$ shellcheck -x <five scripts>
exit=0
$ actionlint .github/workflows/release.yml
exit=0
```

**References Used.**

1. flatpak-builder command reference (build flags used while isolating the
   locale/rofiles behaviour):
   <https://docs.flatpak.org/en/latest/flatpak-builder-command-reference.html>
2. AppStream release history - the 1.0.2 → 1.1 change that fixed compose's
   path handling: <https://github.com/ximion/appstream/releases>
3. GitHub Actions `jobs.<job_id>.continue-on-error`:
   <https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#jobsjob_idcontinue-on-error>

**Optional steps.**

- Give the Flatpak job a working environment (Fedora container with
  `--privileged`, or a newer AppStream on the runner) and drop
  `continue-on-error`, so releases carry the third package again.
- Add a `workflow_dispatch` dry-run input that builds without publishing, so a
  runner gap is found without consuming a version number.
- Cache the AppImage/tarball payload between the two build steps (already shared)
  and the Fedora `dnf` layer, if the Flatpak job moves to a container.

**Possible problems.**

- The Flatpak job is still red on every release; the release body simply leaves
  it out. That is visible in Actions but silent on the release page.
- The AppStream workaround is not in place: `ubuntu-24.04` is still the runner,
  so the job fails at compose until it moves.
- `fedora:44` may not be the stable container tag at the time the Flatpak job is
  fixed; pin whatever tag is current then.
- The `v0.14.1` tag exists with no release behind it. Removing it is a remote tag
  deletion and was not done without asking.

---

## 17:04 — Published v0.14.2

**Objective.** Get a release published that a reader can install straight from
the download.

**Solution.** Tagged `v0.14.2` at `8ec064c` on `main` (the log commit; the
packaging work is `43c2cd9` and the CI fixes `b8c3b9b`). The tag push ran
`Release` run 43325297020:

| Job | Result |
|---|---|
| Resolve the version | success |
| AppImage and portable tarball | success |
| Flatpak | failure (non-blocking, as designed) |
| Publish the release | success |

The release carries `Fallow-0.14.2-x86_64.AppImage` (141 MB),
`Fallow-0.14.2-x86_64.tar.gz` (156 MB) and `SHA256SUMS`. The body lists the two
packages that built and does not mention the Flatpak.

**Actions Performed.**

1. Pushed `development` and `main`, tagged and pushed `v0.14.2`.
2. Polled the run through the public API until it completed.
3. Downloaded the three published assets and ran `sha256sum -c SHA256SUMS`.
4. Installed the downloaded tarball into a throwaway prefix, launched it,
   checked the bundled interpreter and uninstalled.
5. Extracted the downloaded AppImage and imported its Qt stack.

**Verification Output.**

```
$ sha256sum -c SHA256SUMS
Fallow-0.14.2-x86_64.AppImage: OK
Fallow-0.14.2-x86_64.tar.gz: OK

$ ./Fallow-0.14.2-x86_64/install.sh --prefix /tmp/.../prefix
Fallow installed.
$ grep '^Exec=' .../share/applications/org.fallow.PdfReader.desktop
Exec="/tmp/.../prefix/bin/fallow" %U
$ QT_QPA_PLATFORM=offscreen timeout 8 .../prefix/bin/fallow
launch exit=124                                       # stayed up
$ .../lib/fallow/usr/python/bin/python3 -P -c "import PySide6, pymupdf, numpy"
packaged interpreters: 6.11.2 1.28.2 2.2.6
$ .../lib/fallow/uninstall.sh --prefix /tmp/.../prefix
uninstalled cleanly

$ ./Fallow-0.14.2-x86_64.AppImage --appimage-extract
$ squashfs-root/usr/python/bin/python3 -P -c "import PySide6, pymupdf, numpy"
appimage bundled interpreters ok
```

**References Used.**

1. GitHub REST API, releases:
   <https://docs.github.com/en/rest/releases/releases> - reading the published
   assets and the release body.
2. Viewing workflow run logs and job results:
   <https://docs.github.com/en/actions/how-tos/monitor-workflows/view-workflow-run-logs>
   - mapping the failed step from the job list.
3. GNU coreutils `sha256sum`:
   <https://www.gnu.org/software/coreutils/manual/html_node/sha2-utilities.html>
   - the `-c` verification used on the downloaded assets.

**Optional steps.**

- Fix the Flatpak job's environment and drop `continue-on-error`, then cut
  0.14.3 with all three packages.
- Delete the stray `v0.14.1` tag (remote tag deletion) once you decide it is
  unwanted, and the empty `v0.14.0` release from October.
- Sign `SHA256SUMS` with minisign or GPG and publish the signature.

**Possible problems.**

- `v0.14.1` is a tag with no release, and `v0.14.0` is a release with no assets
  (its run failed in October). Both are visible on the tags page until removed.
- The Flatpak is absent from this release; anyone following the README's Flatpak
  instructions will find no file. The README now says a release may not include
  it while its build environment is repaired.
- The release body is generated by shell `echo` calls; a change to the asset
  names must be mirrored in `.github/workflows/release.yml` and in the docs.
