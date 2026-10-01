"""Massachusetts original grids, adjusted launch precision and public semantics."""
import io
import math
import zipfile
from functools import lru_cache

import pytest
from pypdf import PdfWriter

from sdo_mcp import server, store
from sdo_mcp.ingest import ma


@lru_cache
def _bodies():
    return {name: (ma.RAW_DIR / name).read_bytes() for name in ma.FILES}


def _total_grids():
    return {name: [list(row) for row in grid] for name, grid in ma._read_workbook(
        _bodies()[ma.FILE], ma.TOTAL_SHEETS,
        [name for name in ma.TOTAL_SHEETS if "Pop Totals" in name]).items()}


def _age_grids():
    return {name: [list(row) for row in grid] for name, grid in ma._read_workbook(
        _bodies()[ma.DETAIL_FILE], ma.DETAIL_SHEETS,
        [name for name in ma.DETAIL_SHEETS if name.startswith(("County Age", "State Age"))]).items()}


def test_exact_state_api_and_source_precision():
    result = server.get_forecast("MA", "state", "Massachusetts", "population")
    assert result["status"] == "ok"
    assert result["geo"] == dict(level="state", id="25", name="Massachusetts")
    assert result["scenario"] is None
    # Manually read original total-workbook XML; independently corroborated
    # by the separately published age/sex workbook, not generated fixtures.
    assert result["series"] == [dict(year=year, value=value,
                                     datatype="estimate" if year == 2020 else "projection")
        for year, value in zip(ma.YEARS, (7039146.791183238, 7078114, 7115199,
                                          7122364, 7102574, 7063672, 7021497), strict=True)]
    source = result["source"]
    assert (source["vintage"], source["base_year"], source["horizon_year"]) == (ma.VINTAGE, 2020, 2050)
    assert source["url"] == ma.URL
    assert source["retrieved_at"] == next(entry["retrieved_at"] for entry in ma.fetch.read_manifest(ma.RAW_DIR)
                                          if entry["file"] == ma.FILE)
    for marker in ("child-undercount", "Fractional 2020", "May 9, 20204", "October 16, 2024"):
        assert marker in source["method_notes"]


@pytest.mark.parametrize("name,gid,year,value", [
    ("Barnstable", "25001", 2020, 229215.99999999997),
    ("Barnstable", "25001", 2050, 169939), ("Franklin", "25011", 2020, 71122.2067),
    ("Middlesex", "25017", 2050, 1672330), ("Nantucket", "25019", 2050, 15555),
    ("Suffolk", "25025", 2050, 892646),
])
def test_county_api_names_fips_and_anchors(name, gid, year, value):
    result = server.get_forecast("MA", "county", name, "population", year, year)
    assert result == server.get_forecast("MA", "county", gid, "population", year, year)
    assert result["geo"] == dict(level="county", id=gid, name=name + " County")
    assert result["series"] == [dict(year=year, value=value,
                                     datatype="estimate" if year == 2020 else "projection")]


def test_complete_loaded_grid_flags_and_original_state_total():
    conn = store.connect()
    try:
        ma.verify(conn)
        rows = conn.execute("SELECT * FROM observations WHERE state='MA'").fetchall()
        assert len(rows) == 105
        assert {row["variable"] for row in rows} == {"population"}
        assert {row["geo_level"] for row in rows} == {"state", "county"}
        assert len({row["geo_id"] for row in rows if row["geo_level"] == "county"}) == 14
        for year in ma.YEARS:
            state = next(row["value"] for row in rows if row["geo_id"] == "25" and row["year"] == year)
            counties = math.fsum(row["value"] for row in rows if row["geo_level"] == "county" and row["year"] == year)
            assert math.isclose(state, counties, rel_tol=0, abs_tol=1e-8)
    finally:
        conn.close()


