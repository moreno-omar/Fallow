# 2026-09-27 — Flatpak and AppImage packaging

Phase 14 of `ROADMAP.md` ("Flatpak and AppImage"). Two installable artifacts, the
scripts that build them, and `flatpak_appimage_build.md` as the runbook.

---

## 15:10 — Made the application safe to package

**Objective.** A packaged build has no `alices-adventures-in-wonderland.pdf` or
`frankenstein.pdf` next to the source (`*.pdf` is in `.gitignore`), and
`MainWindow` opened both unconditionally on a first launch. Opening a
nonexistent path raises inside `pymupdf.open`, so the very first launch of a
package would have aborted. A file manager also passes documents as command-line
arguments, which `app/main.py` ignored even though `SPEC.md` lists the behaviour.

**Solution.**
- `app/ui/main_window/documents.py`: added `add_sample_documents()`, which opens
  each sample only when it exists and otherwise leaves the window empty.
- `app/ui/main_window/window.py`: `MainWindow(documents=())` — documents named on
  the command line win over the session, the session wins over the samples.
- `app/main.py`: added `document_arguments()`, which keeps existing `.pdf`
  arguments and ignores everything else instead of failing.

**Actions Performed.**
1. Added `add_sample_documents` to the documents layer and called it from the
   `MainWindow` fallback branch.
2. Replaced the hardcoded `add_pdf(... / "alices-adventures-in-wonderland.pdf")`
   pair with the guarded helper.
3. Read the arguments from `QCoreApplication.arguments()[1:]` so Qt's own options
   never reach `document_arguments`.
4. Ran a throwaway check covering all three launch paths.

**Verification Output.**

```
document_arguments: OK
sample fallback: ['Alice', 'Frankenstein']
command-line document: ['Frankenstein']
installed tabs: 0
page status: ''
EMPTY-WINDOW OK
ALL OK
```

The last case copies `app/` to a tree with no PDFs beside it, so it exercises the
packaged first-launch path.

**References Used.**
1. https://doc.qt.io/qt-6/qcoreapplication.html#arguments
2. https://pymupdf.readthedocs.io/en/latest/the-basics.html#opening-a-document
3. https://specifications.freedesktop.org/desktop-entry-spec/latest/exec-variables.html

**Optional steps.** Add a `--version`/`--help` path to `app/main.py`; the
packaged launchers would then be able to report what they contain.

**Possible problems.** `types` are not validated beyond the file extension, so a
well-named non-PDF argument still reaches `pymupdf.open` and would raise there.

---

## 15:20 — Built the Flatpak, working around flatpak#6818

**Objective.** Produce an installable Flatpak. `flatpak-pip-generator` refuses to
generate a PySide6 module and points at `io.qt.PySide.BaseApp`, so the manifest
is built on that base application with PyMuPDF as its only generated module.

**Solution.**
- `flatpak/org.fallow.PdfReader.yml`: `org.kde.Platform//6.11` +
  `io.qt.PySide.BaseApp//6.11`, `BASEAPP_REMOVE_WEBENGINE=1`, PyMuPDF module,
  application module installing `/app/lib/fallow/app` and `/app/bin/fallow`.
- `flatpak/fallow-launcher.sh`, `flatpak/python3-modules.json`,
  `flatpak/build-flatpak.sh`, `flatpak/lsetxattr-shim.c`.
- `packaging/`: shared desktop entry, AppStream metainfo, and icons.

**Actions Performed.**
1. Added flathub as a **user** remote and installed `org.kde.Platform//6.11`,
   `org.kde.Sdk//6.11`, `io.qt.PySide.BaseApp//6.11` for the user, so no root
   password is needed.
2. Generated the PyMuPDF module with `flatpak-pip-generator`, using
   `--runtime=org.kde.Sdk//6.11` (only the SDK ships `pip3`, which the generator
   shells out to) and `--prefer-wheels pymupdf` (otherwise it picks the sdist and
   flatpak-builder would compile MuPDF from source).
3. `flatpak build-init --base=...` failed with
   `error: lsetxattr(security.selinux): Operation not supported` on every target
   path. Reproduced it with a one-line `flatpak build-init`, then found
   flatpak#6818: a regression after 1.17.6 that Fedora 44 ships (flatpak 1.18.2
   with ostree 2026.4) and that is fixed in 1.18.3. No fixed package exists in
   the Fedora 44 repositories, and installing one would need root.
