# Changelog

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