@pytest.mark.parametrize("start,end", [(2010, 2019), (2021, 2024), (2026, 2029), (2051, 2060)])
def test_no_generated_intermediate_or_extra_years(start, end):
    result = server.get_forecast("MA", "county", "Suffolk", "population", start, end)
    assert result["status"] == "empty_range"
    assert (result["available_start_year"], result["available_end_year"]) == (2020, 2050)


def test_published_municipal_and_unverified_products_are_honest():
    for level, name in (("place", "Boston"), ("county_subdivision", "Abington")):
        result = server.get_forecast("MA", level, name, "population")
        assert result["status"] == "not_loaded"
    for level, name in (("state", "MA"), ("county", "Suffolk")):
        for variable in ("households", "employment"):
            assert server.get_forecast("MA", level, name, variable)["status"] == "coverage_unknown"
        assert server.get_components("MA", name)["status"] == "coverage_unknown"
        assert server.get_forecast("MA", level, name, "population", scenario="high")["status"] == "error"
    description = server.describe_source("MA")
    assert description["variables"]["population"]["state"]["load_status"] == "loaded"
    assert description["variables"]["population"]["county"]["load_status"] == "loaded"
    assert description["variables"]["population"]["place"]["load_status"] == "not_loaded"
    assert description["variables"]["population"]["county_subdivision"]["load_status"] == "not_loaded"
    assert description["review"]["status"] == "never_reviewed"


def test_parser_independent_workbook_checks_and_exact_fixtures():
    rows = ma._validate_all(_bodies())
    assert len(rows) == 105
    values = {(row["geo_id"], row["year"]): row["value"] for row in rows}
    for gid, year, value in ma.FIXTURES:
        assert values[gid, year] == value
    assert all(row["datatype"] == ("estimate" if row["year"] == 2020 else "projection") for row in rows)


@pytest.mark.parametrize("body", [b"<html>Service unavailable</html>", b"PKbroken", b"[]"])
def test_soft_200_workbook_rejected(body):
    with pytest.raises(ValueError, match="readable XLSX workbook"):
        ma.parse(body)
    with pytest.raises(ValueError, match="readable XLSX workbook"):
        ma._validate_detail(body, [])


@pytest.mark.parametrize("change", ["sheets", "producer", "edition", "modified"])
def test_readable_wrong_workbook_rejected(change):
    # Mutate the original ZIP member so unrelated metadata remains unchanged;
    # saving through Excel libraries can reset modification dates and caches.
    member, old, new = {
        "sheets": ("xl/workbook.xml", b"RPA Crosswalk", b"Other"),
        "producer": ("docProps/core.xml", b"Denis McAuliffe", b"Other producer"),
        "edition": ("xl/sharedStrings.xml", b"Vintage 2024", b"Vintage 2025"),
        "modified": ("docProps/core.xml", b"2024-10-16T17:39:58Z", b"2025-10-16T17:39:58Z"),
    }[change]
    target = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(_bodies()[ma.FILE])) as original, zipfile.ZipFile(target, "w") as changed:
        for item in original.infolist():
            body = original.read(item.filename)
            if item.filename == member:
                assert old in body
                body = body.replace(old, new)
            changed.writestr(item, body)
    with pytest.raises(ValueError, match="sheets, producer or edition"):
        ma.parse(target.getvalue())


@pytest.mark.parametrize("column,value,error", [
    (0, "Unknown", "unknown county"), (0, "Berkshire", "mismatched county code"),
    (1, "02", "mismatched county code"), (4, None, "invalid population"),
    (4, True, "invalid population"), (4, -1, "invalid population"),
    (4, float("nan"), "invalid population"), (4, float("inf"), "invalid population"),
    (4, 0.5, "invalid population"), (4, "100", "invalid population"),
    (3, float("inf"), "invalid population"),
])
def test_changed_county_code_and_invalid_values_rejected(column, value, error):
    grids = _total_grids()
    grids["County Pop Totals 2010-2050"][1][column] = value
    with pytest.raises(ValueError, match=error):
        ma._parse_total_grids(grids)


