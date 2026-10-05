# Goal
- to have features allow one to focus on reading and delegates most of the other chores.

## improve ui
- have to do more research to know what specifically to improve

## Features

### Bookmarks
- at least create 1 per ebook
- can expand to multiple bookmarks
    - include meta data : name, page_number

### Recents
- a list of ebooks opened that have been closed
- limit to 10

### tabs
- shorten to 20 characters?
- allow to rename?

#### overflow
- only keep the first 5.
- make list for others.

### other views
- continuous
    - also add option to snap
- double

### shortcuts

#### darkmode
- alt+Q ? / Ctrl+Shift / D

#### others
- Ctrl+F for find
- Ctrl+G for goto page
- Ctrl+W for close tab
## Notes

### render markdown in the app
- goal (a later phase): a note should read as Markdown instead of raw syntax, without giving up the
  plain text that is the source of truth.
- where it stands after Phase 13: the editor is a `QPlainTextEdit` and each note's body is a
  Markdown file at `<data_root>/notes/<book-hash>/note-<uuid>.md`, with metadata in `library.db`.
  Rendering is therefore purely a *view* concern — no storage change is needed.
- feedback to weigh when that phase is planned:
    - **Keep the file as the source of truth.** Render into a separate view, or highlight in place;
      never write a re-serialised document back. `QTextDocument.toMarkdown()` normalises whitespace
      and list markers, so saving after a round-trip would slowly rewrite the reader's own file.
    - **"Minimal highlighting" fits `QSyntaxHighlighter` best.** Attaching one to the existing
      `QPlainTextEdit` leaves editing, the 700 ms autosave, the cursor, and the scroll position
      alone; only headings, emphasis, code and quotes get a colour. No new dependency, and no second
      widget to keep in step.
    - **A rendered preview needs a toggle, not a replacement.** `QTextEdit`/`QTextBrowser` with
      `setMarkdown()` gives true rendering (`QTextDocument.setMarkdown` exists since Qt 5.14), but it
      is read-only in practice: swapping it in for the editor would cost the plain-text editing that
      the Markdown file exists for. An edit ⇄ preview toggle keeps both.
    - **Re-rendering on every keystroke fights the typist.** Reuse the autosave pattern (its own
      single-shot timer) rather than re-parsing inside `textChanged`, and make sure a preview refresh
      cannot mark the editor dirty or restart the save timer.
    - **Dark mode is a real trap here.** A `QTextBrowser`/`QTextDocument` brings its own palette, and
      it has to be set from the active theme the way the sidebar and the command palette already are,
      or rendered notes come out black-on-dark at night.
    - **The sidebar is a narrow home for a preview** (320–640px). The note-placement icon below is a
      better place for a rendered note than the sidebar column; consider a dialog and keep the
      sidebar for the list and the editor.
    - **One parser, two consumers.** Tag parsing (`#tag`, front-matter `tags:`) and any renderer must
      agree on what counts as inside a fenced code block. Put the scan in a single
      `app/core/markdown.py` and let the highlighter and the tag scanner both use it.
    - **Export is nearly free.** The notes already *are* Markdown files; what is missing is an action,
      not a format — open the folder (`QDesktopServices.openUrl`), copy to a chosen folder, or write a
      zip. Worth doing in the same phase, because a renderer otherwise tempts an "export to HTML/PDF"
      that nobody asked for.
    - **Long notes:** `highlightBlock` runs per block, so keep the patterns simple and per-block
      instead of reparsing the whole document to colour one line.

### in markdown
- should be able to export in markdown

### presentation
- notes should have minimal highlighting of markdown
  (see `render markdown in the app` above for the approach that fits the current editor)

### note placement icon
- simple icon
- shows dialog that displays note

### notes
- have option to have them all visible (expanded) when toggled.

## highlights

## Context or Command Palette
- think like vim or web design w/o buttons

### Normal mode
- keys mapped to function
- example
    - "d" for dark mode toggle

### Input mode
- keys to type

## Notes export
- to allow notes to be taken out of app

## right-click
- use a context dependent -> always shows subset of actions
