# ROADMAP.md - Project Implementation Phases

## Phase 1: Create Window
- **Goal:** Pyside should be installed. Application should display visible window.
- **Exit Criteria:** User confirms it's visible

## Phase 2: Render PDF in PySide6 Window
- **Goal:** To have pyMuPDF display within Pyside
- **Exit Criteria:** : Alice in Wonderland pdf renders on Window

## Phase 3: Open Multiple PDF in Tabs
- **Goal:** More than 1 pdf can be opened on the same window
- **Exit Criteria:** User can view 2 pdfs open on the same window, each on their own tab.

## Phase 4: Save Session
- **Goal:** Saves into JSON the list of open files and the page they were last at
- **Exit Criteria:** After opening those 2 files, user can close the app, reopen it, and have the same files be opened.

## Phase 5: Has Preferred PDF settings
- **Goal:** : To open in Single Page View, Fit to Page Magnification, allow to turn pages with arrow keys or mouse wheel
- **Exit Criteria:** User able to turn pages.

## Phase 6: Dialog to Pick pdf file
- **Goal:** : create basic dialog to search for a pdf on the computer. 
- **Exit Criteria:**  User able to open a new tab with a pdf picked from the dialog. Hardcoded code neede to open pdf not needed in main.

## Phase 7: Add useful bottom bar 
- **Goal:** : In center, provide field to type in page number, to the right of that, display current page and total pages. Example: "83 of 680". Use QToolBar.
- **Exit Criteria:** User able to view current page number, total number of pages, and able to type what page to navigate to.

## Phase 8: Dark Mode
- **Goal:** To enable option to toggle on. To have a dark mode pallete that still renders colored code snippets properly.
- process the pixmap buffer using an HSL/HSV luminance transformation
- Color Palette Nord / Slate Dark
    - Background: Deep gray-blue (#2E3440 or #1E1E2E)
    - Default Text: Off-white / Ice (#ECEFF4)
- **Exit Criteria:** User can open pdf with color code snippets, shows up properly.

## Phase 9: Useful keyboard shortcuts:
- **Goal** : Using establish the following shortcuts
    - `Ctrl+Shift+D` and `Alt-D` as Dark mode toggle
    - `Ctrl+F` for find
    - `Ctrl+G` for go to page
    - `Ctrl+W` for close tab
    - `Ctrl+B` to bookmark page. Use `Document.make_bookmark()`. Only create scaffold for now.
    - `Ctrl+Mouse wheel` to zoom in/out. Use `pymupdf.Matrix`

- **Exit Criteria** : User confirms all shortcuts can be used.

## Phase 10: Create Command Palette
- **Goal** : Using pyside to catch keyboard shortcut, to activate needed functions (like PyMupdf), to have shortcuts and functions achieved by search
    - create command palette in PySide6 as a QDialog
    - create shortcut for it using `Ctrl-P`
    - all keyboard shortcuts achievable with command palette
- **Exit Criteria** : all keyboard shoctus can be performed with command palette

## Phase 11: Tabs
- **Goal** - limit to 20 characters. create overflow list. Only allow first 5 to be visible.

## Phase 12 : Bookmarks
- **Goal** - save as JSON store keyed by the document's file path or SHA-256 hash. Create panel using 
a QDockWidget docked to Qt.LeftDockWidgetArea. Inside this dock, use a QTabWidget containing:
    - Contents (Outline): A `QTreeView` displaying the document's hierarchical ToC (`doc.get_toc()`). 
    - `QListWidget` or `QListView` displaying the user's custom reading marks.

```text
+-------------------+------------------------------------------+
| Dock Panel (Left) | Main Document View Area                  |
| [Outline] [Marks] |                                          |
|-------------------|                                          |
| • Page 12 - Intro |                 [Page 42]                |
| • Page 42 - Notes |                                          |
|                   |                                          |
+-------------------+------------------------------------------+
```