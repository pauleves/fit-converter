import importlib


def test_imports():
    pkg = importlib.import_module  # package imports ok
    assert pkg is not None


def test_healthz():
    from fit_converter.app import app

    client = app.test_client()
    r = client.get("/healthz")
    assert r.status_code == 200
