"""Illinois PDF extraction, source semantics and public forecast behavior."""

import io
from functools import lru_cache

import pytest
from pypdf import PdfReader, PdfWriter

from sdo_mcp import server, store
from sdo_mcp.ingest import il, seed


@lru_cache
def _pdf():
    return (il.RAW_DIR / il.FILE).read_bytes()


@lru_cache
def _pages():
    reader = PdfReader(io.BytesIO(_pdf()))
    return {i: reader.pages[i].extract_text() for i in (0, 3, *il.TABLE_PAGES)}


def _tables():
    return [_pages()[i] for i in il.TABLE_PAGES]


def test_original_pdf_and_database_match_rendered_table3():
    assert len(il.parse(_pdf())) == 412
    conn = store.connect()
    try:
        il.verify(conn)
    finally:
        conn.close()
    result = server.get_forecast("IL", "state", "Illinois", "population")
    assert result["status"] == "ok"
    assert result["geo"] == {"level": "state", "id": "17", "name": "Illinois"}
    assert result["scenario"] is None
    # Read independently from rendered Table 3 (printed page 8). Table 1
    # differs in 2025/2030; April Census 12,812,508 must never replace July.
    assert result["series"] == [
        {"year": 2020, "value": 12785245, "datatype": "estimate"},
        {"year": 2025, "value": 12780256, "datatype": "projection"},
        {"year": 2030, "value": 12775248, "datatype": "projection"},
        {"year": 2035, "value": 12770245, "datatype": "projection"},
    ]
    source = result["source"]
    assert source["vintage"] == "2023 edition (released May 2024)"
    assert source["base_year"] == 2020
    assert source["horizon_year"] == 2035
    entry = next(e for e in il.fetch.read_manifest(il.RAW_DIR) if e["file"] == il.FILE)
    assert source["retrieved_at"] == entry["retrieved_at"]
    assert source["url"] == entry["source"]
    assert "Table 3" in source["citation"]
    assert "11 lower in 2025 and 3 lower in 2030" in source["method_notes"]
    assert "April 1, 2020" in source["method_notes"]


@pytest.mark.parametrize("name,gid,value", [
    ("Cook", "17031", 4900208), ("Hardin", "17069", 3076),
    ("De Witt", "17039", 13679), ("Jo Daviess", "17085", 20533),
    ("St. Clair", "17163", 246323), ("Woodford", "17203", 40490),
])
def test_names_and_fips_from_all_three_rendered_pages(name, gid, value):
    result = server.get_forecast("IL", "county", name, "population", start_year=2035)
    assert result == server.get_forecast("IL", "county", gid, "population", start_year=2035)
    assert result == server.get_forecast("IL", "county", gid[2:], "population", start_year=2035)
    assert result["geo"]["id"] == gid
    assert result["series"] == [{"year": 2035, "value": value, "datatype": "projection"}]


def test_ambiguous_unknown_and_invalid_scenario():
    ambiguous = server.get_forecast("IL", "county", "Mc", "population")
    assert ambiguous["status"] == "error"
    assert {g["geo_id"] for g in ambiguous["candidates"]} == {"17109", "17111", "17113"}
    assert server.get_forecast("IL", "county", "Chicago", "population")["status"] == "error"
    assert server.get_forecast("IL", "county", "18031", "population")["status"] == "error"
    assert server.get_forecast("IL", "state", "IL", "population", scenario="high")["status"] == "error"


@pytest.mark.parametrize("start,end", [(2010, 2019), (2021, 2024), (2026, 2029), (2031, 2034), (2036, 2050)])
def test_no_interpolated_or_extended_years(start, end):
    result = server.get_forecast("IL", "county", "Cook", "population", start_year=start, end_year=end)
    assert result["status"] == "empty_range"
    assert result["available_start_year"] == 2020
    assert result["available_end_year"] == 2035
    assert "series" not in result


def test_published_deferred_and_unknown_products():
    chicago = server.get_forecast("IL", "place", "Chicago", "population")
    assert chicago["status"] == "not_loaded"
    assert "Chicago" in chicago["reason"]
    assert "series" not in chicago
    for geo in ("IL", "Cook"):
        components = server.get_components("IL", geo)
        assert components["status"] == "pdf_only"
        assert "series" not in components
    for variable in ("households", "employment"):
        assert server.get_forecast("IL", "county", "Cook", variable)["status"] == "coverage_unknown"
    # Absence of publication evidence is not a not_published claim.
    assert server.get_forecast("IL", "msa", "Chicago", "population")["status"] == "coverage_unknown"
    description = server.describe_source("IL")
    summary = server.list_states()["states"]["IL"]
    assert summary["variables"] == description["variables"]
    for level in ("state", "county"):
        assert summary["variables"]["population"][level]["load_status"] == "loaded"
        assert summary["variables"]["components"][level]["load_status"] == "not_loaded"
    assert summary["variables"]["population"]["place"]["load_status"] == "not_loaded"
    assert description["review"]["status"] == "never_reviewed"
    assert description["review"]["interval_days"] == 90
    assert len(description["sources_loaded"]) == 1


