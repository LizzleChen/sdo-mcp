"""Kentucky source semantics, complete grids, and public forecast behavior."""

import io

import openpyxl
import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import ky, seed


def _body(variable):
    filename = ky.POPULATION_FILE if variable == "population" else ky.HOUSEHOLDS_FILE
    return (ky.RAW_DIR / filename).read_bytes()


def _parse(variable, body):
    return (ky.parse_population if variable == "population" else ky.parse_households)(body)


def _changed_workbook(variable, change):
    workbook = openpyxl.load_workbook(io.BytesIO(_body(variable)))
    try:
        change(workbook.active)
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()
    finally:
        workbook.close()


@pytest.mark.parametrize("variable,values", [
    ("population", [4505836, 4580143, 4641150, 4686067, 4721118, 4750369, 4785233]),
    ("households", [1797937, 1845354, 1883299, 1907132, 1922854, 1931902, 1944624]),
])
def test_state_series_and_source_metadata(variable, values):
    # Independently checked against the publisher's report, page 13.
    result = server.get_forecast("KY", "state", "Kentucky", variable)
    assert result["status"] == "ok"
    assert result["geo"] == {"level": "state", "id": "21", "name": "Kentucky"}
    assert result["scenario"] is None
    assert result["series"] == [
        {"year": year, "value": value, "datatype": "estimate" if year == 2020 else "projection"}
        for year, value in zip(range(2020, 2051, 5), values)
    ]
    source = result["source"]
    assert source["vintage"] == "2022 (released August 2022)"
    assert source["base_year"] == 2021  # Last estimate input, not the Census anchor.
    assert source["horizon_year"] == 2050
    filename = ky.POPULATION_FILE if variable == "population" else ky.HOUSEHOLDS_FILE
    entry = next(e for e in ky.fetch.read_manifest(ky.RAW_DIR) if e["file"] == filename)
    assert source["retrieved_at"] == entry["retrieved_at"]
    assert source["url"] == entry["source"]
    assert "2020" in source["method_notes"]
    assert "2021" in source["method_notes"]
    assert "August 2022" in source["citation"]


@pytest.mark.parametrize("variable,name,gid,value", [
    ("population", "Adair", "21001", 16291),
    ("population", "Jefferson", "21111", 838210),
    ("population", "Fayette", "21067", 398219),
    ("households", "Adair", "21001", 6775),
    ("households", "Allen", "21003", 8932),
])
def test_county_codes_names_and_report_fixtures(variable, name, gid, value):
    result = server.get_forecast("KY", "county", name, variable, start_year=2050)
    assert result == server.get_forecast("KY", "county", gid, variable, start_year=2050)
    assert result == server.get_forecast("KY", "county", gid[2:], variable, start_year=2050)
    assert result["geo"]["id"] == gid
    assert result["series"] == [{"year": 2050, "value": value, "datatype": "projection"}]


def test_complete_grids_and_state_county_reconciliation():
    conn = store.connect()
    try:
        ky.verify(conn)
        counties = conn.execute(
            "SELECT geo_id, variable, COUNT(*) FROM observations "
            "WHERE state='KY' AND geo_level='county' GROUP BY geo_id, variable"
        ).fetchall()
        assert len(counties) == 240
        assert all(row[2] == 7 for row in counties)
        assert {row[0] for row in conn.execute(
            "SELECT DISTINCT geo_level FROM observations WHERE state='KY'"
        )} == {"county", "state"}
    finally:
        conn.close()


@pytest.mark.parametrize("variable", ["population", "households"])
@pytest.mark.parametrize("start,end", [(2010, 2019), (2021, 2024), (2026, 2029), (2051, 2060)])
def test_no_interpolated_or_extended_years(variable, start, end):
    result = server.get_forecast("KY", "county", "Adair", variable, start_year=start, end_year=end)
    assert result["status"] == "empty_range"
    assert result["available_start_year"] == 2020
    assert result["available_end_year"] == 2050
    assert "series" not in result


def test_coverage_inventory_and_no_substituted_forecasts():
    for variable in ("population", "households"):
        result = server.get_forecast("KY", "place", "Louisville", variable)
        assert result["status"] == "not_published"
        assert "series" not in result
        assert {p["geo_level"] for p in result["closest_published"]} == {"state", "county"}
    for level, geo in (("state", "KY"), ("county", "Jefferson")):
        assert server.get_forecast("KY", level, geo, "employment")["status"] == "coverage_unknown"
        assert server.get_components("KY", geo)["status"] == "coverage_unknown"
    assert server.get_forecast("KY", "county", "KIPDA", "population")["status"] == "error"
    assert server.get_forecast("KY", "state", "KY", "population", scenario="high")["status"] == "error"
    summary = server.list_states()["states"]["KY"]
    for variable in ("population", "households"):
        assert summary["variables"][variable]["county"]["load_status"] == "loaded"
    description = server.describe_source("KY")
    assert description["variables"] == summary["variables"]
    assert description["review"]["status"] == "never_reviewed"
    assert description["review"]["interval_days"] == 90
    assert len(description["sources_loaded"]) == 2


