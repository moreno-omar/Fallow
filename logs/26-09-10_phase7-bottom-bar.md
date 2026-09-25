# Phase 7 — Useful Bottom Bar

**Completed:** 2026-09-10 · **Index:** [`SUMMARY.md`](../SUMMARY.md)

- Added a non-movable bottom `QToolBar` with expanding spacers that keep its page controls centered.
- Added a validated page-number field and a `current of total` status label for the active PDF tab.
- Added page-change signaling from each viewer so arrow keys, wheel navigation, tab switching, and direct page entry keep the controls synchronized.
- Page entry uses one-based display numbers while the viewer continues to store zero-based page indexes. Possible improvements include a visible Go button, focus-friendly page validation feedback, and previous/next toolbar buttons.
