# Flatpak and AppImage builds

Fallow ships two ways so that nobody has to clone the repository and install
Python to read a PDF. Both are produced by a single script.

| | Flatpak | AppImage |
|---|---|---|
| Artifact | `build/flatpak/org.fallow.PdfReader.flatpak` (86 MB) | `dist/Fallow-0.14.0-x86_64.AppImage` (135 MB) |
| Install | `flatpak install --user <file>` | `chmod +x` and run |
| Sandboxed | yes | no |
| What it needs at runtime | `org.kde.Platform//6.11` + `io.qt.PySide.BaseApp//6.11` (its manifest pulls them in) | glibc and the X11/Wayland client libraries |
| What it needs to build | `flatpak`, `flatpak-builder`, the flathub remote | `curl`, `tar`, `appimagetool` |
| First build | ~2 min once the runtimes are downloaded | ~2 min once the wheels are downloaded |

Everything the builds produce lands in `build/` and `dist/`, both git-ignored.

---

## 0. One-time host setup

```bash
# Fedora / RHEL family. Debian/Ubuntu: apt install flatpak flatpak-builder
sudo dnf install -y flatpak flatpak-builder

# The flathub remote is what supplies the runtime, the SDK, and the BaseApp.
# Add it once; --user avoids needing a password.
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

# appimagetool is a single static binary - drop it anywhere on PATH.
sudo curl -L -o /usr/local/bin/appimagetool \
  https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
sudo chmod +x /usr/local/bin/appimagetool
```

`appimagetool` needs `mksquashfs` (it bundles it) and `desktop-file-validate`
(optional, only used for validation warnings).

---

## 1. Flatpak

### The short version

```bash
bash flatpak/build-flatpak.sh                                     # build
flatpak install --user -y build/flatpak/org.fallow.PdfReader.flatpak
flatpak run org.fallow.PdfReader                                  # or: ... org.fallow.PdfReader doc.pdf
```

To remove it again:

```bash
flatpak uninstall --user org.fallow.PdfReader
rm -rf ~/.var/app/org.fallow.PdfReader          # its session file and library
```

### What the script does

1. **Installs the runtime, the SDK, and the BaseApp** for the current user
   (`--user`, so no root password and nothing outside `$HOME` changes):
   `org.kde.Platform//6.11`, `org.kde.Sdk//6.11`, `io.qt.PySide.BaseApp//6.11`.
   Already-installed refs are skipped, so this step is instant the second time.
2. **Checks for the flatpak/ostree xattr regression** (see *Troubleshooting*).
3. **Runs `flatpak-builder`**, which downloads the PyMuPDF wheel, unpacks the
   BaseApp, copies `app/` and the desktop/metainfo/icon files into `/app/`, and
   exports the result into a local OSTree repository.
4. **Bundles the repository** into one installable `.flatpak` file.

### Why there is a BaseApp

`flatpak-pip-generator` refuses to generate a module for PySide6 and prints:

```
Please use the baseapp https://github.com/flathub/io.qt.PySide.BaseApp
```

It refuses because PySide6 publishes no source distribution - only wheels of
several hundred megabytes - and pip-installing Qt inside a flatpak build is both
slow and easy to get wrong. `io.qt.PySide.BaseApp` is a base application that
already contains PySide6, shiboken6, and numpy compiled against the matching
runtime, so the manifest only has to add PyMuPDF.

That is why `flatpak/python3-modules.json` contains exactly one module.
**Never put PySide6, PySide6-Essentials, PySide6-Addons, or shiboken6 in the
generator input** - it will exit with the message above instead of generating.

### Regenerating `flatpak/python3-modules.json`

Only needed when `pymupdf` is bumped. The generator has its own dependencies, so
give it a throwaway virtualenv:

```bash
python3 -m venv /tmp/genvenv
/tmp/genvenv/bin/pip install requirements-parser packaging

cd flatpak
/tmp/genvenv/bin/python ../flatpak-pip-generator.py \
    --runtime=org.kde.Sdk//6.11 \
    --prefer-wheels pymupdf \
    --wheel-arches x86_64 \
    --checker-data \
    --output python3-modules.json \
    "pymupdf==1.28.2"
```

Three flags matter and each one has a reason:

- `--runtime=org.kde.Sdk//6.11` lets the generator inspect the *runtime's*
  Python and choose a wheel with the right tags. The SDK is used rather than the
  Platform runtime because only the SDK ships `pip3`, which the generator shells
  out to. Both are built on the same freedesktop SDK release, so the tags match.