4. Wrote `flatpak/lsetxattr-shim.c` (LD_PRELOAD) and taught the build script to
   detect the regression by running the failing command once and matching its
   message, so a healthy host never uses the shim.
5. First successful build failed only at the last step
   (`Refspec 'app/org.fallow.PdfReader/x86_64/stable' not found`) because
   flatpak-builder defaults to the `master` branch; added
   `--default-branch=stable`.
6. Verified the installed app, including from inside the source checkout, where
   `flatpak run` inherited the working directory and Python imported the
   *checkout's* `app` package instead of the installed one. Added `-P` to the
   launcher so the working directory can never be on `sys.path`.

**Verification Output.**

```
==> 2/4  Checking for the flatpak/ostree xattr regression (flatpak#6818)
    Host is affected: flatpak < 1.18.3 on a SELinux-enabled kernel.
Built: /home/redram/python/Fallow/build/flatpak/org.fallow.PdfReader.flatpak (86M)

pymupdf PyMuPDF 1.28.2: Python bindings for the MuPDF 1.28.2 library.
numpy 2.3.5
PySide6 6.11.2

running from: /app/lib/fallow/app/__init__.py
tabs: 0 | page status: ''
EMPTY-WINDOW OK
tabs: 1 ['Frankenstein']
pages: 277 | status: of 277
after next_page: 1
DOCUMENT OK
resolved to: /app/lib/fallow/app/__init__.py   # launched from the checkout
exit=124 (the real 'fallow' entrypoint stayed open, no crash)
```

The exported desktop entry carries
`Exec=/usr/bin/flatpak run --branch=stable --arch=x86_64 --command=fallow --file-forwarding org.fallow.PdfReader @@u %U @@`,
so a file manager can hand a document to the app.

**References Used.**
1. https://github.com/flatpak/flatpak/issues/6818
2. https://github.com/flathub/io.qt.PySide.BaseApp
3. https://docs.flatpak.org/en/latest/flatpak-builder-command-reference.html

**Optional steps.** Drop `flatpak/lsetxattr-shim.c` and the detection step once
the distribution ships flatpak/ostree 1.18.3 or newer; add `x-checker-data`-based
automation or Flathub CI to rebuild on dependency updates.

**Possible problems.** The shim is compiled against a bug that is fixed
upstream, so it should be deleted rather than kept forever. The module is
generated for `x86_64` only. Flathub will reject the submission until the
repository has a `LICENSE` file and the metainfo carries a homepage URL and a
screenshot.

---

## 15:28 — Built the AppImage

**Objective.** One self-contained executable file, with no Flatpak and no system
Python needed.

**Solution.**
- `appimage/build-appimage.sh`: unpacks a pinned python-build-standalone CPython,
  pip-installs into it, copies `app/` and the shared `packaging/` assets, and
  runs `appimagetool`.
- `appimage/AppRun`: sets `PYTHONPATH`, runs `python3 -P -m app.main`.
- `appimage/requirements-appimage.txt`: mirrors `requirements.txt` but with
  `PySide6-Essentials` instead of `PySide6`, because the reader imports only
  `QtCore`, `QtGui`, and `QtWidgets` and the Addons package would add roughly
  250 MB of unused Qt modules.

**Actions Performed.**
1. Pinned `python-build-standalone` 20260924 / CPython 3.13.15 and downloaded the
   `install_only_stripped` tarball into `build/appimage/cache/`.
2. Unpacked it to `AppDir/usr/python`, pip-installed the three runtime
   dependencies, and copied the application and assets into the AppDir.
3. Added `.DirIcon`, removed every `__pycache__`, and squashed the AppDir with
   `appimagetool`.
4. Verified by running the image headless and by extracting it and probing the
   bundled interpreter directly.

**Verification Output.**

```
Built: /home/redram/python/Fallow/dist/Fallow-0.14.0-x86_64.AppImage (135M)

pymupdf ('1.28.2', '1.28.2', None)
numpy 2.2.6
PySide6 6.11.2

running from: .../squashfs-root/usr/share/fallow/app/__init__.py
tabs: 0 | page status: ''
EMPTY-WINDOW OK
tabs: 1 ['Frankenstein']
pages: 277 | status: of 277
after next_page: 1 | status: of 277
zoom: 1.15
sidebar visible: True
DOCUMENT OK
```

A first launch in a clean profile wrote `"tabs": []` to `session.json` and
stayed open with no traceback; a launch with a PDF argument recorded the
document in `session.json`.

