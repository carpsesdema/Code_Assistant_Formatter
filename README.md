# Code Helper

A desktop tool I built to clean up and refactor Python projects.

It scans your repo, lets you search and replace across all `.py` files (with optional regex), auto-formats them with [Ruff](https://docs.astral.sh/ruff/), and lets you paste snippets to replace matching functions or classes using AST.

Also supports full-file diffs, line-by-line previews, and safe undo/redo with `.bak`/`.redo` files.

No cloud, no telemetry, no dependencies you don’t need. Just a PyQt6 app that does what it says.

---

## Features

- Recursive `.py` file scan
- Regex or plain-text find + replace
- Auto-format with Ruff
- Paste a snippet → replaces the same function/class in a real file
- Full diff previews before you commit changes
- Manual overwrite option
- Safe undo/redo
- File filtering + inline preview
- All local, no tracking, no fluff

---

## Install

Make sure you’ve got:

- Python 3.10+
- `ruff` installed (`pip install ruff`)
- PyQt6 (`pip install PyQt6`)

Then just run:

```bash
python -m src.main