def test_duplicate_county_rejected():
    grids = _total_grids()
    grids["County Pop Totals 2010-2050"][2] = list(grids["County Pop Totals 2010-2050"][1])
    with pytest.raises(ValueError, match="duplicate county"):
        ma._parse_total_grids(grids)


@pytest.mark.parametrize("change", ["header", "missing_row", "missing_column", "extra_column", "extra_row"])
def test_changed_total_grid_shape_rejected(change):
    grids = _total_grids()
    grid = grids["County Pop Totals 2010-2050"]
    if change == "header":
        grid[0][4] = 2026
    elif change == "missing_row":
        grid.pop()
    elif change == "missing_column":
        grid[1].pop()
    elif change == "extra_row":
        grid.append(list(grid[-1]))
    else:
        grid[1].append(0)
    with pytest.raises(ValueError, match="header or shape"):
        ma._parse_total_grids(grids)


@pytest.mark.parametrize("change", ["code", "name", "county", "county_code", "rpa"])
def test_changed_municipal_geographies_rejected(change):
    grids = _total_grids()
    row = grids["CityTown Pop Totals 2010-2050"][1]
    row[{"code": 1, "name": 0, "county": 2, "county_code": 3, "rpa": 4}[change]] = {
        "code": 2, "name": "Acton", "county": "Unknown", "county_code": "99", "rpa": "Unknown"}[change]
    with pytest.raises(ValueError, match="municipal geography/code"):
        ma._parse_total_grids(grids)


@pytest.mark.parametrize("sheet,column,error", [
    ("State Pop Totals 2010-2050", 3, "county/state"),
    ("CityTown Pop Totals 2010-2050", 7, "municipal/county"),
    ("RPA Pop Totals 2010-2050", 3, "municipal/RPA"),
])
def test_changed_source_totals_fail_reconciliation(sheet, column, error):
    grids = _total_grids()
    grids[sheet][1][column] += 1
    with pytest.raises(ValueError, match=error):
        ma._parse_total_grids(grids)


def test_consistently_changed_totals_must_match_independent_workbook():
    grids = _total_grids()
    # Change a municipality and all its parents consistently; the primary
    # workbook reconciles, but the independently published detail still fails.
    grids["CityTown Pop Totals 2010-2050"][1][7] += 1  # Abington 2025
    for sheet, name, column in (("County Pop Totals 2010-2050", "Plymouth", 4),
                                ("RPA Pop Totals 2010-2050", "OCPC", 3),
                                ("State Pop Totals 2010-2050", "Massachusetts", 3)):
        next(row for row in grids[sheet][1:] if row[0] == name)[column] += 1
    rows = ma._parse_total_grids(grids)
    with pytest.raises(ValueError, match="independent age/sex workbook"):
        ma._validate_detail(_bodies()[ma.DETAIL_FILE], rows)


@pytest.mark.parametrize("column,value,error", [
    (0, "Unknown", "unknown age/sex geography"), (1, "99", "county code"),
    (2, 19, "changed age/sex category"), (3, "0-5", "changed age/sex category"),
    (4, "Unknown", "changed age/sex category"), (7, 0.5, "invalid population"),
])
def test_changed_age_sex_geographies_and_categories_rejected(column, value, error):
    grids = _age_grids()
    grids["County Age_Sex 2010-2050"][1][column] = value
    with pytest.raises(ValueError, match=error):
        ma._validate_age_grids(grids, [])


def test_duplicate_age_sex_category_rejected():
    grids = _age_grids()
    grids["County Age_Sex 2010-2050"][2] = list(grids["County Age_Sex 2010-2050"][1])
    with pytest.raises(ValueError, match="duplicate age/sex"):
        ma._validate_age_grids(grids, [])


def test_changed_age_sex_sum_rejected():
    grids = _age_grids()
    grids["County Age_Sex 2010-2050"][1][7] += 1
    with pytest.raises(ValueError, match="age/sex cells do not reconcile"):
        ma._validate_age_grids(grids, [])