**References Used.**
1. https://github.com/astral-sh/python-build-standalone/releases
2. https://docs.appimage.org/packaging-guide/manual.html
3. https://doc.python.org/3/using/cmdline.html#cmdoption-P

**Optional steps.** Add `--appimage-updateinfo` so the image can update itself
with AppImageUpdate; provide arm64 images by changing the pinned tarball to the
`aarch64` asset.

**Possible problems.** `requirements-appimage.txt` duplicates the pins of
`requirements.txt` and can drift from it; the image also relies on the host for
`libGL`, `libxkbcommon-x11`, and the X11/Wayland client libraries, so it is not
as isolated as the Flatpak.

---

## 15:42 — Prepared the AppStream screenshot

**Objective.** `fallow-screenshot.png` was added to the repository and the
metadata should use it, so that the packaging work is complete as far as it can
be without a public repository URL. Also confirm whether the deferred homepage
URL blocks anything today.

**Solution.**
- The image argument of an AppStream `<image>` element must be a **web URL**. A
  relative path to a file next to the metadata is a hard validation error
  (`E: web-url-expected`), which was confirmed against a throwaway metainfo
  before changing anything. The screenshot therefore cannot be shipped inside a
  package and is not installed by either build.
- `packaging/fallow-screenshot.png`: the capture is 2558x1396 (1.83:1) and
  AppStream asks for 16:9 or 4:3 at 624x351 to 1600x900, so 38px were cropped
  from each side to reach exactly 16:9 and the result scaled to 1600x900.
- `packaging/org.fallow.PdfReader.metainfo.xml`: added one commented-out block
  holding both deferred items - `<url type="homepage">` and the `<screenshots>`
  entry - with the placeholders to replace. Commented rather than present so
  validation stays clean and no broken URL is published.

**Actions Performed.**
1. Validated a throwaway metainfo with a relative `<image>` to establish that a
   web URL is required, not merely recommended.
2. Cropped and scaled the screenshot with ImageMagick into `packaging/`.
3. Added the commented placeholder block to the metainfo and re-validated.
4. Rebuilt and reinstalled the Flatpak so the shipped metadata matches the
   repository, then re-ran the clean-profile launch check.

**Verification Output.**

```
# before the placeholder block was added
E: org.fallow.PdfReader:15: web-url-expected shot.png

# after
W: org.fallow.PdfReader:~: url-homepage-missing
I: org.fallow.PdfReader:~: developer-info-missing
✘ Validation failed: warnings: 1, infos: 1, pedantic: 1     # no errors

packaging/fallow-screenshot.png: PNG image data, 1600 x 900
Host is affected: flatpak < 1.18.3 on a SELinux-enabled kernel.
Built: build/flatpak/org.fallow.PdfReader.flatpak (86M)
exit=124 (clean-profile launch stayed open, no crash)
{"active_tab_index": 0, "dark_mode": true, "tabs": []}
```

**References Used.**
1. https://opensource.org/license/gpl-3-0
2. https://spdx.org/licenses/GPL-3.0-or-later.html
3. https://www.freedesktop.org/software/appstream/docs/

**Optional steps.** Add `<developer id="org.fallow">` to clear the remaining
`developer-info-missing` info note; keep a second screenshot showing tabs and the
marks list once the first one is published, so the listing shows more than one.

**Possible problems.** GPL-3.0 is declared in the metadata while the repository
still has no `LICENSE` file, so the declaration is currently an intention rather
than a fact - Flathub checks the two agree. The homepage warning stays until the
repository is public, and the screenshot stays unusable until it is committed and
reachable over HTTPS.

---

## 15:52 — Finalized the AppStream metadata

**Objective.** Replace the deferred placeholders with the real values: the
homepage URL, the screenshot, and the exact license. The repository is public at
`https://github.com/moreno-omar/Fallow`, which unblocks all three.

**Solution.**
- `<project_license>` is now `GPL-3.0-only`, the SPDX spelling of plain GPL-3.0.
  The bare `GPL-3.0` id still validates but is deprecated in SPDX, and
  `GPL-3.0-or-later` would have granted a right the maintainer did not ask for.
- Added `<url type="homepage">` and the `<screenshots>` block, and deleted the
  commented placeholder block they replace.
- The screenshot URL is the **raw** form, not the blob form that was suggested:
  `github.com/.../blob/...` returns `content-type: text/html` (an HTML page a
  browser renders as an image), which would leave a software-centre listing
  blank. `raw.githubusercontent.com/...` returns the file.
