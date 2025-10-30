# tests/test_rotation.py
from logging import getLogger

from fit_converter.logging_setup import configure_logging


def test_rotates_when_max_reached(tmp_path):
    log_file = tmp_path / "rot.log"
    configure_logging(
        level="INFO",
        to_file=True,
        file_path=str(log_file),
        rotate_max_bytes=100,
        backup_count=2,
    )
    logger = getLogger("test")
    for i in range(200):
        logger.info("x" * 50)
    # base file exists and at least one backup present
    assert log_file.exists()
    rolled = list(log_file.parent.glob("rot.log.*"))
    assert rolled  # at least one rotation occurred
