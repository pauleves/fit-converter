# tests/test_app_bootstrap_logging.py
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def test_app_bootstrap_passes_logging_block(monkeypatch):
    fake_cfg = {
        "logging": {
            "level": "INFO",
            "to_file": True,
            # no file_path in the new API; handler derives it from ensure_dirs().logs_dir
            "rotate_max_bytes": 123,
            "backup_count": 9,
            # "filename": "fit-converter.log",  # optional, default used if omitted
        },
        "transform": True,
    }

    # Build a full fake Paths object with all attributes your app may touch on import
    fake_paths = SimpleNamespace(
        config_dir=Path("/tmp/fitc-config"),
        data_dir=Path("/tmp/fitc-data"),
        state_dir=Path("/tmp/fitc-state"),
        inbox=Path("/tmp/fitc-data/inbox"),
        outbox=Path("/tmp/fitc-data/outbox"),
        logs_dir=Path("/tmp/fitc-state/logs"),
    )

    with (
        patch("fit_converter.cfg.effective_config", return_value=fake_cfg),
        patch("fit_converter.paths.ensure_dirs", return_value=fake_paths),
        patch("fit_converter.logging_setup.configure_logging") as mock_conf,
    ):
        # Import once; don't reload — reloading reruns top-level bootstrap
        import fit_converter.app as appmod  # noqa: F401

        mock_conf.assert_called_once_with(
            logs_dir=fake_paths.logs_dir,
            logging_cfg=fake_cfg["logging"],
        )
