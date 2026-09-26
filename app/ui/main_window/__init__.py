"""The application window, split into one mixin per feature area.

``MainWindow`` is assembled from a stack of small mixins because the single-class
version mixed six unrelated concerns (theme, find, bookmarks, page navigation,
document tabs, menus/shortcuts). Import :class:`MainWindow` from here:

    from app.ui.main_window import MainWindow
"""

from app.ui.main_window.window import MainWindow

__all__ = ["MainWindow"]
