# tests/test_app_upload.py
from __future__ import annotations

# from pathlib import Path
import io

import pytest

import fit_converter.app as appmod


@pytest.fixture
def client(monkeypatch, tmp_path):
    appmod.paths.INBOX = tmp_path / "inbox"
    appmod.paths.INBOX.mkdir()
    appmod.paths.OUTBOX = tmp_path / "outbox"
    appmod.paths.OUTBOX.mkdir()
    app = appmod.app
    app.config["TESTING"] = True
    return app.test_client()


def test_upload_happy_path(monkeypatch, client, tmp_path, fake_convert_factory):
    fake, calls = fake_convert_factory(
        ok=True, rows=2104, seconds=2.06, message="converted"
    )
    monkeypatch.setattr(appmod, "convert_with_report", fake)

    data = {"fitfile": (io.BytesIO(b"fakefit"), "file.fit"), "transform": "on"}
    resp = client.post("/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 302
    assert "Location" in resp.headers


def test_upload_missing_file(client):
    resp = client.post("/upload", data={}, content_type="multipart/form-data")
    assert resp.status_code == 302
