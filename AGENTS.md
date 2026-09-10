# AGENTS.md - Developer Guidelines & Environment Rules

## Environment & Tech Stack
- **OS:** Linux (Bash shell)
- **Language:** Python 3.10+
- **Virtual Environment:** Always use the local `.venv` directory (activate via `source .venv/bin/activate`).
- **Dependencies:** Install packages strictly via `pip` and update `requirements.txt` when necessary.
- **databases:** if for single user app, sqlite. Anything else, postgresql.

## Testing & Validation Rules
- **Skip Testing by default:**  Do not write test files or run unit tests. Can write tests when refactoring or make a replacing tools. Like postgresql for sqlite, python pymupdf for pdfplumber.
- **Manual Verification:** Rely strictly on direct script execution, CLI output checks, or dry-run validation logs to confirm code functionality.

## Python Execution Rules
- Always use the local virtual environment interpreter directly (.venv/bin/python on Linux/macOS or .venv\Scripts\python.exe on Windows) instead of running `source .venv/bin/activate`.
- Do not chain commands using `&&` for environment activation. Execute python/pip/manage.py commands using the direct path.

## Coding Style & Guardrails
- Write clean, modular, production-grade Python code with clear docstrings and type hints.
- functions should be independent and do one job only (mostly).
- Keep modifications scoped strictly to the requested feature or bug fix.
- Do not introduce external dependencies or databases unless explicitly authorized in the architecture specification.
- Never execute destructive git commands or commit changes automatically.
- Keep frontend minimal. HTMX. alpine.js to show loading or progress. dark mode. Prefer css over javascript in regards to web design.
- Create or update SUMMARY.md. Goal: for user too understand how it works and be able to create a simpler functional version on own. Give Summary of important steps taken and why. Provide timestamp.
- when you complete a task from `@TASKS.md`, mark it there as complete.

## Important reading 
- Read `@SPEC.md`, and `@ROADMAP.md`. Implement **Phase number** of the roadmap. Check `@TASKS.md` for the current sub-tasks to execute.
