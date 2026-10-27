"""New Jersey's old projection edition, state models, exact county totals and guards."""

import io
import zipfile
from xml.etree import ElementTree as ET

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import nj


def _body(name):
    return (nj.RAW_DIR / name).read_bytes()


def _changed_cell(name, cell, value):
    """Change one original XML cell, preserving the publisher's edition metadata."""
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(_body(name))) as old, zipfile.ZipFile(output, "w") as new:
        for item in old.infolist():
            body = old.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                root = ET.fromstring(body)
                ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
                node = root.find(f".//{ns}c[@r='{cell}']")
                if node is None:
                    row_number = cell.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                    row = root.find(f".//{ns}row[@r='{row_number}']")
                    assert row is not None
                    node = ET.SubElement(row, ns + "c", r=cell)
                for child in list(node):
                    node.remove(child)
                if isinstance(value, str):
                    node.set("t", "inlineStr")
                    ET.SubElement(ET.SubElement(node, ns + "is"), ns + "t").text = value
                elif value is not None:
                    node.attrib.pop("t", None)
                    ET.SubElement(node, ns + "v").text = str(value)
                else:
                    node.attrib.pop("t", None)
                body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            new.writestr(item, body)
    return output.getvalue()


def _changed_zip(name, target, change):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(_body(name))) as old, zipfile.ZipFile(output, "w") as new:
        for item in old.infolist():
            body = old.read(item.filename)
            if item.filename == target:
                body = change(body)
            new.writestr(item, body)
    return output.getvalue()


@pytest.mark.parametrize("scenario,values", [
    ("economic_demographic", (8938200, 9132700, 9338000, 9531200, 9733400)),
    ("zero_migration", (8938200, 9128200, 9258000, 9326000, 9342500)),
    ("historical_migration", (8938200, 9109800, 9263100, 9402600, 9522200)),
    ("linear_regression", (8938200, 9438900, 9750900, 10062800, 10374700)),
])
def test_state_models_published_points_and_old_base(scenario, values):
    result = server.get_forecast("NJ", "state", "New Jersey", "population", scenario=scenario)
    assert result["status"] == "ok"
    assert result["scenario"] == scenario
    assert result["series"] == [
        {"year": year, "value": value, "datatype": "estimate" if year == 2014 else "projection"}
        for year, value in zip(nj.YEARS, values)
    ]
    source = result["source"]
    assert (source["base_year"], source["horizon_year"], source["vintage"]) == (2014, 2034, nj.VINTAGE)
    assert source["url"] == nj.STATE_URL
    assert source["retrieved_at"] == next(e["retrieved_at"] for e in nj.fetch.read_manifest(nj.RAW_DIR)
                                          if e["file"] == nj.STATE_FILE)
    assert "9,531,200" in source["method_notes"]
    assert "9,530,900" in source["method_notes"]
    assert "Census Vintage 2014" in source["method_notes"]
    assert "not a jobs forecast" in source["method_notes"]
    assert server.get_forecast("NJ", "state", "34", "population")["scenario"] == "economic_demographic"


@pytest.mark.parametrize("name,gid,values", [
    ("Bergen", "34003", (933600, 967500, 998700, 1031500, 1065500)),
    ("Cape May", "34009", (95300, 94100, 94400, 93300, 93400)),
    ("Hudson", "34017", (669100, 708100, 718700, 747400, 766500)),
    ("Salem", "34033", (64700, 63000, 62600, 61000, 59800)),
])
def test_county_names_fips_and_single_preferred_model(name, gid, values):
    result = server.get_forecast("NJ", "county", name, "population")
    assert result == server.get_forecast("NJ", "county", gid, "population")
    assert result["scenario"] is None
    assert result["series"] == [
        {"year": year, "value": value, "datatype": "estimate" if year == 2014 else "projection"}
        for year, value in zip(nj.YEARS, values)
    ]
    assert result["source"]["url"] == nj.COUNTY_URL
    assert server.get_forecast("NJ", "county", gid, "population", scenario="economic_demographic")["status"] == "error"


