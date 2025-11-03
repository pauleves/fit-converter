from unittest.mock import patch


def test_app_bootstrap_passes_logging_block(monkeypatch):
    fake_cfg = {
        "logging": {
            "level": "INFO",
            "to_file": True,
            # no file_path in the new API; the handler derives it from ensure_dirs()
            "rotate_max_bytes": 123,
            "backup_count": 9,
        },
        "transform": True,
    }

    with (
        patch("fit_converter.cfg.effective_config", return_value=fake_cfg),
        patch("fit_converter.logging_setup.configure_logging") as mock_conf,
    ):
        # Import once; don't reload — reloading reruns top-level bootstrap
        import fit_converter.app as appmod  # noqa: F401

        mock_conf.assert_called_once_with(
            level="INFO",
            to_file=True,
            rotate_max_bytes=123,
            backup_count=9,
        )