- Dropped `packaging/fallow-screenshot.png`, the 1600x900 copy prepared earlier.
  It was never committed, the published 2558x1396 capture is accepted, and two
  copies would only drift.

**Actions Performed.**
1. Checked the content types of the repository page, the blob URL, and both raw
   URLs with `curl -o /dev/null -w '%{http_code} %{content_type}'`. The root raw
   URL returned `200 image/png` (the file is already published); the
   `packaging/` raw URL returned `404` (never committed).
2. Tested `GPL-3.0`, `GPL-3.0-only`, and `GPL-3.0-or-later` against
   `appstreamcli validate`; all three are accepted.
3. Validated a candidate metainfo **with** network access, so `appstreamcli`
   fetched the screenshot and inspected it at 2558x1396 - accepted, confirming
   the 16:9/1600x900 figures are guidance rather than enforced limits.
4. Edited the metainfo, removed the redundant screenshot copy, and validated the
   final file.
5. Rebuilt and reinstalled the Flatpak so the shipped metadata matches, then
   re-ran the clean-profile launch check.

**Verification Output.**

```
repo page        -> 200 text/html; charset=utf-8
blob URL (given) -> 200 text/html; charset=utf-8     # not an image
raw (root)       -> 200 image/png                    # the one to use

# final metainfo, validated with network
I: org.fallow.PdfReader:~: developer-info-missing
✔ Validation was successful: infos: 1, pedantic: 1     # no errors, no warnings

# installed inside the rebuilt Flatpak
<project_license>GPL-3.0-only</project_license>
<url type="homepage">https://github.com/moreno-omar/Fallow</url>
<image type="source">https://raw.githubusercontent.com/moreno-omar/Fallow/main/fallow-screenshot.png</image>
exit=124 (clean-profile launch stayed open, no crash)
```

**References Used.**
1. https://spdx.org/licenses/GPL-3.0-only.html
2. https://www.freedesktop.org/software/appstream/docs/
3. https://opensource.org/license/gpl-3-0

**Optional steps.** Add `.gitignore` entries are already in place; adding a
second screenshot (tabs and the marks list) would show more in the listing, and
`<developer id="github.com.moreno-omar">` would clear the last info note.

**Possible problems.** The license declaration still has no `LICENSE` file behind
it, which is now the only thing standing between the repository and a Flathub
submission. Deleting the tracked screenshot, moving it, or renaming the default
branch away from `main` breaks the metadata URL with no build-time warning -
`appstreamcli` only notices when it can reach the network.

---

## 15:58 — Added the LICENSE file, updated the README, settled .gitignore

**Objective.** Back the `GPL-3.0-only` declaration with a real license file,
update the README now that the repository is public and the packages exist, and
settle which packaging files belong in version control.

**Solution.**
- `LICENSE`: the official GPL-3.0 text, downloaded from `gnu.org` rather than
  transcribed, so the wording is exact. 674 lines / 35149 bytes.
- `README.md`: the screenshot at the top, an **Install** section covering both
  packages, the real clone URL in place of the `your-username/repo-name`
  placeholder, and a **License** section.
- `.gitignore`: the build outputs were already excluded; added
  `flatpak/*.so`, `flatpak/*.flatpak`, and `appimage/*.AppImage` for artifacts
  that can land next to the sources instead of in `build/`.
- `flatpak/` and `appimage/` stay tracked. They hold sources - the manifest, the
  generated module, the launcher, the shim, and the build scripts - and ignoring
  them would leave a clone with no way to build either package. Everything they
  *produce* lands in `build/` or `dist/`, which are ignored.

**Actions Performed.**
1. `curl -fsSL https://www.gnu.org/licenses/gpl-3.0.txt -o LICENSE`, then
   verified the header, the version line, the byte count, and the sha256.
2. Edited the README in four places and trimmed a stray trailing space in the
   title.
3. Audited the ignore rules with `git check-ignore -v` and listed what a clone
   would lose if the two source folders were ignored, which is what settled the
   question.
4. Replaced the two places that still said the repository had no LICENSE file,
   then rebuilt and reinstalled the Flatpak so the installed metadata matches the
   repository.

**Verification Output.**

