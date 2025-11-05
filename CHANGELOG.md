# Changelog

## v0.6.0 — Unified Env Configuration & Logging (November 2025)

### 🧩 Highlights
- Replaced layered TOML configuration with a **single env-only system**.
- Unified **FIT_CONVERTER_*** naming across all modules (removed legacy `APP_`).
- Centralised logging configuration — one source of truth for log filename and level.
- Cleaned development structure (`.devdata/` replaces scattered `/inbox`, `/outbox`, `/logs`).
- Simplified `app.py` and `watcher.py` startup logic for deterministic bootstrap.
- Updated tests to match new configuration and logging bootstrap model.

---

### 🔧 Core Changes
| Area | Change |
|------|---------|
| **Configuration** | Removed TOML & config discovery; added env-only `cfg.py` with defaults and type coercion. |
| **Environment Prefixes** | All runtime settings now use `FIT_CONVERTER_` prefix (e.g. `FIT_CONVERTER_TRANSFORM=false`). |
| **Paths** | Simplified `paths.py` — no `APP_*`; logs relative to `state_dir` when not absolute. |
| **Logging** | `configure_logging(logs_dir=…, logging_cfg=…)` API; filename configurable via `FIT_CONVERTER_LOG_FILENAME`. |
| **Noise Control** | Quieted `watchdog` and `werkzeug` at higher log levels to stop feedback loops. |
| **Watcher** | Uses new logging bootstrap; no more nested `.devdata/.devdata` path bug. |
| **Tests** | Modernised `test_app_bootstrap_logging` for new API; full `Paths` namespace mocking. |

---

### 🧪 Developer Notes
- **Dev env:** load `.env.dev` → creates `.devdata/{inbox,outbox,logs}`.
- **Prod env:** managed via `/etc/fit-converter/env`.
- `fit-converter doctor` reads env context; no TOML required.
- `FIT_CONVERTER_LOG_TO_FILE=true` writes to `<state_dir>/logs/<filename>` (default `fit-converter.log`).

---

### 🧱 Migration
| From | To |
|------|----|
| `APP_DATA_DIR`, `APP_LOGS_DIR`, etc. | → `FIT_CONVERTER_DATA_DIR`, `FIT_CONVERTER_LOGS_DIR` |
| `config.toml` or `config.local.toml` | → delete; use env vars |
| Hardcoded `"fit-converter.log"` | → `FIT_CONVERTER_LOG_FILENAME` in env |

---

## [v0.5.1] — 2025-11-03

### 🧹 Fixes & maintenance
- Fixed unit tests after path/logging refactor.
- Minor tweaks from App Readiness checklist (CI smoke tests, favicon, packaging).
- Verified wheel install and TestPyPI publishing flow.

---

## [v0.5.0] — 2025-11-02

### ✨ Major Improvements
- **CWD-independent paths:** all data, config, and log directories now resolve via platform-appropriate XDG/AppData locations.
  - Linux/macOS: `~/.config`, `~/.local/share`, `~/.local/state`
  - Windows: `%APPDATA%`, `%LOCALAPPDATA%`
- **Unified logging system:**
  - Removed `logging.file_path` from config — use `[paths].logs_dir` only.
  - All processes write to `<logs_dir>/fit-converter.log`.
  - Duplicate-handler guards, rotating file handler, and clear fallback to console.
- **Deterministic startup:**
  `ensure_dirs → effective_config → configure_logging` is now the standard init sequence for all entry points.
- **Watcher and web app alignment:**
  Both resolve paths at runtime using `paths.resolve(config)`; no more global `paths.INBOX/OUTBOX`.
- **Doctor utility:**
  New `python -m fit_converter.doctor` command reports config locations, rwx permissions, and free-space checks.
- **Simplified configuration:**
  - Config files read from `~/.config/fit_converter/config.toml` (or Windows equivalent).
  - Support `[paths]` and `[logging]` TOML tables plus environment overrides (`APP_DATA_DIR`, `APP_LOGS_DIR`, etc.).
- **README overhaul:**
  New setup guide detailing installation, default folder locations, and config examples.

### 🧹 Minor / Internal
- Removed unused `get_app_logger()`.
- Removed deprecated module-level `INBOX`, `OUTBOX`, `LOGS_DIR`.
- Cleaned up Ruff warnings (E741, F401, F841, etc.).
- Consistent `__init__.py` exports for `effective_config` and path utilities.

### 🚀 Upgrade notes
If upgrading from ≤ v0.4:
1. Delete any `logging.file_path` keys in your TOML.
2. Optionally set `[paths].logs_dir` to choose where `fit-converter.log` lives.
3. Run `python -m fit_converter.doctor` to verify folder permissions.

---

## Version bump

### 1️⃣ In `pyproject.toml`
```toml
[project]
name = "fit-converter"
-version = "0.4.0"
+version = "0.5.0"
```

## [0.4.0] — 2025-10-29

### 🚀 Highlights
- Modernised architecture with unified configuration, logging, and CLI tooling.
- Added typed error handling (`ConversionError`) for safe FIT→CSV conversions.
- Introduced comprehensive automated test coverage for config, app, and watcher.

### 🧱 Core Changes
#### Configuration
- Implemented **layered config system** (`cfg.py`):
  - Merges defaults → `config.toml` → `config.local.toml` → environment → CLI.
  - Adds automatic fallback to `config.example.toml` if no main config exists.
  - Protects against malformed TOML files with decode guard (warns, doesn’t crash).
- Added `tests/test_cfg.py` verifying precedence, coercion, and error handling.

#### Paths & Logging
- `paths.py` now exposes typed `Paths` dataclass and ensures inbox/outbox/logs directories exist.
- `logging_setup.py` unifies console + rotating file logging with duplicate-handler protection.

#### Converter
- Introduced `ConversionError` for clean, recoverable failures (corrupt FIT, I/O issues).
- All modules now catch and handle `ConversionError` consistently.

#### Flask App (`fit-converter`)
- Simplified `/upload` route; global + local error handling for clear user messages.
- Returns proper HTTP 400 for bad uploads or corrupt files.
- `/health` and `/healthz` endpoints for liveness probes.
- CLI entry point: `fit-converter --host 0.0.0.0 --port 5000 [--debug]`.

#### Watcher (`fit-converter-watcher`)
- Uses watchdog to monitor inbox for `.fit` files and convert automatically.
- Implements:
  - **File-stabilisation polling** before conversion.
  - **Retry with backoff** for transient errors.
  - **No-retry path** for `ConversionError`.
  - **Debounce** to prevent duplicate processing on rapid FS events.
- Graceful SIGINT/SIGTERM shutdown (systemd/Docker-safe).
- CLI overrides for inbox/outbox/poll/retries/transform/log-level.

#### Testing
- Added full pytest suite:
  - `test_cfg.py` — config precedence and TOML decode guard.
  - `test_app_upload.py` — Flask upload success and failure paths.
  - `test_watcher.py` — retry, no-retry, and debounce logic.
- All tests pass.

#### CI / Tooling
- Unified GitHub Actions workflow:
  - Linting (`black`, `isort`, `ruff`)
  - Tests (`pytest`)
- Added verification for CLI entry points and status badges.

### 🧩 Summary
Phase 4 delivers a stable, production-ready baseline:
- Safe, predictable configuration and logging.
- Robust file-watching and upload handling.
- Verified correctness and resilience through tests.

**Next:** Packaging polish and operational tooling (Docker/systemd) in Phase 5.

---
