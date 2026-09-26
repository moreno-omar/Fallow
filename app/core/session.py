"""Persistent application session storage."""

import json
import os
from pathlib import Path
from typing import Any


class SessionManager:
    """Load and save validated PDF reader session state."""

    def __init__(self) -> None:
        config_home = os.environ.get("XDG_CONFIG_HOME")
        base_directory = Path(config_home).expanduser() if config_home else Path.home() / ".config"
        self.session_path = base_directory / "linux-pdf-reader" / "session.json"

    def load(self) -> dict[str, Any] | None:
        """Return a valid session, or ``None`` when no usable session exists."""
        try:
            with self.session_path.open(encoding="utf-8") as session_file:
                data = json.load(session_file)
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict):
            return None

        raw_tabs = data.get("tabs")
        if not isinstance(raw_tabs, list):
            return None

        tabs: list[dict[str, Any]] = []
        for raw_tab in raw_tabs:
            if not isinstance(raw_tab, dict):
                continue
            file_path = raw_tab.get("file_path")
            current_page = raw_tab.get("current_page")
            if (
                isinstance(file_path, str)
                and Path(file_path).is_file()
                and isinstance(current_page, int)
                and not isinstance(current_page, bool)
                and current_page >= 0
            ):
                tabs.append({"file_path": str(Path(file_path).resolve()), "current_page": current_page})

        active_tab_index = data.get("active_tab_index", 0)
        if not isinstance(active_tab_index, int) or isinstance(active_tab_index, bool):
            active_tab_index = 0
        active_tab_index = min(max(active_tab_index, 0), max(len(tabs) - 1, 0))

        dark_mode = data.get("dark_mode", True)
        if not isinstance(dark_mode, bool):
            dark_mode = False

        return {
            "active_tab_index": active_tab_index,
            "dark_mode": dark_mode,
            "tabs": tabs,
        }

    def save(self, active_tab_index: int, viewers: list[Any], dark_mode: bool = False) -> None:
        """Persist open viewers and their current pages to the XDG config path."""
        tabs = [
            {
                "file_path": str(viewer.engine.file_path.resolve()),
                "current_page": viewer.current_page,
            }
            for viewer in viewers
            if not viewer._disposed
        ]
        state = {
            "active_tab_index": min(max(active_tab_index, 0), max(len(tabs) - 1, 0)),
            "dark_mode": dark_mode,
            "tabs": tabs,
        }
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.session_path.with_suffix(".tmp")
        with temporary_path.open("w", encoding="utf-8") as session_file:
            json.dump(state, session_file, indent=2)
            session_file.write("\n")
        temporary_path.replace(self.session_path)