def test_seed_only_returns_not_loaded(tmp_path, monkeypatch):
    path = tmp_path / "seed.sqlite"
    conn = store.connect(path, create=True)
    try:
        store.init_db(conn)
        seed.load(conn)
    finally:
        conn.close()
    monkeypatch.setenv("SDO_DB", str(path))
    assert server.get_forecast("IL", "county", "Cook", "population")["status"] == "not_loaded"


@pytest.mark.parametrize("old,new,error", [
    ("April 1, 2020 2020 2025 2030 2035", "April 1, 2020 2021 2025 2030 2035", "header"),
    ("Census1 Estimate1 Projections", "Estimate1 Census1 Projections", "header"),
    ("as of July 1", "as of April 1", "header"),
    ("Adams 65,737 65,530 64,025 63,004 62,292", "", "incomplete"),
    ("Adams", "Chicago", "unknown geography"),
    ("Adams", "Illinois", "duplicate"),
    ("65,530", "-1", "invalid integer"),
    ("65,530", "1.5", "invalid integer"),
    ("65,530", "NaN", "invalid integer"),
    ("65,530", "(D)", "invalid integer"),
    ("65,530", "", "malformed|unknown geography"),
    ("65,530", "6,5530", "invalid integer"),
    ("65,530", "65,531", "totals differ"),
])
def test_rejects_corrupted_extraction(old, new, error):
    tables = _tables()
    assert old in tables[0]
    tables[0] = tables[0].replace(old, new, 1)
    with pytest.raises(ValueError, match=error):
        il._parse_table3(tables)


def test_rejects_missing_page_and_attribution():
    with pytest.raises(ValueError, match="all three"):
        il._parse_table3(_tables()[:2])
    tables = _tables()
    tables[2] = tables[2].replace("Source: Illinois Department of Public Health, 2023", "")
    with pytest.raises(ValueError, match="footnote"):
        il._parse_table3(tables)


@pytest.mark.parametrize("page,old,new", [
    (0, "2023 Edition", "2024 Edition"), (0, "May 2024", "May 2025"),
    (3, "July 1, 2020 population estimates", "July 1, 2021 population estimates"),
])
def test_rejects_changed_edition_or_base(page, old, new):
    pages = dict(_pages())
    assert old in pages[page]
    pages[page] = pages[page].replace(old, new)
    with pytest.raises(ValueError, match="edition|base year"):
        il._validate_edition(pages[0], pages[3])


@pytest.mark.parametrize("body", [b"<html>Service unavailable</html>", b"%PDF-broken", b"[]"])
def test_rejects_soft_200_errors(body):
    with pytest.raises(ValueError, match="readable PDF"):
        il.parse(body)


def test_rejects_wrong_but_readable_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(ValueError, match="page count"):
        il.parse(output.getvalue())


def test_acquire_reuses_snapshots_without_network(monkeypatch):
    before = (il.RAW_DIR / "manifest.json").read_bytes()
    def fail_network(*args, **kwargs):
        raise AssertionError("saved edition must not be fetched again")
    monkeypatch.setattr(il.fetch, "get_bytes", fail_network)
    il.acquire()
    assert (il.RAW_DIR / "manifest.json").read_bytes() == before


@pytest.mark.parametrize("failed_url", [il.URL, il.CATALOG_URL, il.POPULATION_URL])
def test_acquire_saves_nothing_when_any_download_is_invalid(tmp_path, monkeypatch, failed_url):
    downloads = {il.URL: _pdf()}
    downloads.update({url: (il.RAW_DIR / name).read_bytes() for name, url, _ in il.REFERENCES})
    target = tmp_path / "il"
    monkeypatch.setattr(il, "RAW_DIR", target)
    monkeypatch.setattr(il.fetch, "get_bytes", lambda url: (
        b"<html>temporary error</html>" if url == failed_url else downloads[url]
    ))
    with pytest.raises(ValueError, match="readable PDF|catalog"):
        il.acquire()
    assert not target.exists()
