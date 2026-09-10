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
- **Goal:**
- **Exit Criteria:** 