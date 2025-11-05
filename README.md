# FIT → CSV Converter

[![CI](https://github.com/pauleves/fit-converter/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/pauleves/fit-converter/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.14-blue)
[![License](https://img.shields.io/github/license/pauleves/fit-converter)](./LICENSE)
![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)
[![isort](https://img.shields.io/badge/imports-isort-brightgreen.svg)](https://pycqa.github.io/isort/)
[![Ruff](https://img.shields.io/badge/lint-Ruff-success)](https://docs.astral.sh/ruff/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com/)
[![codecov](https://codecov.io/gh/pauleves/fit-converter/branch/main/graph/badge.svg)](https://codecov.io/gh/pauleves/fit-converter)

Convert Garmin `.FIT` files into clean, human-readable `.CSV` files.
Includes optional data transformations, a Flask upload interface, and a headless file-watcher for automated conversions.

---

# Setup & Configuration

This section explains how to install the app, where it stores its files, using a **single environment-based configuration**.
No `config.toml` or per-user config files are required.

## 1️⃣ Install

```bash
# From your project root
python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip build
python -m build
pip install dist/fit_converter-*.whl
```


## 2️⃣ Where files live (default locations)

The app follows platform conventions and never depends on your current working directory.

| Purpose             | Default path (Linux/macOS)                            | Notes                                                                     |
| ------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------- |
| Data (inbox/outbox) | `~/.local/share/fit_converter/`                       | configurable via `FIT_CONVERTER_DATA_DIR`                                 |
| State (logs, cache) | `~/.local/state/fit_converter/`                       | configurable via `FIT_CONVERTER_STATE_DIR`                                |
| Logs                | `~/.local/state/fit_converter/logs/fit-converter.log` | configurable via `FIT_CONVERTER_LOGS_DIR` or `FIT_CONVERTER_LOG_FILENAME` |


Windows uses `%LOCALAPPDATA%\fit_converter\` and `%APPDATA%\fit_converter\` equivalents.


## 3️⃣ Configure via Environment

All runtime behaviour is controlled with `FIT_CONVERTER_*` variables (and optional `FLASK_*` for the web server).

Example .env.dev:
```bash
# Paths
# (Uncomment these only if you want to set a non-default location in dev)
# FIT_CONVERTER_DATA_DIR=/<location>
# FIT_CONVERTER_STATE_DIR=./<location>
# FIT_CONVERTER_LOGS_DIR=logs

FIT_CONVERTER_INBOX=inbox
FIT_CONVERTER_OUTBOX=outbox
FIT_CONVERTER_LOG_FILENAME=fit-converter.log

# Behaviour
FIT_CONVERTER_TRANSFORM=false
FIT_CONVERTER_POLL_INTERVAL=0.5
FIT_CONVERTER_RETRIES=3

# Logging
FIT_CONVERTER_LOG_LEVEL=DEBUG
FIT_CONVERTER_LOG_TO_FILE=true
FIT_CONVERTER_LOG_ROTATE_MAX_BYTES=1000000
FIT_CONVERTER_LOG_BACKUP_COUNT=5

# Flask (dev)
FLASK_HOST=127.0.0.1
FLASK_PORT=8000
FLASK_DEBUG=0
FLASK_SECRET_KEY=dev-only-not-secret
```
Load it when running locally:
```bash
set -a && source .env.dev && set +a
export PYTHONPATH=src
```


## 4️⃣ Verify setup with Doctor

Run the built-in diagnostic tool:
```bash
python -m fit_converter.doctor
```

It prints:

- Relevant `FIT_CONVERTER_*` and `FLASK_*` environment variables
- Resolved absolute paths and RWX permissions
- Effective logging configuration and log file path


## 6️⃣ Start the Web UI

```bash
python -m fit_converter.app --host 127.0.0.1 --port 8000
# Visit http://127.0.0.1:8000
```
- uploads go to `inbox/`, CSVs appear in `outbox/`.
- Logs are written to `<state_dir>/logs/<filename>` (unless overriden).


## 7️⃣ Start the Watcher

The watcher automatically converts new .fit files dropped into inbox/:
```bash
python -m fit_converter.watcher --log-level INFO --poll 0.5 --retries 2
```
CLI flags temporarily override environment values for that session.


## 8️⃣ Troubleshooting
🧩 **No logs written?**
- Run `python -m fit_converter.doctor` and confirm `logs_dir` exists and is writable.
- Check `FIT_CONVERTER_LOG_TO_FILE=true`.

📂 **Files go to an unexpected inbox/outbox?**
In development, you normally **don’t set** any of the path variables.
The app automatically uses platform defaults:

- Data: `~/.local/share/fit_converter` (Linux/macOS) or `%LOCALAPPDATA%\fit_converter`
- State/Logs: `~/.local/state/fit_converter` (Linux/macOS) or `%LOCALAPPDATA%\fit_converter\Logs`

These locations are stable and prevent watcher feedback loops during local runs.

Only in **production** (for example on a Raspberry Pi or server) should you override them, e.g.:

```bash
FIT_CONVERTER_DATA_DIR=/var/lib/fit-converter
FIT_CONVERTER_STATE_DIR=/var/lib/fit-converter/state
FIT_CONVERTER_LOGS_DIR=/var/lib/fit-converter/state/logs
```

Log feedback loop?
At DEBUG level, `watchdog` may emit many inotify events; these are suppressed automatically in 0.6.


## 9️⃣ Uninstall / Reset
```bash
pip uninstall fit-converter
rm -rf ~/.config/fit_converter
rm -rf ~/.local/share/fit_converter
rm -rf ~/.local/state/fit_converter
```

Now you’re ready to convert FIT files reliably — no CWD issues, consistent logs, and clean per-user configuration.


# Development & Release
To verify a build locally before tagging, run:

```bash
# Verify install locally before tagging
rm -rf dist build *.egg-info
python -m build --wheel
pip install dist/fit_converter-*.whl --force-reinstall
pytest -q
python -m fit_converter.doctor
```

Tag a release:
```bash
git tag -a v0.6.0 -m "v0.6.0 — unified env config & logging"
git push origin v0.6.0
```
