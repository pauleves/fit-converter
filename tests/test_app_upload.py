# tests/test_app_upload.py
from __future__ import annotations

import importlib

# from pathlib import Path
import io
import sys

import pytest


@pytest.fixture
def client(monkeypatch, tmp_path):
    # Isolate all paths via env
    monkeypatch.setenv("APP_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("APP_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("APP_LOGS_DIR", str(tmp_path / "state" / "logs"))

    # Import after env is set so app picks up our tmp dirs
    import fit_converter.app as appmod

    importlib.reload(appmod)  # ensure it re-runs startup logic

    app = appmod.app
    app.config["TESTING"] = True
    return app.test_client()


def test_upload_happy_path(monkeypatch, client, fake_convert_factory):
    appmod = sys.modules["fit_converter.app"]
    # Swap in a fake converter that pretends to write a CSV successfully
    fake, calls = fake_convert_factory(ok=True, rows=2104, seconds=2.06)

    monkeypatch.setattr(appmod, "convert_with_report", fake)

    data = {"fitfile": (io.BytesIO(b"fakefit"), "file.fit"), "transform": "on"}
    resp = client.post("/upload", data=data, content_type="multipart/form-data")

    assert resp.status_code == 302
    assert "Location" in resp.headers
    assert calls["n"] == 1


def test_upload_missing_file(client):
    resp = client.post("/upload", data={}, content_type="multipart/form-data")
    assert resp.status_code == 302
