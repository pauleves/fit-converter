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


def test_upload_happy_path(monkeypatch, client, tmp_path):
    def fake_convert(in_path, out_path, *, transform=True):
        out_path.write_text("csv")

    monkeypatch.setattr(appmod, "fit_to_csv", fake_convert)

    data = {"fitfile": (io.BytesIO(b"fakefit"), "file.fit"), "transform": "on"}
    resp = client.post("/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"].startswith("attachment;")


def test_upload_missing_file(client):
    resp = client.post("/upload", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