def test_published_series_without_data_returns_not_loaded(tmp_path, monkeypatch):
    path = tmp_path / "seed.sqlite"
    conn = store.connect(path, create=True)
    try:
        store.init_db(conn)
        seed.load(conn)
    finally:
        conn.close()
    monkeypatch.setenv("SDO_DB", str(path))
    for variable in ("population", "households"):
        assert server.get_forecast("KY", "county", "Adair", variable)["status"] == "not_loaded"


@pytest.mark.parametrize("variable,cell,value,error", [
    ("population", "I1", "N2021", "header"),
    ("population", "B2", 1, "FIPS/name"),
    ("population", "C2", "Allen", "FIPS/name"),
    ("population", "D2", 2, "sex/age"),
    ("population", "D2", False, "sex/age"),
    ("population", "E2", True, "sex/age"),
    ("population", "E2", 19, "sex/age"),
    ("population", "E3", 1, "duplicate"),
    ("population", "I2", -1, "invalid population"),
    ("population", "I2", 1.5, "invalid population"),
    ("population", "I2", "NaN", "invalid population"),
    ("population", "I2", None, "invalid population"),
    ("population", "I2", True, "invalid population"),
    ("population", "F2", "error", "invalid population"),
    ("households", "E1", "HH2021", "header"),
    ("households", "B2", 21001, "code/name"),
    ("households", "C2", "Allen", "code/name"),
    ("households", "E2", -1, "invalid households"),
    ("households", "E2", 1.5, "invalid households"),
    ("households", "E2", None, "invalid households"),
    ("households", "E2", True, "invalid households"),
])
def test_parser_rejects_changed_semantics_and_invalid_values(variable, cell, value, error):
    with pytest.raises(ValueError, match=error):
        _parse(variable, _changed_workbook(variable, lambda s: setattr(s[cell], "value", value)))


@pytest.mark.parametrize("variable", ["population", "households"])
def test_parser_rejects_missing_row(variable):
    with pytest.raises(ValueError, match="row counts|geographies differ"):
        _parse(variable, _changed_workbook(variable, lambda s: s.delete_rows(2)))


def test_household_parser_rejects_duplicate_geography():
    def duplicate(sheet):
        sheet.append([cell.value for cell in sheet[2]])
    with pytest.raises(ValueError, match="duplicate"):
        ky.parse_households(_changed_workbook("households", duplicate))


@pytest.mark.parametrize("variable", ["population", "households"])
@pytest.mark.parametrize("body", [b"<html>Service unavailable</html>", b"PKnot a workbook", b"[]"])
def test_parser_rejects_soft_200_errors(variable, body):
    with pytest.raises(ValueError, match="readable"):
        _parse(variable, body)


def test_acquire_reuses_originals_without_network(monkeypatch):
    before = (ky.RAW_DIR / "manifest.json").read_bytes()
    def fail_network(*args, **kwargs):
        raise AssertionError("saved edition must not be downloaded again")
    monkeypatch.setattr(ky.fetch, "get_bytes", fail_network)
    ky.acquire()
    assert (ky.RAW_DIR / "manifest.json").read_bytes() == before


@pytest.mark.parametrize("failed_url", [ky.POPULATION_URL, ky.HOUSEHOLDS_URL, ky.CATALOG_URL, ky.CODEBOOK_URL])
def test_acquire_does_not_save_invalid_downloads(tmp_path, monkeypatch, failed_url):
    downloads = {
        ky.POPULATION_URL: _body("population"), ky.HOUSEHOLDS_URL: _body("households"),
        ky.CATALOG_URL: (ky.RAW_DIR / ky.CATALOG_FILE).read_bytes(),
        ky.CODEBOOK_URL: (ky.RAW_DIR / ky.CODEBOOK_FILE).read_bytes(),
    }
    raw = tmp_path / "ky"
    monkeypatch.setattr(ky, "RAW_DIR", raw)
    monkeypatch.setattr(ky.fetch, "get_bytes", lambda url: (
        b"<html>temporary error</html>" if url == failed_url else downloads[url]
    ))
    with pytest.raises(ValueError, match="readable|catalog"):
        ky.acquire()
    assert not raw.exists()


def test_catalog_rejects_changed_estimate_base():
    body = (ky.RAW_DIR / ky.CATALOG_FILE).read_bytes().replace(b"2021 Population Estimates", b"2022 Population Estimates")
    with pytest.raises(ValueError, match="2021 population estimates"):
        ky._validate_catalog(body)
