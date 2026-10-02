"""Kansas's adopted older forecast and separate unresolved newer CEDBR candidate."""

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import ks


def _bodies():
    return {name: (ks.RAW_DIR / name).read_bytes() for name in ks.FILES}


def _texts():
    return [page.extract_text() or "" for page in ks._reader(_bodies()[ks.FILE]).pages[146:186]]


def test_original_report_exact_grid_and_rendered_fixtures():
    rows = ks._validate(_bodies())
    assert len(rows) == 1260
    assert len({row["geo_id"] for row in rows}) == 105
    assert {row["year"] for row in rows} == set(range(2010, 2022))
    assert {row["datatype"] for row in rows} == {"projection"}
    values = {(row["geo_id"], row["year"]): row["value"] for row in rows}
    for gid, year, value in ks.FIXTURES:
        assert values[gid, year] == value


@pytest.mark.parametrize("name,gid,year,value", [
    ("Allen", "20001", 2010, 13448),
    ("Johnson", "20091", 2010, 552605),
    ("Johnson County", "20091", 2021, 614875),
    ("Greeley", "20071", 2010, 1218),
    ("Greeley", "20071", 2021, 873),
    ("Sedgwick", "20173", 2021, 503158),
    ("Bourbon", "20011", 2016, 14846),
    ("Wyandotte", "20209", 2021, 141796),
])
def test_county_names_and_identifiers(name, gid, year, value):
    result = server.get_forecast("KS", "county", name, "population", start_year=year, end_year=year)
    assert result == server.get_forecast("KS", "county", gid, "population", start_year=year, end_year=year)
    assert result["series"] == [{"year": year, "value": value, "datatype": "projection"}]


def test_old_horizon_unknown_base_and_correct_official_producer():
    result = server.get_forecast("KS", "county", "Johnson", "population")
    source = result["source"]
    assert len(result["series"]) == 12
    assert (source["vintage"], source["base_year"], source["horizon_year"]) == (ks.VINTAGE, None, 2021)
    assert source["url"] == ks.URL
    assert source["retrieved_at"] == "2026-10-02"
    assert "commissioned" in source["agency"] and "Moody" in source["agency"]
    assert "entire 2010-2021 horizon is in the past" in source["method_notes"]
    assert "No successor official projection was established" in source["method_notes"]
    assert "official state demographic authority or adoption was not established" in source["method_notes"]
    assert server.get_forecast("KS", "county", "Johnson", "population", start_year=2022)["status"] == "empty_range"
    assert server.get_forecast("KS", "county", "Johnson", "population", start_year=2009, end_year=2009)["status"] == "empty_range"


def test_complete_grid_no_generated_state_total_and_no_substituted_products():
    conn = store.connect()
    try:
        ks.verify(conn)
        assert conn.execute("SELECT COUNT(*) FROM observations WHERE state='KS' AND geo_level='state'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM observations WHERE state='KS' AND year=2006").fetchone()[0] == 0
    finally:
        conn.close()
    assert server.get_forecast("KS", "state", "Kansas", "population")["status"] == "coverage_unknown"
    assert server.get_forecast("KS", "place", "Wichita", "population")["status"] == "coverage_unknown"
    assert server.get_forecast("KS", "county", "Johnson", "households")["status"] == "coverage_unknown"
    assert server.get_forecast("KS", "county", "Johnson", "employment")["status"] == "coverage_unknown"
    assert server.get_components("KS", "Johnson")["status"] == "coverage_unknown"
    assert server.get_forecast("KS", "county", "Johnson", "population", scenario="high")["status"] == "error"


def test_catalog_distinguishes_old_loaded_data_from_newer_candidate():
    result = server.describe_source("KS")
    assert result["review"]["status"] == "never_reviewed"
    assert result["variables"]["population"]["county"]["load_status"] == "loaded"
    assert "2021" in result["current_vintage"] and "CEDBR" in result["current_vintage"]
    assert server.list_states()["states"]["KS"]["data_loaded"] is True
    assert len(result["sources_loaded"]) == 1


@pytest.mark.parametrize("body", [b"<html>server error</html>", b"%PDF-broken", b"[]"])
def test_soft_200_rejected(body):
    with pytest.raises(ValueError, match="original report PDF"):
        ks.parse(body)


@pytest.mark.parametrize("before,after,error", [
    ("2010 2011 2012", "2009 2011 2012", "year header"),
    ("Allen County", "Missing County", "unknown county"),
    ("13,448", "Suppressed", "invalid population"),
    ("13,448", "-13448", "invalid population"),
    ("13,448", "13,448.5", "invalid population"),
    ("Age 0 thru 4", "Age 5 thru 9", "age row"),
])
def test_changed_pdf_semantics_rejected(before, after, error):
    texts = _texts()
    texts[0] = texts[0].replace(before, after, 1)
    with pytest.raises(ValueError, match=error):
        ks.parse_texts(texts)


def test_missing_or_duplicate_county_total_rejected():
    texts = _texts()
    line = next(line for line in texts[0].splitlines() if line.strip().startswith("Total Population"))
    for changed, error in [(texts[0].replace(line, "", 1), "missing county total"),
                           (texts[0].replace(line, line + "\n" + line, 1), "duplicate")]:
        with pytest.raises(ValueError, match=error):
            ks.parse_texts([changed, *texts[1:]])


def test_complete_missing_county_block_rejected():
    texts = _texts()
    start, end = texts[0].index(" Allen County"), texts[0].index(" Anderson County")
    texts[0] = texts[0][:start] + texts[0][end:]
    with pytest.raises(ValueError, match="incomplete county"):
        ks.parse_texts(texts)


def test_bad_continuation_rejected():
    texts = _texts()
    texts[1] = texts[1].replace("Atchison County (cont'd)", "Allen County (cont'd)", 1)
    with pytest.raises(ValueError, match="invalid county continuation"):
        ks.parse_texts(texts)


def test_missing_appendix_page_rejected():
    with pytest.raises(ValueError, match="page count"):
        ks.parse_texts(_texts()[:-1])


@pytest.mark.parametrize("name", [name for name in ks.FILES if name.endswith(".html")])
def test_wrong_catalog_evidence_rejected(name):
    with pytest.raises(ValueError, match="invalid publisher evidence"):
        ks._validate_page(name, b"<html>Service Unavailable</html>")


def test_candidate_dashboard_edition_change_is_rejected():
    name = "cedbr_population_candidate_2026-10-02.html"
    body = _bodies()[name].replace(b"2024PopulationForecastDashboard", b"2099PopulationForecastDashboard")
    with pytest.raises(ValueError, match="candidate dashboard edition"):
        ks._validate_page(name, body)


def test_acquisition_reuses_immutable_originals(monkeypatch):
    before = (ks.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(ks.fetch, "get_bytes", lambda *_args: pytest.fail("unexpected network"))
    ks.acquire()
    assert before == (ks.RAW_DIR / "manifest.json").read_bytes()
