import pytest

from sdo_mcp.ingest import build


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    """One offline rebuild per test session, from the committed snapshots."""
    p = tmp_path_factory.mktemp("db") / "sdo.sqlite"
    build.rebuild(p)
    return p


@pytest.fixture(autouse=True)
def _point_server_at_test_db(db_path, monkeypatch):
    monkeypatch.setenv("SDO_DB", str(db_path))