def test_exact_grid_unknown_products_and_geography_specific_scenarios():
    for year in (2010, 2015, 2020, 2025, 2035):
        assert server.get_forecast("NJ", "state", "34", "population", year, year)["status"] == "empty_range"
    for variable in ("households", "employment"):
        for level, name in (("state", "New Jersey"), ("county", "Bergen")):
            assert server.get_forecast("NJ", level, name, variable)["status"] == "coverage_unknown"
    assert server.get_forecast("NJ", "place", "Newark", "population")["status"] == "coverage_unknown"
    assert server.get_components("NJ", "New Jersey")["status"] == "coverage_unknown"
    assert server.get_forecast("NJ", "state", "New Jersey", "population", scenario="low")["status"] == "error"
    metadata = server.list_states()["states"]["NJ"]
    assert metadata["scenario_geo_levels"] == ["state"]
    assert metadata["default_scenario"] == "economic_demographic"
    assert metadata["variables"]["population"]["county"]["load_status"] == "loaded"
    description = server.describe_source("NJ")
    assert description["review"]["status"] == "never_reviewed"
    assert "labor force" in description["employment_note"].lower()


def test_complete_grid_preserves_state_county_discrepancy_and_rounding():
    conn = store.connect()
    try:
        nj.verify(conn)
        for year, expected_difference in zip(nj.YEARS, (100, 0, -300, 300, 100)):
            state = conn.execute("SELECT value FROM observations WHERE state='NJ' AND geo_level='state' "
                                 "AND year=? AND scenario='economic_demographic'", (year,)).fetchone()[0]
            counties = conn.execute("SELECT SUM(value) FROM observations WHERE state='NJ' "
                                    "AND geo_level='county' AND year=?", (year,)).fetchone()[0]
            assert state - counties == expected_difference
        assert conn.execute("SELECT COUNT(*) FROM sources WHERE state='NJ'").fetchone()[0] == 2
        assert conn.execute("SELECT DISTINCT variable FROM observations WHERE state='NJ'").fetchall()[0][0] == "population"
    finally:
        conn.close()


def test_parser_grid_and_independent_publisher_charts():
    bodies = {name: _body(name) for name in nj.FILES}
    rows = nj._validate_all(bodies)
    assert len(rows) == 125
    assert len(nj.parse_state_workbook(bodies[nj.STATE_FILE])) == 20
    assert len(nj.parse_county_workbook(bodies[nj.COUNTY_FILE_NAME])) == 105
    checks = nj.parse_report(bodies[nj.REPORT_FILE])
    assert len(checks) == 45
    selected = {(r["geo_id"], r["year"]): r["value"] for r in rows
                if r.get("scenario", "economic_demographic") == "economic_demographic"}
    assert all(selected[key] == value for key, value in checks.items())
    assert checks["34", 2029] == 9531200
    assert checks["34033", 2034] == 59800


@pytest.mark.parametrize("parser", [nj.parse_state_workbook, nj.parse_report, nj._doc_text])
@pytest.mark.parametrize("body", [b"<html>Temporarily unavailable</html>", b"[]", b"PKbroken"])
def test_soft_200_data_rejected(parser, body):
    with pytest.raises(ValueError, match="readable"):
        parser(body)


@pytest.mark.parametrize("cell,value,error", [
    ("A1", "Table 1. Labor Force Projections", "state title"),
    ("C5", "Projections ", "estimate/projection"),
    ("E6", 2025, "year grid"),
    ("A12", "Economic-Demographic", "duplicate state model"),
    ("A12", "Invented Model", "unknown or duplicate"),
    ("A12", None, "unknown or duplicate"),
    ("C9", 8938300, "historical anchors"),
    ("D9", -1, "invalid population"),
    ("D9", 9132700.5, "invalid population"),
    ("D9", "9132700", "invalid population"),
    ("D9", None, "invalid population"),
    ("D9", 9132701, "rounding"),
    ("A20", "No preferred model", "preferred-model footnote"),
])
def test_changed_state_semantics_rejected(cell, value, error):
    with pytest.raises(ValueError, match=error):
        nj.parse_state_workbook(_changed_cell(nj.STATE_FILE, cell, value))


