"""Vermont's separate adopted 2025 state and historical 2013 county products."""
import io
import json
from functools import lru_cache

import pytest
from pypdf import PdfReader

from sdo_mcp import server, store
from sdo_mcp.ingest import vt


@lru_cache
def _body():
    return (vt.RAW_DIR / vt.FILE).read_bytes()


@lru_cache
def _pages():
    return tuple(page.extract_text() for page in PdfReader(io.BytesIO(_body())).pages)


def test_parser_complete_county_scenarios_and_rendered_fixtures():
    rows = vt.parse(_body())
    assert len(rows) == 84
    assert {(r["geo_id"], r["scenario"], r["year"]) for r in rows} == {(gid, scenario, year) for gid in set(vt._geographies().values()) - {"50"} for scenario in vt.SCENARIOS for year in vt.YEARS}
    assert all(r["datatype"] == ("estimate" if r["year"] == 2010 else "projection") for r in rows)
    values = {(r["geo_id"], r["scenario"], r["year"]): r["value"] for r in rows}
    for gid, scenario, year, value in vt.FIXTURES:
        if gid != "50":
            assert values[gid, scenario, year] == value


def test_parser_new_state_exhaustive_age_normalization():
    body = (vt.RAW_DIR / vt.HOUSING_FILE).read_bytes()
    extract = (vt.RAW_DIR / vt.EXTRACT_FILE).read_bytes()
    rows = vt._parse_state(body, extract)
    assert rows == [dict(state="VT", geo_level="state", geo_id="50", year=year, variable="population",
                         value=value, datatype="projection", scenario="current_trends", source_id=vt.STATE_SOURCE_ID)
                    for year, value in zip((2030, 2040, 2050), (666640, 667903, 644731))]
    data = json.loads(extract)
    assert len(data["age_groups"]) == 18 and len(data["values_by_year"]) == 3
    assert data["values_by_year"][0][0] == 29443 and data["values_by_year"][2][-1] == 42641


def test_query_products_have_separate_source_base_horizon_and_default():
    state = server.get_forecast("VT", "state", "Vermont", "population")
    assert state["status"] == "ok" and state["scenario"] == "current_trends"
    assert state == server.get_forecast("VT", "state", "50", "population")
    assert state["series"] == [dict(year=year, value=value, datatype="projection")
                               for year, value in zip((2030, 2040, 2050), (666640, 667903, 644731))]
    assert state["source"]["base_year"] is None and state["source"]["horizon_year"] == 2050
    assert "March 10, 2025" in state["source"]["vintage"]
    county = server.get_forecast("VT", "county", "Chittenden", "population")
    assert county["status"] == "ok" and county["scenario"] == "b"
    assert county == server.get_forecast("VT", "county", "50007", "population")
    explicit = server.get_forecast("VT", "county", "50007", "population", scenario="B")
    assert explicit["series"] == county["series"] and explicit["source"] == county["source"]
    assert explicit["scenario"] == "b"
    assert county["series"] == [dict(year=2010, value=156545, datatype="estimate"),
                                dict(year=2020, value=161812, datatype="projection"),
                                dict(year=2030, value=162967, datatype="projection")]
    assert county["source"]["vintage"] == "August 2013" and county["source"]["base_year"] == 2010
    assert county["source"]["horizon_year"] == 2030
    assert server.get_forecast("VT", "county", "Essex", "population", scenario="A")["series"][-1]["value"] == 5489
    conn = store.connect()
    try:
        vt.verify(conn)
    finally:
        conn.close()


def test_only_valid_scenarios_for_selected_geography():
    for level, name, scenario in (("state", "VT", "A"), ("state", "VT", "B"),
                                 ("county", "Chittenden", "current_trends"), ("county", "Essex", "high")):
        assert server.get_forecast("VT", level, name, "population", scenario=scenario)["status"] == "error"


def test_deferred_municipal_and_unverified_extra_variables():
    assert server.get_forecast("VT", "county_subdivision", "Burlington", "population")["status"] == "pdf_only"
    for variable in ("households", "employment"):
        assert server.get_forecast("VT", "state", "VT", variable)["status"] == "coverage_unknown"
    assert server.get_components("VT", "VT")["status"] == "coverage_unknown"
    assert server.describe_source("VT")["review"]["status"] == "never_reviewed"


@pytest.mark.parametrize("level,name,start,end", [("state", "VT", 2010, 2029), ("state", "VT", 2031, 2039),
                                                    ("state", "VT", 2051, 2070), ("county", "Essex", 2021, 2029),
                                                    ("county", "Essex", 2031, 2050)])
def test_no_interpolation_fabricated_base_or_horizon_extension(level, name, start, end):
    assert server.get_forecast("VT", level, name, "population", start_year=start, end_year=end)["status"] == "empty_range"


@pytest.mark.parametrize("token", ["-1", "1.5", "1,00", "NA", "*", "", "nan"])
def test_parser_rejects_suppressed_or_invalid_population(token):
    with pytest.raises(ValueError, match="integer"):
        vt._integer(token)


@pytest.mark.parametrize("change", [
    lambda text: text.replace("Scenario A", "Scenario B"),
    lambda text: text.replace("2020", "2025"),
    lambda text: text.replace("Essex County", "Orleans County"),
    lambda text: text.replace("254 186", "254 *"),
    lambda text: text.replace("Total 6,306 5,949", "Total 6,306 5,948"),
    lambda text: text + "\nTotal 6,306 5,949 -5.7% 5,489 -13.0%\n",
])
def test_parser_rejects_changed_scenario_year_geography_suppression_totals_duplicates(change):
    with pytest.raises(ValueError):
        vt._parse_table(change(_pages()[10]), "Essex County", "a")


@pytest.mark.parametrize("change", [
    lambda d: d["age_groups"].pop(),
    lambda d: d["years"].__setitem__(1, 2045),
    lambda d: d["values_by_year"][0].__setitem__(0, 29442),
    lambda d: d.__setitem__("source_sha256", "0" * 64),
    lambda d: d.__setitem__("chart_decoded_sha256", "0" * 64),
])
def test_parser_rejects_altered_raster_derived_cells_and_provenance(change):
    data = json.loads((vt.RAW_DIR / vt.EXTRACT_FILE).read_bytes())
    change(data)
    with pytest.raises(ValueError, match="extraction"):
        vt._parse_state((vt.RAW_DIR / vt.HOUSING_FILE).read_bytes(), json.dumps(data).encode())


@pytest.mark.parametrize("body", [b"<html>error200</html>", b'{"error":"not a PDF"}', b"%PDF-broken"])
def test_parser_rejects_http200_non_pdf(body):
    with pytest.raises(ValueError, match="PDF"):
        vt.parse(body)


def test_snapshot_manifest_fingerprints():
    assert {entry["file"] for entry in vt.fetch.read_manifest(vt.RAW_DIR)} == set(vt.FILES)
