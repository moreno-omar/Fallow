# Fallow 

A lightweight, distraction-free Linux PDF reader, that saves reading session, built with Python and PySide6.


## Features
- **Tabbed Viewing:** Open multiple documents simultaneously.
- **Single-Page View:** Focus on one page at a time with fit-to-page magnification.
- **Dark Mode:** Toggles UI chrome and inverts PDF rendering for night reading.
- **Session Restore:** Remembers open tabs and exact page positions across restarts.
- **Keyboard & Mouse Navigation:** Discrete page turning via arrow keys and scroll wheel.

## Non-Goals
- PDF editing, annotating, or form-filling.
- Cross-platform support (Linux only).
- Continuous multi-page scrolling.

## Requirements
- Linux (X11 or Wayland)
- Python >= 3.10

## Quickstart

```bash
git clone [https://github.com/your-username/repo-name.git](https://github.com/your-username/repo-name.git)
cd repo-name
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Future Roadmap
- Support for EPUB and comic formats (CBZ/CBR).
- Dual-page spread mode.
- Configurable hotkeys.
- Better UI