- `--prefer-wheels pymupdf` is essential. Without it the generator picks the
  source distribution and flatpak-builder would compile MuPDF from scratch.
- `--wheel-arches x86_64` keeps a single-architecture module. Drop it to emit
  `x86_64` and `aarch64` sources for a multi-arch build.

### Flatpak files

| Path | Purpose |
|---|---|
| `flatpak/org.fallow.PdfReader.yml` | the manifest: runtime, BaseApp, permissions, modules |
| `flatpak/python3-modules.json` | generated PyMuPDF module (pinned URL + sha256) |
| `flatpak/fallow-launcher.sh` | installed as `/app/bin/fallow`; sets `PYTHONPATH`, runs the app |
| `flatpak/lsetxattr-shim.c` | workaround for flatpak#6818 - delete it once the host is fixed |
| `flatpak/build-flatpak.sh` | the build script |

---

## 2. AppImage

### The short version

```bash
bash appimage/build-appimage.sh
./dist/Fallow-0.14.0-x86_64.AppImage                          # or: ... /path/to/document.pdf
```

### What the script does

1. **Creates the AppDir skeleton** under `build/appimage/Fallow.AppDir`.
2. **Unpacks a standalone CPython** from
   [python-build-standalone](https://github.com/astral-sh/python-build-standalone)
   into `usr/python/`. The download is cached in `build/appimage/cache/`.
3. **Installs the runtime dependencies** from
   `appimage/requirements-appimage.txt` into that interpreter.
4. **Copies** `app/`, `AppRun`, the desktop file, and the icons into place, then
   deletes every `__pycache__`.
5. **Runs `appimagetool`** to squash the AppDir into one executable file.

### Why python-build-standalone

An AppImage has to be self-contained, so it cannot rely on the host's Python. A
`python -m venv` would still point at the system interpreter, and a portable
Python built from source is a long detour. python-build-standalone publishes
relocatable CPython tarballs whose prefix is derived from the executable's own
path, which is exactly what an AppImage needs: unpack it, and it works from
wherever the image is mounted.

The tarball and both version numbers are pinned at the top of
`appimage/build-appimage.sh`.

### Why PySide6-Essentials and not PySide6

`requirements.txt` pins `PySide6`, the meta package, which installs **both**
`PySide6-Essentials` and `PySide6-Addons`. The reader imports only `QtCore`,
`QtGui`, and `QtWidgets` - all of them in Essentials. Installing Addons inside a
distributed image would add roughly 250 MB of Qt modules that are never loaded,
so `appimage/requirements-appimage.txt` lists `PySide6-Essentials` instead.

**Keep those two files in step.** Whenever `requirements.txt` changes, change
`appimage/requirements-appimage.txt` to match.

### AppImage files

| Path | Purpose |
|---|---|
| `appimage/build-appimage.sh` | the build script |
| `appimage/AppRun` | entry point inside the image; sets `PYTHONPATH`, runs the app |
| `appimage/requirements-appimage.txt` | runtime dependencies, Essentials instead of full PySide6 |
| `packaging/` | shared with the Flatpak (see below) |

### Shared files

Both formats describe the same application, so the branding lives in one place:

| Path | Purpose |
|---|---|
| `packaging/org.fallow.PdfReader.desktop` | the menu entry |
| `packaging/org.fallow.PdfReader.metainfo.xml` | the AppStream description |
| `packaging/org.fallow.PdfReader.svg` | scalable icon (from `fallow_app_icon.svg`) |
| `packaging/org.fallow.PdfReader-256.png` | 256x256 icon exported from the source icon |

The app ID `org.fallow.PdfReader` appears in all four, plus in the Flatpak
manifest filename and its `app-id`, plus in the icon filename inside the AppDir.
Flatpak and the desktop environment match these by string, so renaming the app
means editing every one of them together.

`fallow-screenshot.png` at the repository root is the software-centre screenshot.
It is deliberately **not** copied into `packaging/`: AppStream requires the
`<image>` to be a web URL, so the file is never installed into either package -
the metainfo only points at its published copy.

---

## 3. The two traps found while packaging

Both were real failures during the first build, not theory. Anything that
packages this app has to handle them.

**1. The working directory can shadow the installed code.** `flatpak run`
inherits the caller's working directory, and Python puts the working directory
first on `sys.path` when running `-m`. Start the Flatpak from inside a source
checkout and the *checkout's* `app` package is imported instead of the installed
one - silently testing or running the wrong code. Both launchers therefore run
the interpreter with **`-P`**, which keeps the working directory off `sys.path`
while leaving `PYTHONPATH` alone. Verified: from inside the repository, the app
resolves to `/app/lib/fallow/app/__init__.py`, not the checkout.

**2. The sample PDFs are not in a packaged build.** `*.pdf` is in `.gitignore`,
so `alices-adventures-in-wonderland.pdf` and `frankenstein.pdf` exist only in an
author's checkout. `MainWindow` used to open them unconditionally on first
launch, which in a packaged build pointed at a nonexistent path and aborted the
launch. It now looks for them, skips the ones that are missing, and starts with
an empty window instead. The first launch of either package shows an empty
window by design - use `Ctrl+O` to open a document.

---

## 4. Changing a version

| You changed | Also update |
|---|---|
| a dependency in `requirements.txt` | `appimage/requirements-appimage.txt`, then rebuild the AppImage |
| `pymupdf` | regenerate `flatpak/python3-modules.json` (see above), then rebuild the Flatpak |
| the app version | `VERSION` in `appimage/build-appimage.sh`, the `<release>` in `packaging/org.fallow.PdfReader.metainfo.xml` |
| PySide6 | nothing for the AppImage beyond `appimage/requirements-appimage.txt`. For the Flatpak you cannot pin PySide6 - it is whatever the BaseApp provides, so bump `base-version` **and** `runtime-version` together, and `RUNTIME_VERSION` in `flatpak/build-flatpak.sh` |

The PySide6 pair has to move together because the BaseApp is built against one
runtime branch; mixing them gives Qt libraries that do not match the runtime's
own.

---

## 5. Troubleshooting

### `error: lsetxattr(security.selinux): Operation not supported`

This is [flatpak#6818](https://github.com/flatpak/flatpak/issues/6818): a
regression introduced after 1.17.6, fixed in flatpak 1.18.3 and the matching
ostree. **Fedora 44 shipped flatpak 1.18.2 and ostree 2026.4, which still have
it**, so on Fedora 44 every `flatpak build-init --base=...` fails and no Flatpak
that uses a base application can be built.

`flatpak/build-flatpak.sh` detects it (by running the failing command once and
matching the message) and then compiles `flatpak/lsetxattr-shim.c` and injects
it with `LD_PRELOAD`. The shim does two things:

- it makes xattrs go through the path rather than the symlink, because
  `lsetxattr()` on `/proc/self/fd/N` labels the procfs magic link instead of the
  open file;
- it ignores the one `security.selinux` failure an unprivileged user is not
  allowed to cause, which is harmless for a local build: the files are relabelled
  from the host policy when the bundle is installed.

**Prefer the real fix.** Once a fixed flatpak/ostree is available in the
distribution, upgrade and delete `flatpak/lsetxattr-shim.c` plus the detection
step - the script simply stops using it, prints "Not affected", and the file can
go. The script is written so that a healthy host never needs the shim.

### `flatpak-pip-generator` prints "Please use the baseapp ..."

Expected. PySide6 cannot be generated. Take PySide6 out of the generator input
and let the BaseApp provide it (see *Why there is a BaseApp*).

### The Flatpak runs but finds no documents

The window starts empty on a first run - there is no session yet and the sample
PDFs are not packaged. Open something with `Ctrl+O`, or pass a file:

```bash
flatpak run org.fallow.PdfReader ~/Documents/some.pdf
```

The Flatpak has `--filesystem=home`, so it can read documents anywhere in your
home directory and can re-open them on the next launch.

### The AppImage will not start: "failed to open /dev/fuse"

FUSE is unavailable (common in containers and on some locked-down systems). Run
the image without mounting it:

```bash
./dist/Fallow-0.14.0-x86_64.AppImage --appimage-extract-and-run doc.pdf
```

### The AppImage throws errors about `libGL`, `libxcb`, or `xkbcommon`

The image carries Qt but not the X11/Wayland client libraries, which are
expected to come from the host desktop. Install them from your distribution
(`mesa-libGL`, `libxkbcommon-x11`, `libxcb` on Fedora).

### No menu entry after installing the Flatpak

Flatpak writes the exported entry to
`~/.local/share/flatpak/exports/share/applications/org.fallow.PdfReader.desktop`.
If it does not appear, check that the directory is on `XDG_DATA_DIRS`, or run
`update-desktop-database ~/.local/share/applications` and log in again.

---

## 6. What was verified

Both packages were built and exercised on Fedora 44 (KDE, Wayland, SELinux
enforcing). Checks and results:

| Check | Result |
|---|---|
| Flatpak build | `build/flatpak/org.fallow.PdfReader.flatpak`, 86 MB |
| AppImage build | `dist/Fallow-0.14.0-x86_64.AppImage`, 135 MB |
| Bundled versions, Flatpak | PyMuPDF 1.28.2, PySide6 6.11.2, numpy 2.3.5 (numpy from the BaseApp) |
| Bundled versions, AppImage | PyMuPDF 1.28.2, PySide6 6.11.2, numpy 2.2.6 |
| First launch, clean profile, no arguments | empty window, no traceback, session written with `"tabs": []` |
| Launch with a PDF argument | one tab, 277 pages, page bar shows `of 277` |
| Page turning and zoom inside the package | `next_page()` -> page 1, `zoom_in()` -> 1.15 |
| Sidebar | opens and is visible inside the package |
| `import app` from inside the source checkout | resolves to `/app/lib/fallow/app/__init__.py` (the `-P` fix) |
| Desktop entry | exported by Flatpak with `--file-forwarding` and `@@u %U @@`, i.e. a file manager can pass a document straight in |
| AppStream metadata | `appstreamcli validate` -> **clean**: no errors, no warnings |
| Screenshot URL | fetched over the network by `appstreamcli` and accepted at the published 2558x1396 |

Commands used, in case they need repeating:

```bash
# Flatpak
bash flatpak/build-flatpak.sh
flatpak install --user -y build/flatpak/org.fallow.PdfReader.flatpak
flatpak run --env=QT_QPA_PLATFORM=offscreen org.fallow.PdfReader /path/to/doc.pdf

# AppImage
bash appimage/build-appimage.sh
QT_QPA_PLATFORM=offscreen ./dist/Fallow-0.14.0-x86_64.AppImage /path/to/doc.pdf

# Validate the shared assets
desktop-file-validate packaging/org.fallow.PdfReader.desktop
appstreamcli validate --no-net packaging/org.fallow.PdfReader.metainfo.xml
```

---

## 7. Before publishing

The metadata is finished: `appstreamcli validate` passes with no errors and no
warnings, the screenshot and homepage URLs are live, and the `GPL-3.0-only`
declaration is backed by a `LICENSE` file at the repository root. What remains is
not metadata work.

1. **Optionally silence the last info note.** `appstreamcli` reports
   `developer-info-missing`; a `<developer id="github.com.moreno-omar">` element
   with the maintainer's name clears it. Informational only - Flathub accepts it.
2. **Decide on multi-arch.** The Flatpak module is generated for `x86_64` only.
   For `aarch64`, regenerate without `--wheel-arches` and build on that
   architecture.
3. **Submit to Flathub** if a public build is wanted: open a pull request against
   `flathub/flathub` containing the manifest, `python3-modules.json`, the
   desktop file, the metainfo, and the icons. Flathub builds from the manifest
   itself, so `lsetxattr-shim.c` and the build script are not part of it.

### The screenshot URL has to be the raw one

The metainfo points at
`https://raw.githubusercontent.com/moreno-omar/Fallow/main/fallow-screenshot.png`,
which is the "raw" form of the GitHub link. The obvious-looking *blob* URL

```
https://github.com/moreno-omar/Fallow/blob/main/fallow-screenshot.png
```

is **wrong**: it returns an HTML page (`content-type: text/html`) that a browser
happens to render as an image, so a software-centre listing shows nothing.
Always use `raw.githubusercontent.com` for any image URL in AppStream metadata.

## References

- Flatpak Builder manifests: <https://docs.flatpak.org/en/latest/flatpak-builder-command-reference.html>
- PySide6 BaseApp (README documents the BaseApp variables used here): <https://github.com/flathub/io.qt.PySide.BaseApp>
- flatpak#6818, the `lsetxattr(security.selinux)` regression: <https://github.com/flatpak/flatpak/issues/6818>
- `flatpak-pip-generator`: <https://github.com/flatpak/flatpak-builder-tools/tree/master/pip>
- python-build-standalone releases: <https://github.com/astral-sh/python-build-standalone/releases>
- appimagetool: <https://github.com/AppImage/appimagetool>
