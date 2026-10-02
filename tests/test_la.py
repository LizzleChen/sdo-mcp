"""Original Louisiana state-commissioned 2009 archive and storm/scenario caveats."""
import io
from functools import lru_cache
from zipfile import ZipFile

import pytest
import xlrd

from sdo_mcp import server, store
from sdo_mcp.ingest import la


@lru_cache
def _body():
    return (la.RAW_DIR / la.FILE).read_bytes()


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("la-only") / "sdo.sqlite"
    conn = store.connect(path, create=True)
    store.init_db(conn)
    conn.execute("INSERT INTO geographies VALUES ('22','state','LA','Louisiana')")
    conn.executemany("INSERT INTO geographies VALUES (?,'county','LA',?)", la.roster().items())
    conn.executemany("INSERT INTO coverage VALUES ('LA','population',?,'available','Original selected state-commissioned product')", [("state",), ("county",)])
    la.load(conn)
    la.verify(conn)
    conn.close()
    return path


def _sheet():
    archive = ZipFile(io.BytesIO(_body()))
    return xlrd.open_workbook(file_contents=archive.read("Acadia Parish.xls")).sheet_by_name("Tables-Middle Series")


def test_exact_65_geography_six_year_three_scenario_grid():
    rows = la.parse(_body())
    expected = {(g, y, s) for g in ("22", *la.roster()) for y in la.YEARS for s in ("middle", "low", "high")}
    assert len(rows) == 1170 and {(r["geo_id"], r["year"], r["scenario"]) for r in rows} == expected
    assert all(r["datatype"] == ("estimate" if r["year"] == 2005 else "projection") for r in rows)
    result = server.get_forecast("LA", "state", "Louisiana", "population")
    assert result["status"] == "ok" and result["scenario"] == "middle"
    assert result["series"] == [dict(year=y, value=v, datatype="estimate" if y == 2005 else "projection")
        for y, v in zip(la.YEARS, (4510170, 4369760, 4477680, 4588310, 4699260, 4813420))]
    assert result == server.get_forecast("LA", "state", "22", "population")
    assert result["source"]["vintage"] == la.VINTAGE and result["source"]["horizon_year"] == 2030
    assert result["source"]["base_year"] == 2007


@pytest.mark.parametrize("geo,base,first,horizon", [
    ("East Baton Rouge", 2007, 433700, 421500),
    ("Tensas", 2005, 5660, 3990),
    ("Orleans", 2007, 247580, 256010),
    ("Jefferson Davis", 2005, 31200, 29720),
])
def test_independent_rendered_report_and_original_xls_checks(geo, base, first, horizon):
    result = server.get_forecast("LA", "county", geo, "population", 2010, 2030)
    assert result["status"] == "ok" and result["source"]["base_year"] == base
    assert result["series"][0] == dict(year=2010, value=first, datatype="projection")
    assert result["series"][-1] == dict(year=2030, value=horizon, datatype="projection")
    assert "29,720 versus report 29,190" in result["source"]["method_notes"]


def test_scenarios_are_migration_multipliers_not_ordered_population_ranges():
    values = {s: server.get_forecast("LA", "county", "Acadia", "population", 2030, 2030, scenario=s)["series"][0]["value"]
              for s in ("low", "middle", "high")}
    assert values == {"low": 63840, "middle": 59590, "high": 55360}
    high = server.get_forecast("LA", "county", "Orleans", "population", 2010, 2030, scenario="HIGH")
    assert high["series"][0]["value"] == 259970 and high["series"][-1]["value"] == 275180
    assert high["source"]["base_year"] == 2007
    assert "does not splice" in high["source"]["method_notes"]
    assert "January 2009 upward revisions" in high["source"]["method_notes"]


@pytest.mark.parametrize("start,end", [(2006, 2009), (2011, 2014), (2031, 2060)])
def test_no_fabricated_2007_interpolation_or_extension(start, end):
    result = server.get_forecast("LA", "state", "LA", "population", start, end)
    assert result["status"] == "empty_range"


def test_other_products_remain_unknown_and_invalid_scenario_rejected():
    for v in ("households", "employment"):
        assert server.get_forecast("LA", "state", "LA", v)["status"] == "coverage_unknown"
    assert server.get_components("LA", "LA")["status"] == "coverage_unknown"
    assert server.get_forecast("LA", "place", "New Orleans", "population")["status"] == "coverage_unknown"
    assert server.get_forecast("LA", "state", "LA", "population", scenario="recommended")["status"] == "error"
    assert server.get_forecast("LA", "county", "De Soto", "population")["status"] == "ok"


@pytest.mark.parametrize("row,col,value,error", [
    (0, 0, "Another Parish", "parish title"), (2, 0, "Detailed 2007", "year grid"),
    (3, 1, "Black", "column header"), (4, 11, "Households", "column header"),
    (5, 0, "0-5", "age grid"), (23, 10, "Total population", "total row"),
    (5, 11, -10, "nonnegative"), (5, 11, 4511, "rounded"),
    (5, 11, 4520, "summary cells"), (23, 11, 59300, "published total"),
])
def test_changed_headers_grid_and_numeric_cells_rejected(row, col, value, error):
    sheet = _sheet()
    sheet._cell_values[row][col] = value
    with pytest.raises(ValueError, match=error):
        la._parse_sheet(sheet, "Acadia Parish")


@pytest.mark.parametrize("value", ["", "NaN", "suppressed", float("nan"), float("inf")])
def test_missing_suppressed_nonfinite_population_rejected(value):
    sheet = _sheet()
    sheet._cell_values[23][11] = value
    with pytest.raises(ValueError, match="nonnegative"):
        la._parse_sheet(sheet, "Acadia Parish")


def test_archive_missing_or_unexpected_parish_rejected():
    for omit, extra in [("Winn Parish.xls", None), (None, "Unexpected Parish.xls")]:
        original = ZipFile(io.BytesIO(_body()))
        output = io.BytesIO()
        with ZipFile(output, "w") as edited:
            for info in original.infolist():
                if info.filename != omit:
                    edited.writestr(info, original.read(info.filename))
            if extra:
                edited.writestr(extra, b"bad")
        with pytest.raises(ValueError, match="archive members"):
            la.parse(output.getvalue())


@pytest.mark.parametrize("body", [b"<html>Service unavailable</html>", b"[]", b"PKbroken"])
def test_soft_200_wrong_archive_rejected(body):
    with pytest.raises(ValueError, match="unreadable original ZIP"):
        la.parse(body)


def test_original_government_cells_match_archive_and_reuse_is_offline(monkeypatch):
    before = (la.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(la.fetch, "get_bytes", lambda *_: pytest.fail("unexpected network"))
    la.acquire()
    assert (la.RAW_DIR / "manifest.json").read_bytes() == before


@pytest.mark.parametrize("failed_file", list(la.FILES))
def test_failed_source_archives_nothing(tmp_path, monkeypatch, failed_file):
    bodies = {url: (la.RAW_DIR / name).read_bytes() for name, url in la.FILES.items()}
    bodies[la.FILES[failed_file]] = b"<html>temporary error</html>"
    raw = tmp_path / "la"
    monkeypatch.setattr(la, "RAW_DIR", raw)
    monkeypatch.setattr(la.fetch, "get_bytes", lambda url: bodies[url])
    with pytest.raises(ValueError):
        la.acquire()
    assert not raw.exists()
