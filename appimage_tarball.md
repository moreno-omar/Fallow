# AppImage and tarball packaging — review

## Goal

Ship files that a reader can install straight after downloading, without cloning
the repository and without running a build script:

- a tarball that installs a normal desktop app (menu entry, icon, `fallow`
  command) on Linux;
- an AppImage that runs as a single executable, no installation;
- both published on GitHub Releases, one version per tag, so a reader can pick
  the release they want.

## What already existed

- `appimage/build-appimage.sh` staged a standalone CPython plus the wheels into
  an AppDir and squashed it with `appimagetool`.
- `flatpak/build-flatpak.sh` built the Flatpak.
- `.github/workflows/release.yml` published both on a `v*` tag.

So the AppImage already satisfied "download and run", and releases already
existed. Two gaps remained: there was **no tarball at all**, and the only
downloadable installer was the Flatpak.

## What was missing, concretely

1. No portable tarball, and therefore no install step that needs neither root nor
   Flatpak.
2. The AppDir staging logic lived inside the AppImage script, so a second package
   would either duplicate the pinned interpreter versions and the pip step or
   rebuild them.
3. Nothing let a downloader verify what they got.

## What now exists

| Path | Role |
|---|---|
| `packaging/stage-payload.sh` | shared staging: CPython, wheels, `app/`, `AppRun`, icons |
| `packaging/requirements-runtime.txt` | the runtime wheels, shared by both bundles |
| `appimage/build-appimage.sh` | stages the payload, squashes it with `appimagetool` |
| `tarball/build-tarball.sh` | stages or reuses the payload, adds the installer, packs `.tar.gz` |
| `tarball/install.sh` | user-local (`~/.local`) or `--prefix /usr/local` installer |
| `tarball/uninstall.sh` | removes an install, keeps the reader's data |
| `tarball/README.txt` | the instructions placed inside the archive |

The archive is self-contained:

```
Fallow-0.14.0-x86_64/
├── fallow -> AppRun          runs in place, no install needed
├── install.sh                copies into ~/.local, adds menu entry + icon
├── uninstall.sh
├── README.txt
├── AppRun
├── org.fallow.PdfReader.{desktop,png,svg}
└── usr/
    ├── python/               standalone CPython 3.13 + PySide6/PyMuPDF/numpy
    └── share/fallow/app/     the application
```

## Installing a download

Tarball — no root, no build tools:

```bash
tar -xzf Fallow-0.14.0-x86_64.tar.gz
cd Fallow-0.14.0-x86_64
./install.sh                    # or: sudo ./install.sh --prefix /usr/local
fallow document.pdf
```

`install.sh` only copies files: payload to `<prefix>/lib/fallow`, a `fallow`
symlink in `<prefix>/bin`, a desktop entry whose `Exec=` is the absolute launcher,
and both icons. `uninstall.sh` reverses exactly that and leaves
`~/.local/share/linux-pdf-reader` alone.

AppImage — nothing to install:

```bash
chmod +x Fallow-0.14.0-x86_64.AppImage
./Fallow-0.14.0-x86_64.AppImage document.pdf
```

## Building

```bash
bash tarball/build-tarball.sh      # standalone, needs curl + tar
bash appimage/build-appimage.sh    # needs appimagetool

# both from one staged payload, which is what CI does
bash appimage/build-appimage.sh
bash tarball/build-tarball.sh --payload build/appimage/Fallow.AppDir
```

## Releases

`.github/workflows/release.yml` runs on a `v*` tag:

1. `bundles` builds the AppImage, then the tarball from the same AppDir, and
   smoke-tests both (unpack, install into a throwaway prefix, import the app);
2. `flatpak` builds and smoke-tests the Flatpak;
3. `release` writes `SHA256SUMS` and attaches the AppImage, the tarball, the
   Flatpak and the checksums to the GitHub Release.

A reader downloads one file, verifies it with `sha256sum -c SHA256SUMS`, and
installs it.

## Verified locally (2026-11-12)

- `tarball/build-tarball.sh` produced `dist/Fallow-0.14.0-x86_64.tar.gz` (149 MB),
  both standalone and with `--payload`.
- `diff -r app <bundle>/usr/share/fallow/app` — the packaged code matches the
  checkout.
- `install.sh --prefix <tmp>` produced the launcher, absolute `Exec=`, both icons;
  `QT_QPA_PLATFORM=offscreen timeout 10 <prefix>/bin/fallow` stayed up (exit 124,
  no traceback), and the uninstalled-in-place `./fallow` did the same.
- `uninstall.sh` removed the launcher, entry, icons and payload; a second run
  reports "nothing to do".
- `appimage/build-appimage.sh` still produced a 135 MB AppImage after the staging
  refactor, and its extracted interpreter imported PySide6 6.11.2, PyMuPDF
  1.28.2, numpy 2.2.6.

## Remaining / optional

- The workflow has not run on GitHub since the tarball was added.
- Releases are still unsigned; checksums only prove the download is intact, not
  who built it.
- No `.zsync` for AppImage self-updates, and no `aarch64` packages.
- `install.sh` does not register Fallow as the default PDF handler; it only adds
  the menu entry (`xdg-mime default` would be a separate, more intrusive step).
