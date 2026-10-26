import importlib

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch, black_drawing):
    monkeypatch.setenv("OPENFAIR_JOBS", str(tmp_path / "jobs"))
    monkeypatch.setenv("OPENFAIR_TOKEN", "s3cret")
    import src.webapp as web
    web = importlib.reload(web)
    from tests.conftest import CALLOUTS, fake_extractor_for
    real = web.run_pipeline
    monkeypatch.setattr(web, "run_pipeline", lambda *a, **k: real(*a, **k, extractor=fake_extractor_for(CALLOUTS),
                                                                  title_extractor=lambda p: {}))
    return TestClient(web.app), black_drawing.read_bytes()


def test_token_required(client):
    c, pdf = client
    r = c.post("/run", files={"pdf": ("d.pdf", pdf, "application/pdf")}, data={"token": "wrong"})
    assert r.status_code == 401


def test_rejects_non_pdf(client):
    c, _ = client
    r = c.post("/run", files={"pdf": ("d.pdf", b"hello", "application/pdf")}, data={"token": "s3cret"})
    assert r.status_code == 400


def test_full_run_and_download(client):
    c, pdf = client
    r = c.post("/run", files={"pdf": ("d.pdf", pdf, "application/pdf")}, data={"token": "s3cret"})
    assert r.status_code == 200 and "4 characteristics" in r.text
    import re
    link = re.search(r'href="(/files/[0-9a-f]{32}/drawing_FAIR\.xlsx\?token=s3cret)"', r.text).group(1)
    assert c.get(link).status_code == 200
    assert c.get(link.replace("s3cret", "nope")).status_code == 401
    assert c.get("/files/../../etc/passwd?token=s3cret").status_code == 404
