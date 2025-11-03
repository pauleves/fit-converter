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

This section explains how to install the app, where it stores its files, and how to configure `config.toml` after installation.

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

### Linux / macOS
| Purpose           | Default path                                          |
| ----------------- | ----------------------------------------------------- |
| Config            | `~/.config/fit_converter/`                            |
| Data (user files) | `~/.local/share/fit_converter/` → `inbox/`, `outbox/` |
| State (internal)  | `~/.local/state/fit_converter/`                       |
| Logs              | `~/.local/state/fit_converter/logs/fit-converter.log` |

### Windows
| Purpose | Default path                                          |
| ------- | ----------------------------------------------------- |
| Config  | `%APPDATA%\fit_converter\`                            |
| Data    | `%LOCALAPPDATA%\fit_converter\` → `inbox\`, `outbox\` |
| State   | `%LOCALAPPDATA%\fit_converter\`                       |
| Logs    | `%LOCALAPPDATA%\fit_converter\Logs\fit-converter.log` |


To confirm your current paths:
```bash

python - <<'PY'
from fit_converter.paths import resolve_runtime_paths
p = resolve_runtime_paths()
print("config_dir:", p.config_dir)
print("data_dir :", p.data_dir)
print("state_dir:", p.state_dir)
print("inbox    :", p.inbox)
print("outbox   :", p.outbox)
print("logs_dir :", p.logs_dir)
PY
```


## 3️⃣ Create your configuration

Create your config folder and add config.toml:
```bash
mkdir -p ~/.config/fit_converter
nano ~/.config/fit_converter/config.toml
```

### Example `config.toml`
```toml
[paths]
# Folder for logs (filename fixed to 'fit-converter.log')
# logs_dir = "~/.local/state/fit_converter/logs"

# Optional data folder and inbox/outbox overrides
# data_dir = "~/fc-data"
# inbox = "incoming"
# outbox = "exports"

[logging]
level = "INFO"
to_file = true
rotate_max_bytes = 1000000
backup_count = 5
```

### Notes
- `inbox`/`outbox` can be absolute or relative to `data_dir`.
- Log filename is always `fit-converter.log`; you control only `logs_dir`.
- Internal `state_dir` is handled automatically.


## 4️⃣ Environment overrides (optional)

You can override TOML settings with environment variables:

| Env var         | Purpose                             |
| --------------- | ----------------------------------- |
| `APP_DATA_DIR`  | Base for `inbox/` and `outbox/`     |
| `APP_STATE_DIR` | Base for logs if `logs_dir` not set |
| `APP_LOGS_DIR`  | Force logs directory directly       |


Example:
```bash
APP_DATA_DIR=/tmp/fc-data python -m fit_converter.app
APP_LOGS_DIR=/var/log/fit_converter python -m fit_converter.watcher
```

If using `/var/log/fit_converter`:
```bash
sudo mkdir -p /var/log/fit_converter
sudo chown "$USER":adm /var/log/fit_converter
```


## 5️⃣ Verify setup with Doctor

Run the built-in diagnostics:
```bash
python -m fit_converter.doctor
```

It prints:

- Config file locations (`config.toml`, `config.local.toml`)
- Resolved paths (config/data/state/inbox/outbox/logs)
- RWX permissions and free-space warnings


## 6️⃣ Start the Web UI

```bash
python -m fit_converter.app --host 127.0.0.1 --port 5000
# Visit http://127.0.0.1:5000
```
Uploads go to `inbox/`, converted CSVs appear in `outbox/`.
Logs stream to `<logs_dir>/fit-converter.log`.


## 7️⃣ Start the Watcher

The watcher automatically converts new .fit files dropped into inbox/:
```bash
python -m fit_converter.watcher --log-level INFO --poll 0.5 --retries 2
```
CLI flags override TOML settings for that session.


## 8️⃣ Troubleshooting
🧩 No logs written?
- Run python -m fit_converter.doctor and confirm logs_dir exists and is writable.
- Remove any old `logging.file_path` keys from your TOML.

📂 Files go to wrong inbox/outbox?

Make sure you resolve paths at startup:
```python
from fit_converter.paths import resolve
paths = resolve(config)
INBOX, OUTBOX = paths.inbox, paths.outbox
```

🔐 Permissions on `/var/log`

- Either adjust ownership or use a user-space log directory.

- 🪟 Windows paths

Use quotes for paths with spaces:
``toml
[paths]
logs_dir = "C:\\Users\\Paul\\AppData\\Local\\fit_converter\\Logs"
```


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
./scripts/verify-install.sh
```