```
$ head -4 LICENSE
                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>

$ wc -c -l LICENSE
  674 35149 LICENSE
3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986  LICENSE

$ git check-ignore -v build/appimage/cache dist/Fallow-0.14.0-x86_64.AppImage flatpak/lsetxattr-shim.so
.gitignore:7:build/     build/appimage/cache
.gitignore:8:dist/      dist/Fallow-0.14.0-x86_64.AppImage
.gitignore:13:flatpak/*.so      flatpak/lsetxattr-shim.so
```

The GPL text matches the published copy byte for byte; only build output is
ignored; `LICENSE`, `flatpak/`, `appimage/`, `packaging/`, and
`flatpak_appimage_build.md` all remain visible to git.

**References Used.**
1. https://www.gnu.org/licenses/gpl-3.0.txt
2. https://www.gnu.org/licenses/gpl-howto.html
3. https://git-scm.com/docs/gitignore

**Optional steps.** Nothing was staged or committed, so the work is still a set
of unstaged changes; the README's feature list and its `Save Session file`
section still predate the sidebar, bookmarks, notes, and `library.db` of
Phases 12-13.

**Possible problems.** `fallow-screenshot.png` must stay tracked: the metainfo
points at its published URL, so deleting it or changing the default branch breaks
the listing with no build-time warning. A `LICENSE` file does not retroactively
apply to anything published before it.

---

## 16:05 — Brought the README up to date

**Objective.** The README predated Phases 9-13: its feature list stopped at
keyboard navigation and it documented only `session.json`, while the app had
grown a command palette, find, bookmarks, notes, a sidebar, and a SQLite library.
It also had to answer whether build instructions belong in it.

**Solution.**
- Rewrote the feature list to match what ships, and added a keyboard shortcut
  table, because the application is shortcut-driven and the shortcuts were only
  discoverable from the menus.
- Replaced the `Save Session file` section with `Where your data lives`, covering
  `session.json`, the `QSettings` file, `library.db`, and the notes directory,
  and recording two behaviours worth knowing: deleted files are pruned from the
  session, and bookmarks and notes follow a document's contents rather than its
  path.
- Build instructions stay short in the README: the two commands, one sentence on
  the two tools they need, and a link to `flatpak_appimage_build.md`. That file
  carries the flags, the runtime prerequisites, and the host bug workaround,
  which is too much detail for a README whose job is to get a reader started.
- Added Markdown rendering of notes to the roadmap, since notes are plain text
  today and that is Phase 15.

**Actions Performed.**
1. Read `commands.py` for the authoritative shortcut list rather than trusting
   the notes, and confirmed the sidebar's tab names in `sidebar.py`
   (`Bookmarks` for the outline and marks pane, `Notes`).
2. Read `bookmarks_panel.py` (the outline sits above the marks in one splitter)
   and `database.py: default_data_root` for the exact XDG paths.
3. Checked the Tab Search claim against `command_palette.Command`, which holds
   only `title` and `shortcut`. `tab_commands` passes the tab title and the
   `page N of M` hint, so the palette does **not** search the file path - the
   first draft of the feature list said it did, and was corrected. The path is a
   tooltip on the tab and on each overflow-menu row instead.
4. Re-read the finished README end to end against the code.

**Verification Output.**

```
app/ui/sidebar.py:42:  self.insertTab(self.BOOKMARKS_INDEX, self.bookmarks_panel, "Bookmarks")
app/ui/sidebar.py:43:  self.insertTab(self.NOTES_INDEX, self.notes_panel, "Notes")
app/ui/bookmarks_panel.py:82: splitter.addWidget(self.build_section("Contents", self.outline_view))
app/ui/bookmarks_panel.py:83: splitter.addWidget(self.build_section("Bookmarks", self.marks_list))
app/core/database.py:100: def default_data_root() -> Path:
app/ui/main_window/commands.py:32: DARK_MODE_SHORTCUTS = ("Ctrl+Shift+D", "Alt+D", "Ctrl+D")

# the correction, after checking Command's fields
- **Tabbed viewing:** ... `Ctrl+Shift+A` searches the open documents by title.
```

Every documented shortcut, tab name, and path was read from the source rather
than restated from the phase notes.

**References Used.**
1. https://specifications.freedesktop.org/basedir-spec/latest/
2. https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes
3. https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax

**Optional steps.** The README could carry a second screenshot of the sidebar
once the first is proven in the listing, and a badge row (license, latest
release) once releases exist.

**Possible problems.** The README documents behaviour rather than enforcing it,
so it can drift again as Phases 15+ land; the shortcut table in particular
duplicates `commands.py`, and nothing checks the two agree.




