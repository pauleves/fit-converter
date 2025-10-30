import importlib
from unittest.mock import patch


def test_app_bootstrap_passes_logging_block(monkeypatch):
    fake_cfg = {
        "logging": {
            "level": "INFO",
            "to_file": True,
            "file_path": "logs/fit-converter.log",
            "rotate_max_bytes": 123,
            "backup_count": 9,
        },
        "transform": True,
    }

    # Patch the ORIGINAL definitions that app.py imports from
    with (
        patch("fit_converter.cfg.effective_config", side_effect=[fake_cfg, fake_cfg]),
        patch("fit_converter.logging_setup.configure_logging") as mock_conf,
    ):
        from fit_converter import app as appmod

        importlib.reload(appmod)  # triggers bootstrap

        mock_conf.assert_called_once_with(
            level="INFO",
            to_file=True,
            file_path="logs/fit-converter.log",
            rotate_max_bytes=123,
            backup_count=9,
        )
