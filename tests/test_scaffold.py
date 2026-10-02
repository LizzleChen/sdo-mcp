"""Scaffold behavior: coverage-driven refusals, geo resolution, metadata tools.

Everything here runs offline against a db rebuilt from committed snapshots.
"""

from sdo_mcp import server, store
from sdo_mcp.ingest import seed


FIFTY_STATES = set("""AK AL AR AZ CA CO CT DE FL GA HI IA ID IL IN KS KY LA MA MD
ME MI MN MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT
WA WI WV WY""".split())


def test_list_states_covers_the_covered_states():
    res = server.list_states()
    assert set(res["states"]) == set(seed.COVERED_STATES) == FIFTY_STATES
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
    assert server.describe_source("ZZ")["status"] == "error"


def test_recognized_state_without_data_or_publication_findings(tmp_path, monkeypatch):
    p = tmp_path / "metadata_only.sqlite"
    conn = store.connect(p, create=True)
    try:
        store.init_db(conn)
        seed.load(conn)
        conn.execute("DELETE FROM coverage WHERE state='IA'")
        conn.commit()
        assert store.resolve_geo(conn, "IA", "county", "Polk")["geo_id"] == "19153"
    finally:
        conn.close()
    monkeypatch.setenv("SDO_DB", str(p))
    state = server.list_states()["states"]["IA"]
    assert state["data_loaded"] is False and state["variables"] == {}
    source = server.describe_source("IA")
    assert source["name"] == "Iowa" and source["sources_loaded"] is None
    assert source["variables"] == {} and source["review"]["status"] == "never_reviewed"
    assert server.get_forecast("IA", "county", "Polk", "population")["status"] == "coverage_unknown"
    assert server.get_components("IA", "Polk")["status"] == "coverage_unknown"


def test_national_catalog_distinguishes_montana_unresolved_source_from_loaded_forecasts():
    states = server.list_states()["states"]
    population_loaded = {state for state, meta in states.items()
                         if any(product["load_status"] == "loaded" for product in meta["variables"].get("population", {}).values())}
    assert population_loaded == FIFTY_STATES - {"MT"}
    assert states["MT"]["data_loaded"] is False and states["MT"]["variables"] == {}
    source = server.describe_source("MT")
    assert source["name"] == "Montana" and source["sources_loaded"] is None
    assert "redistribution" in source["license"]
    for variable in ("population", "households", "employment"):
        assert server.get_forecast("MT", "county", "Yellowstone", variable)["status"] == "coverage_unknown"
    assert server.get_components("MT", "Yellowstone")["status"] == "coverage_unknown"
    assert source["review"]["status"] == "never_reviewed"


def test_unknown_variable_names_the_right_tool():
    res = server.get_forecast("CO", "county", "Douglas", "births")
    assert res["status"] == "error"
    assert "get_components" in res["error"]
