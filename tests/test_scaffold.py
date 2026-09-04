"""Scaffold behavior: coverage-driven refusals, geo resolution, metadata tools.

Everything here runs offline against a db rebuilt from committed snapshots.
"""

from sdo_mcp import server, store
from sdo_mcp.ingest import seed


def test_list_states_covers_the_covered_states():
    res = server.list_states()
    # The six pilots plus the expansion states ingested so far.
    assert {"CO", "TX", "CA", "TN", "GA", "FL", "NC", "MN", "AZ", "WA", "OR"} <= set(res["states"])
    tx = res["states"]["TX"]
    assert tx["variables"]["households"]["county"]["status"] == "not_published"
    assert tx["scenarios"] == ["mid", "high", "low"]
    assert res["states"]["CO"]["scenarios"] is None


def test_refusal_tx_households_is_structural():
    res = server.get_forecast("TX", "county", "Harris", "households")
    assert res["status"] == "not_published"
    assert "2018" in res["reason"]
    assert res["closest_published"] is None


def test_refusal_fl_county_employment_points_to_state_pdf():
    res = server.get_forecast("FL", "county", "Alachua", "employment")
    assert res["status"] == "state_level_only"
    pointers = res["closest_published"]
    assert pointers and pointers[0]["geo_level"] == "state"
    assert pointers[0]["status"] == "pdf_only"


def test_refusal_co_place_points_to_county():
    res = server.get_forecast("CO", "place", "Colorado Springs", "population")
    assert res["status"] == "not_published"
    assert "municipal" in res["reason"].lower()
    assert "county" in {p["geo_level"] for p in res["closest_published"]}


def test_published_but_not_ingested_is_distinct_from_not_published(tmp_path, monkeypatch):
    # A seed-only database (coverage + geographies, no adapters): a variable a
    # state publishes but this server hasn't ingested is "not_loaded" — never
    # conflated with "not_published".
    p = tmp_path / "seed_only.sqlite"
    conn = store.connect(p, create=True)
    store.init_db(conn)
    seed.load(conn)
    conn.close()
    monkeypatch.setenv("SDO_DB", str(p))
    res = server.get_forecast("TX", "county", "Harris", "population")
    assert res["status"] == "not_loaded"
    assert "not been ingested" in res["reason"]


def test_scenario_validation():
    res = server.get_forecast("TX", "county", "Harris", "population", scenario="zzz")
    assert res["status"] == "error"
    assert "mid" in res["error"]
    res = server.get_forecast("CO", "county", "Douglas", "population", scenario="high")
    assert res["status"] == "error"
    assert "no scenarios" in res["error"]


def test_geo_resolution(db_path):
    conn = store.connect(db_path)
    try:
        assert store.resolve_geo(conn, "CO", "county", "35")["geo_id"] == "08035"
        assert store.resolve_geo(conn, "CO", "county", "Douglas")["name"] == "Douglas County"
        assert store.resolve_geo(conn, "CO", "county", "08035")["name"] == "Douglas County"
        assert store.resolve_geo(conn, "CO", "state", "Colorado")["geo_id"] == "08"
        amb = store.resolve_geo(conn, "CO", "county", "ar")
        assert len(amb["candidates"]) >= 2  # Arapahoe, Archuleta, Larimer, ...
        assert "error" in store.resolve_geo(conn, "CO", "county", "Sprongfield")
    finally:
        conn.close()


def test_describe_source():
    res = server.describe_source("co")
    assert "Department of Local Affairs" in res["agency"]
    assert res["sources_loaded"] is None or isinstance(res["sources_loaded"], list)
    assert server.describe_source("WY")["status"] == "error"


def test_unknown_variable_names_the_right_tool():
    res = server.get_forecast("CO", "county", "Douglas", "births")
    assert res["status"] == "error"
    assert "get_components" in res["error"]
