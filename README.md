# Fallow

A lightweight, distraction-free Linux PDF reader that saves your reading session, built with Python and PySide6.

![Fallow showing a document with the command palette open](https://raw.githubusercontent.com/moreno-omar/Fallow/main/fallow-screenshot.png)

## Features
- **Tabbed viewing:** Open multiple documents at once. The tab strip keeps five
  visible and moves the rest into an overflow menu, and `Ctrl+Shift+A` searches
  the open documents by title. Each tab's tooltip carries the full file path, so
  two similarly named documents stay apart.
- **Single-page view:** One page at a time, scaled to fit the window while
  keeping the aspect ratio. Magnify with `Ctrl` and the mouse wheel.
- **Dark mode:** Applies a Nord-style palette to the window *and* inverts the
  rendered page, so a white PDF does not glare in a dark room.
- **Session restore:** Reopens the tabs you had and returns each one to the page
  you left it on, along with the theme you were using.
- **Page navigation:** Arrow keys, `Page Up`/`Page Down`, and the mouse wheel turn
  exactly one page at a time, with no overshoot at either end.
- **Find in document:** `Ctrl+F` highlights every match on the page and steps
  through the document, wrapping at the end.
- **Bookmarks and notes:** `Ctrl+B` marks the current page. The sidebar shows the
  document's own outline above your marks, and a Notes tab keeps per-document
  notes that autosave as Markdown files.
- **Command palette:** `Ctrl+P` reaches every command by search, so no shortcut
  has to be memorised.
- **Entirely offline:** The reader opens only the files you hand it and writes
  only its own session, library, and notes.

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Ctrl+O` | Open a PDF |
| `Ctrl+W` | Close the current tab |
| `Ctrl+Q` | Quit |
| `Ctrl+F` | Find in the document (`Enter` for the next match, `Esc` to close) |
| `Ctrl+G` | Go to a page number |
| `Ctrl+B` | Bookmark the current page |
| `Ctrl+P` | Command palette |
| `Ctrl+Shift+A` | Search the open tabs |
| `Ctrl+Shift+E` or `F9` | Show or hide the side panel |
| `Ctrl+Shift+D`, `Alt+D`, or `Ctrl+D` | Toggle dark mode |
| `Ctrl` + mouse wheel, `Ctrl++`, `Ctrl+-`, `Ctrl+0` | Zoom in, out, and reset to fit |
| `Left`/`Right`, `Up`/`Down`, `Page Up`/`Page Down`, wheel | Previous or next page |
| `Delete` | Remove the selected bookmark (in the sidebar) |

## Non-Goals
- PDF editing, annotating, or form-filling.
- Cross-platform support (Linux only).
- Continuous multi-page scrolling.

## Requirements
- Linux (X11 or Wayland)
- Python >= 3.10 when running from source

## Install

Two self-contained packages are built from this repository. Neither needs Python
or a source checkout on the machine that installs it:

```bash
bash flatpak/build-flatpak.sh      # -> build/flatpak/org.fallow.PdfReader.flatpak
bash appimage/build-appimage.sh    # -> dist/Fallow-0.14.0-x86_64.AppImage
```

The scripts install or download everything they need. Building the Flatpak wants
`flatpak-builder` and the flathub remote (plus, on Fedora 44 specifically, a
workaround for a Flatpak bug the script applies on its own); building the
AppImage wants `appimagetool`. Both sets of requirements, and the flags behind
every step, are in [`flatpak_appimage_build.md`](flatpak_appimage_build.md) -
this README only carries the commands.

The AppImage needs no installation at all:

```bash
chmod +x dist/Fallow-0.14.0-x86_64.AppImage
./dist/Fallow-0.14.0-x86_64.AppImage document.pdf
```

The Flatpak installs into the current user's Flatpak installation:

```bash
flatpak install --user -y build/flatpak/org.fallow.PdfReader.flatpak
flatpak run org.fallow.PdfReader document.pdf
```

Both accept document paths as arguments, and both start with an empty window the
first time - open something with `Ctrl+O` or pass it on the command line.

## Quickstart

Running from source:

```bash
git clone https://github.com/moreno-omar/Fallow.git
cd Fallow
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Where your data lives

Fallow follows the XDG Base Directory specification and keeps everything under
one folder per kind of data.

| What | Path |
|---|---|
| Open tabs, page positions, theme | `$XDG_CONFIG_HOME/linux-pdf-reader/session.json` |
| Sidebar layout and library location | `$XDG_CONFIG_HOME/linux-pdf-reader/Fallow PDF Reader.conf` |
| Bookmarks and note index | `$XDG_DATA_HOME/linux-pdf-reader/library.db` (SQLite) |
| Note bodies | `$XDG_DATA_HOME/linux-pdf-reader/notes/<document-hash>/*.md` |

Both variables fall back to `~/.config` and `~/.local/share`. A Flatpak keeps
these under `~/.var/app/org.fallow.PdfReader/` instead.

Deleted files are pruned from the session on the next launch. Bookmarks and notes
are keyed by the contents of the document, not its path, so renaming or moving a
file keeps them. If the data folder cannot be written, the reader says so in the
status bar and runs with a temporary library rather than refusing to start.

## Future Roadmap
- Markdown rendering and a preview pane for notes, which are plain text today.
- Support for EPUB and comic formats (CBZ/CBR).
- Dual-page spread mode.
- Configurable hotkeys.
- Better UI

## License

GPL-3.0-only - see [`LICENSE`](LICENSE).
