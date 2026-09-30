"""Checked New Hampshire PDF extraction and public forecast semantics."""
import io
from functools import lru_cache

import pytest
from pypdf import PdfReader, PdfWriter

from sdo_mcp import server, store
from sdo_mcp.ingest import nh


@lru_cache
def _body():
    return (nh.RAW_DIR / nh.FILE).read_bytes()


@lru_cache
def _pages():
    reader = PdfReader(io.BytesIO(_body()))
    return {i: reader.pages[i].extract_text() for i in (0, 1, nh.TABLE_PAGE, *nh.CHECK_PAGES)}


def test_exact_state_points_and_source_metadata():
    result = server.get_forecast("NH", "state", "New Hampshire", "population")
    assert result["status"] == "ok"
    assert result["series"] == [
        dict(year=year, value=value, datatype="estimate" if year == 2020 else "projection")
        for year, value in zip(nh.YEARS, (1377533, 1430601, 1473286, 1501045, 1511770, 1509955, 1501909))
    ]
    source = result["source"]
    assert source["vintage"] == "September 2022"
    assert source["base_year"] == 2020
    assert source["horizon_year"] == 2050
    assert source["url"] == nh.URL
    assert source["retrieved_at"] == next(e["retrieved_at"] for e in nh.fetch.read_manifest(nh.RAW_DIR) if e["file"] == nh.FILE)
    assert "Table 1" in source["citation"]
    assert "one above its county sum" in source["method_notes"]


@pytest.mark.parametrize("name,gid,year,value", [
    ("Belknap", "33001", 2050, 70103), ("Carroll", "33003", 2020, 50111),
    ("Coos", "33007", 2050, 27428), ("Hillsborough", "33011", 2050, 471369),
    ("Strafford", "33017", 2050, 149435), ("Sullivan", "33019", 2050, 42141),
])
def test_county_names_fips_and_rendered_anchors(name, gid, year, value):
    result = server.get_forecast("NH", "county", name, "population", year, year)
    assert result == server.get_forecast("NH", "county", gid, "population", year, year)
    assert result["series"] == [dict(year=year, value=value, datatype="estimate" if year == 2020 else "projection")]


def test_complete_grid_and_deferred_products():
    conn = store.connect()
    try:
        nh.verify(conn)
    finally:
        conn.close()
    assert server.get_forecast("NH", "place", "Concord", "population")["status"] == "not_loaded"
    assert server.get_components("NH", "Carroll")["status"] == "pdf_only"
    for variable in ("households", "employment"):
        assert server.get_forecast("NH", "county", "Carroll", variable)["status"] == "coverage_unknown"
    assert server.describe_source("NH")["review"]["status"] == "never_reviewed"


@pytest.mark.parametrize("start,end", [(2021, 2024), (2026, 2029), (2051, 2060)])
def test_no_generated_years(start, end):
    result = server.get_forecast("NH", "state", "NH", "population", start, end)
    assert result["status"] == "empty_range"
    assert result["available_start_year"] == 2020
    assert result["available_end_year"] == 2050


def test_table_and_appendix_match_all_values():
    rows = nh._parse_table(_pages()[nh.TABLE_PAGE])
    check = nh._parse_appendix([_pages()[i] for i in nh.CHECK_PAGES])
    assert len(rows) == len(check) == 77
    assert all(check[r["geo_id"], r["year"]] == r["value"] for r in rows)


@pytest.mark.parametrize("old,new,error", [
    ("Census 2025 2030 2035 2040 2045 2050", "Estimate 2025 2030 2035 2040 2045 2050", "header"),
    ("Belknap", "Unknown", "unknown geography"),
    ("Belknap", "Carroll", "duplicate"),
    ("63,705", "-1", "invalid integer"), ("63,705", "NaN", "invalid integer"),
    ("63,705", "63.705", "invalid integer"), ("63,705", "63,706", "difference"),
    ("1,473,286", "1,473,285", "difference"),
])
def test_corrupted_table_rejected(old, new, error):
    text = _pages()[nh.TABLE_PAGE]
    assert old in text
    with pytest.raises(ValueError, match=error):
        nh._parse_table(text.replace(old, new, 1))


def test_empty_table_rejected():
    with pytest.raises(ValueError, match="Table 1 header"):
        nh._parse_table("")


def test_missing_rows_and_appendix_totals_rejected():
    text = _pages()[nh.TABLE_PAGE]
    text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("Sullivan "))
    with pytest.raises(ValueError, match="incomplete"):
        nh._parse_table(text)
    pages = [_pages()[i] for i in nh.CHECK_PAGES]
    pages[0] = pages[0].replace("1,501,909", "1,501,910", 1)
    with pytest.raises(ValueError, match="sex totals"):
        nh._parse_appendix(pages)
    with pytest.raises(ValueError, match="incomplete"):
        nh._parse_appendix(pages[:-1])


@pytest.mark.parametrize("page,old,new", [(0,"September 2022","September 2023"),
                                        (1,"2020 U.S. Census","2010 U.S. Census")])
def test_changed_edition_and_base_rejected(page, old, new):
    pages = dict(_pages())
    pages[page] = pages[page].replace(old, new)
    with pytest.raises(ValueError, match="edition.*base year"):
        nh._validate_edition(pages[0], pages[1])


@pytest.mark.parametrize("body", [b"<html>Service unavailable</html>", b"%PDF-broken", b"[]"])
def test_soft_200_rejected(body):
    with pytest.raises(ValueError, match="readable PDF"):
        nh.parse(body)


def test_wrong_readable_pdf_rejected():
    writer = PdfWriter()
    writer.add_blank_page(612, 792)
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(ValueError, match="page count"):
        nh.parse(output.getvalue())


def test_reuse_snapshots_without_network(monkeypatch):
    before = (nh.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(nh.fetch, "get_bytes", lambda *_: pytest.fail("unexpected network call"))
    nh.acquire()
    assert (nh.RAW_DIR / "manifest.json").read_bytes() == before


@pytest.mark.parametrize("failed_file", list(nh.FILES))
def test_failed_download_archives_nothing(tmp_path, monkeypatch, failed_file):
    bodies = {url: (nh.RAW_DIR / name).read_bytes() for name, url in nh.FILES.items()}
    bodies[nh.FILES[failed_file]] = b"<html>temporary error</html>"
    raw = tmp_path / "nh"
    monkeypatch.setattr(nh, "RAW_DIR", raw)
    monkeypatch.setattr(nh.fetch, "get_bytes", lambda url: bodies[url])
    with pytest.raises(ValueError, match="readable PDF|publisher catalog"):
        nh.acquire()
    assert not raw.exists()