@pytest.mark.parametrize("cell,value,error", [
    ("A1", "Table 1. Labor Force Projections", "county title"),
    ("C3", "Projections ", "estimate/projection"),
    ("F4", 2025, "year grid"),
    ("A9", "Atlantic", "duplicate county geography"),
    ("A9", "Invented County", "unknown or duplicate"),
    ("A9", None, "unknown or duplicate"),
    ("D9", 1, "extra county value"),
    ("H9", -1, "invalid population"),
    ("H9", 1065500.5, "invalid population"),
    ("H9", "1065500", "invalid population"),
    ("H9", None, "invalid population"),
    ("H9", 1065501, "rounding"),
    ("H9", 1065600, "reconciliation"),
    ("H198", 100, "outside published county table"),
    ("A36", "No rounding", "county title"),
])
def test_changed_county_semantics_rejected(cell, value, error):
    with pytest.raises(ValueError, match=error):
        nj.parse_county_workbook(_changed_cell(nj.COUNTY_FILE_NAME, cell, value))


def test_valid_number_changed_in_state_table_rejected_by_independent_chart():
    bodies = {name: _body(name) for name in nj.FILES}
    # Both source workbooks agree after this mutation; the independently
    # published summary chart still repeats the preferred state 2019 total.
    bodies[nj.STATE_FILE] = _changed_cell(nj.STATE_FILE, "D9", 9132800)
    bodies[nj.COUNTY_FILE_NAME] = _changed_zip(
        nj.COUNTY_FILE_NAME, "xl/worksheets/sheet1.xml",
        lambda body: body.replace(b"<v>9132700</v>", b"<v>9132800</v>")
                        .replace(b"<v>967500</v>", b"<v>967600</v>"))
    with pytest.raises(ValueError, match="independent presentation disagree"):
        nj._validate_all(bodies)


def test_changed_presentation_chart_rejected():
    bodies = {name: _body(name) for name in nj.FILES}
    bodies[nj.REPORT_FILE] = _changed_zip(
        nj.REPORT_FILE, "ppt/charts/chart3.xml",
        lambda body: body.replace(b"<c:v>1065500</c:v>", b"<c:v>1065600</c:v>"))
    with pytest.raises(ValueError, match="independent presentation disagree"):
        nj._validate_all(bodies)


@pytest.mark.parametrize("name,old,new", [
    (nj.METHOD_FILE, b"vintage 2014", b"vintage 2015"),
    (nj.METHOD_FILE, b"cohort-component", b"cohort/componenT"),
    (nj.INTRO_FILE, b"21 counties", b"20 counties"),
    (nj.INTRO_FILE, b"not forecasts or predictions", b"yes forecasts or predictions"),
])
def test_changed_methodology_or_base_rejected(name, old, new):
    assert old in _body(name)
    assert len(old) == len(new)
    with pytest.raises(ValueError, match="changed model"):
        nj._validate_doc(_body(name).replace(old, new), name)


def test_truncated_binary_doc_rejected():
    with pytest.raises(ValueError, match="readable binary Word"):
        nj._doc_text(_body(nj.METHOD_FILE)[:2048])


def test_changed_catalog_rejected():
    with pytest.raises(ValueError, match="projection catalog"):
        nj._validate_catalog(_body(nj.CATALOG_FILE).replace(b"sptab1.xlsx", b"unpublished.xlsx"))


def test_workbook_edition_rejected():
    body = _changed_zip(nj.STATE_FILE, "docProps/core.xml",
                        lambda data: data.replace(b"2017-05-11T14:49:29Z", b"2026-10-01T14:49:29Z"))
    with pytest.raises(ValueError, match="workbook edition"):
        nj.parse_state_workbook(body)


def test_reuses_original_snapshots_and_rejects_missing_manifest_entry(monkeypatch, tmp_path):
    manifest = _body("manifest.json")
    monkeypatch.setattr(nj.fetch, "get_bytes", lambda *_: pytest.fail("unexpected network call"))
    nj.acquire()
    assert _body("manifest.json") == manifest
    (tmp_path / "manifest.json").write_text("[]")
    monkeypatch.setattr(nj, "RAW_DIR", tmp_path)
    with pytest.raises(ValueError, match="incomplete saved snapshot manifest"):
        nj.acquire()
