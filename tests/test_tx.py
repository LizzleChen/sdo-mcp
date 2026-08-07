"""Texas round-trips through the tools: known published values (confirmed
against TDC's Projections/Totals API at acquire time) must come back out of
get_forecast exactly, per scenario. Offline — runs against the committed
scenario zips."""

from sdo_mcp import server


def _point(res, year):
    return next(p for p in res["series"] if p["year"] == year)


def test_state_defaults_to_mid_scenario():
    res = server.get_forecast("TX", "state", "Texas", "population")
    assert res["status"] == "ok"
    assert res["scenario"] == "mid"
    assert "recommended" in res["scenario_note"]
    assert _point(res, 2020) == {"year": 2020, "value": 29145505, "datatype": "estimate"}
    assert _point(res, 2024) == {"year": 2024, "value": 31290831, "datatype": "estimate"}
    assert _point(res, 2025) == {"year": 2025, "value": 31669507, "datatype": "projection"}
    years = [p["year"] for p in res["series"]]
    assert (years[0], years[-1]) == (2020, 2060)
    assert len(years) == len(set(years))  # the 2020 duplicate row is gone


def test_county_scenarios_differ():
    mid = server.get_forecast("TX", "county", "Harris", "population", scenario="mid")
    high = server.get_forecast("TX", "county", "Harris", "population", scenario="high")
    low = server.get_forecast("TX", "county", "Harris", "population", scenario="low")
    assert mid["geo"]["id"] == "48201"
    assert _point(mid, 2060)["value"] == 6865248
    assert _point(low, 2060)["value"] < _point(mid, 2060)["value"] < _point(high, 2060)["value"]
    # All three scenarios share the same estimate history.
    assert _point(low, 2020) == _point(mid, 2020) == _point(high, 2020)


def test_anderson_county_matches_totals_api():
    res = server.get_forecast("TX", "county", "Anderson", "population", 2030, 2060)
    assert res["status"] == "ok"
    assert _point(res, 2030)["value"] == 60080
    assert _point(res, 2060)["value"] == 59622


def test_source_records_vintage_and_2020_convention():
    res = server.get_forecast("TX", "state", "48", "population", 2020, 2020)
    src = res["source"]
    assert src["vintage"] == "2024" and src["base_year"] == 2024
    assert "April 1 Census" in src["method_notes"]
    assert src["retrieved_at"]


def test_msa_round_trip_by_name_and_fips():
    by_name = server.get_forecast("TX", "msa", "Austin", "population")
    assert by_name["status"] == "ok"
    assert by_name["geo"] == {
        "level": "msa", "id": "12420", "name": "Austin-Round Rock-San Marcos, TX",
    }
    by_fips = server.get_forecast("TX", "msa", "10180", "population")
    assert by_fips["geo"]["name"] == "Abilene, TX"
    assert _point(by_fips, 2020)["value"] == 176579
    assert _point(by_fips, 2060)["value"] == 218016


def test_cog_round_trip_by_name_and_bare_int():
    by_name = server.get_forecast("TX", "cog", "Alamo Area", "population")
    assert by_name["status"] == "ok"
    assert by_name["geo"] == {"level": "cog", "id": "tx-cog-18", "name": "Alamo Area"}
    assert _point(by_name, 2020)["value"] == 2671161
    assert _point(by_name, 2060)["value"] == 4074166
    by_int = server.get_forecast("TX", "cog", "18", "population")
    assert by_int["geo"]["id"] == "tx-cog-18"


def test_txdot_round_trip_by_name_and_bare_int():
    by_name = server.get_forecast("TX", "txdot_district", "Abilene District", "population")
    assert by_name["status"] == "ok"
    assert by_name["geo"] == {
        "level": "txdot_district", "id": "tx-txdot-1", "name": "Abilene District",
    }
    assert _point(by_name, 2020)["value"] == 266921
    assert _point(by_name, 2060)["value"] == 301271
    by_int = server.get_forecast("TX", "txdot_district", "1", "population")
    assert by_int["geo"]["id"] == "tx-txdot-1"


def test_geo_levels_are_decade_only_with_estimate_projection_flags():
    res = server.get_forecast("TX", "msa", "12420", "population")
    assert [p["year"] for p in res["series"]] == [2020, 2030, 2040, 2050, 2060]
    assert _point(res, 2020)["datatype"] == "estimate"
    assert all(p["datatype"] == "projection" for p in res["series"][1:])
    src = res["source"]
    assert src["vintage"] == "2024" and src["base_year"] == 2024
    assert "decade resolution" in src["method_notes"]


def test_geo_scenario_ordering_low_mid_high():
    for level, geo in (("msa", "12420"), ("cog", "tx-cog-18"),
                       ("txdot_district", "tx-txdot-1")):
        low = server.get_forecast("TX", level, geo, "population", scenario="low")
        mid = server.get_forecast("TX", level, geo, "population", scenario="mid")
        high = server.get_forecast("TX", level, geo, "population", scenario="high")
        assert _point(low, 2020) == _point(mid, 2020) == _point(high, 2020)
        assert (_point(low, 2060)["value"] < _point(mid, 2060)["value"]
                < _point(high, 2060)["value"])


def test_cog_and_txdot_partition_state_mid():
    state = server.get_forecast("TX", "state", "48", "population", scenario="mid")
    # State/county are annual; MSA/COG/TxDOT are decade-only — compare the
    # five decade years the two channels share.
    state_vals = {
        p["year"]: p["value"] for p in state["series"]
        if p["year"] in (2020, 2030, 2040, 2050, 2060)
    }
    for level in ("cog", "txdot_district"):
        sums = {}
        for i in range(1, 26):  # ids 1-25 cover both (COG runs 1-24)
            res = server.get_forecast("TX", level, str(i), "population", scenario="mid")
            if res["status"] != "ok":
                continue
            for p in res["series"]:
                sums[p["year"]] = sums.get(p["year"], 0) + p["value"]
        assert sums == state_vals, f"{level} sums must equal the state total (Mid)"


def test_ambiguous_name_returns_candidates_never_a_guess():
    res = server.get_forecast("TX", "cog", "Grande", "population")
    assert res["status"] == "error"
    assert "ambiguous" in res["error"]
    names = {c["name"] for c in res["candidates"]}
    assert {"Rio Grande", "Middle Rio Grande", "Lower Rio Grande Valley"} <= names


def test_returned_geo_id_is_requeryable():
    first = server.get_forecast("TX", "cog", "Alamo Area", "population")
    again = server.get_forecast("TX", "cog", first["geo"]["id"], "population")
    assert again["status"] == "ok"
    assert again["series"] == first["series"]


def test_list_states_shows_served_tx_geo_levels():
    res = server.list_states()
    tx_pop = res["states"]["TX"]["variables"]["population"]
    for level in ("msa", "cog", "txdot_district"):
        assert tx_pop[level]["status"] == "available"
        assert "TDC Totals API" in tx_pop[level]["detail"]