def test_changed_state_age_control_rejected():
    grids = _age_grids()
    grids["State Age 2010-2050"][1][5] += 1
    grids["State Age_Sex 2010-2050"][1][6] += 1
    with pytest.raises(ValueError, match="county/state age/sex"):
        ma._validate_age_grids(grids, [])


@pytest.mark.parametrize("page,old,new", [
    (0, "Vintage 2024", "Vintage 2025"), (0, "May 9, 2024", "May 9, 2025"),
    (19, "2020 Decennial Census", "2010 Decennial Census"),
    (30, "initial launch year is 2020", "initial launch year is 2025"),
])
def test_changed_method_edition_or_boundary_rejected(monkeypatch, page, old, new):
    pages = ma._method_pages(_bodies()[ma.METHOD_FILE])
    assert old in pages[page]
    pages[page] = pages[page].replace(old, new)
    monkeypatch.setattr(ma, "_method_pages", lambda _: pages)
    with pytest.raises(ValueError, match="edition, producer or launch boundary"):
        ma._validate_method(b"ignored in favor of patched extracted pages")


def test_wrong_readable_method_pdf_rejected():
    writer = PdfWriter()
    writer.add_blank_page(612, 792)
    body = io.BytesIO()
    writer.write(body)
    with pytest.raises(ValueError, match="page count"):
        ma._validate_method(body.getvalue())


def test_catalog_product_links_and_soft_200_error_checked():
    body = _bodies()[ma.CATALOG_FILE]
    ma._validate_catalog(body)
    for bad in (b"<html>Temporary error</html>", body.replace(b"/media/2441/download", b"/media/9999/download")):
        with pytest.raises(ValueError, match="invalid publisher catalog"):
            ma._validate_catalog(bad)


def test_snapshot_reuse_preserves_retrieval_and_original_bytes(monkeypatch):
    before = {name: (ma.RAW_DIR / name).read_bytes() for name in (*ma.FILES, "manifest.json")}
    monkeypatch.setattr(ma.fetch, "get_bytes", lambda _: pytest.fail("unexpected network call"))
    ma.acquire()
    assert {name: (ma.RAW_DIR / name).read_bytes() for name in before} == before


@pytest.mark.parametrize("name", list(ma.FILES))
def test_invalid_download_archives_nothing(tmp_path, monkeypatch, name):
    bodies = dict(_bodies())
    bodies[name] = b"<html>Temporary error</html>"
    by_url = {url: bodies[file] for file, url in ma.FILES.items()}
    raw = tmp_path / "ma"
    monkeypatch.setattr(ma, "RAW_DIR", raw)
    monkeypatch.setattr(ma.fetch, "get_bytes", lambda url: by_url[url])
    with pytest.raises(ValueError, match="readable PDF|readable XLSX workbook|invalid publisher catalog"):
        ma.acquire()
    assert not raw.exists()


def test_incomplete_saved_manifest_rejected_offline(tmp_path, monkeypatch):
    raw = tmp_path / "ma"
    raw.mkdir()
    (raw / "manifest.json").write_text("[]\n")
    monkeypatch.setattr(ma, "RAW_DIR", raw)
    monkeypatch.setattr(ma.fetch, "get_bytes", lambda _: pytest.fail("unexpected network call"))
    with pytest.raises(ValueError, match="incomplete saved manifest"):
        ma.acquire()


def test_tampered_snapshot_rejected_without_overwriting(tmp_path, monkeypatch):
    raw = tmp_path / "ma"
    raw.mkdir()
    for name in (*ma.FILES, "manifest.json"):
        (raw / name).write_bytes((ma.RAW_DIR / name).read_bytes())
    (raw / ma.FILE).write_bytes(b"changed original")
    monkeypatch.setattr(ma, "RAW_DIR", raw)
    monkeypatch.setattr(ma.fetch, "get_bytes", lambda _: pytest.fail("unexpected network call"))
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        ma.acquire()
    assert (raw / ma.FILE).read_bytes() == b"changed original"
