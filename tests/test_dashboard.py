"""Dashboard auth, safety, projections and packaging contract."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from aura.api import create_app
from aura.config import Settings
from aura.dashboard_fixture import seed_dashboard
from aura.store import Store

ADMIN = "synthetic-dashboard-admin-access-token-only"
VIEWER = "synthetic-dashboard-viewer-access-token-only"
AUTH = {"Authorization": "Bearer " + ADMIN}
READ = {"Authorization": "Bearer " + VIEWER}


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(tmp_path, ADMIN, VIEWER))) as c:
        yield c


def test_dash01_public_shell_contains_no_credentials(client):
    page = client.get("/dashboard")
    assert page.status_code == 200 and "Command center" in page.text
    assert ADMIN not in page.text and VIEWER not in page.text
    assert page.headers["cache-control"] == "no-store"
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert page.headers["x-frame-options"] == "DENY"
    for name in ("app.js", "app.css"):
        assert client.get("/dashboard/" + name).status_code == 200
    assert client.get("/dashboard/../../aura/config.py").status_code == 404


def test_dash02_summary_requires_auth_and_handles_empty_database(client):
    assert client.get("/v1/dashboard/overview").status_code == 401
    data = client.get("/v1/dashboard/overview", headers=READ).json()
    assert data["role"] == "viewer"
    assert data["kill_switch"] is True and not data["live_enabled"]
    assert data["feeds"] == data["sessions"] == data["evaluations"] == []
    assert sum(a["implementation"] == "local_task" for a in data["agents"]) == 3
    assert data["runtime"]["android"] == "not_built"
    assert not data["dashboard_entries_enabled"]
    assert data["version"] == "0.6.1"


def test_dash03_viewer_cannot_stop_or_clear_control(client):
    assert client.post("/v1/dashboard/stop", json={"enabled": True}, headers=READ).status_code == 403
    assert client.post("/v1/dashboard/stop", json={"enabled": False}, headers=AUTH).status_code == 422
    assert client.post("/v1/dashboard/stop", json={"enabled": True, "other": 1}, headers=AUTH).status_code == 422


def test_dash04_admin_can_only_activate_stop_from_dashboard(client):
    client.app.state.store.set_kill(False)
    response = client.post("/v1/dashboard/stop", json={"enabled": True}, headers=AUTH)
    assert response.status_code == 200 and response.json()["kill_switch"] is True
    assert client.app.state.store.killed()


def test_dash05_missing_safety_state_returns_unavailable(client):
    with client.app.state.store.connect() as db:
        db.execute("DELETE FROM controls WHERE name='kill_switch'")
    result = client.get("/v1/dashboard/overview", headers=AUTH)
    assert result.status_code == 503 and "unavailable" in result.text


def test_dash06_seeded_projections_and_sensitive_bindings_excluded(tmp_path):
    seed_dashboard(tmp_path)
    # A deliberately private binding marker must not appear in the projection.
    with Store(tmp_path).connect() as db:
        db.execute("INSERT INTO feed_bindings VALUES (?,?)", ("private-feed", "private-fingerprint-marker"))
    with TestClient(create_app(Settings(tmp_path, ADMIN, VIEWER))) as c:
        response = c.get("/v1/dashboard/overview", headers=READ)
        assert response.status_code == 200
        data = response.json()
        assert data["fixture_preview"]
        assert len(data["sessions"]) == 1 and len(data["evaluations"]) == 3
        assert data["sessions"][0]["source"] == "fixture"
        assert data["sessions"][0]["position"]["side"] == "buy"
        assert len(data["recent_research"]) == 1
        assert "private-fingerprint-marker" not in response.text
        assert ADMIN not in response.text and VIEWER not in response.text
        assert all(not r["promotion_allowed"] for r in data["evaluations"])


def test_dash07_fixture_refuses_operational_directory(tmp_path):
    (tmp_path / "existing.txt").write_text("keep")
    with pytest.raises(ValueError, match="empty"):
        seed_dashboard(tmp_path)
    assert (tmp_path / "existing.txt").read_text() == "keep"


def test_dash08_assets_do_not_persist_tokens_or_render_untrusted_html():
    script = (Path(__file__).parents[1] / "aura/web/app.js").read_text()
    assert "localStorage" not in script and "sessionStorage" not in script
    assert "innerHTML" not in script and "insertAdjacentHTML" not in script
    assert "textContent" in script
    assert "JSON.stringify({enabled:true})" in script


def test_dash09_launcher_loopback_and_operational_stop_unchanged(tmp_path, monkeypatch, capsys):
    import sys

    from aura.dashboard import main

    store = Store(tmp_path)
    monkeypatch.setenv("AURA_ADMIN_TOKEN", ADMIN)
    monkeypatch.setenv("AURA_VIEWER_TOKEN", VIEWER)
    monkeypatch.setattr(sys, "argv", ["dashboard", "--data-dir", str(tmp_path)])
    with patch("aura.dashboard.uvicorn.run") as run:
        main()
        assert run.call_args.kwargs["host"] == "127.0.0.1"
        assert run.call_args.kwargs["access_log"] is False
    assert ADMIN not in capsys.readouterr().out
    assert store.killed()


def test_dash10_version_matches_package():
    import tomllib

    from aura import __version__

    data = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert data["project"]["version"] == __version__
    assert "web/*.html" in data["tool"]["setuptools"]["package-data"]["aura"]
