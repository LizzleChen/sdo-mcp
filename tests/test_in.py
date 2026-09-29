"""Indiana: complete published grids, separate metadata, no invented values."""

from importlib import import_module
import io
import re

import pytest

from sdo_mcp import server, store

indiana = import_module("sdo_mcp.ingest.in")


def _body():
    return (indiana.RAW_DIR / indiana.FILE).read_bytes()


def test_state_round_trip_and_projection_labels():
    result = server.get_forecast("IN", "state", "Indiana", "population")
    assert result["status"] == "ok"
    assert result["geo"] == {"level": "state", "id": "18", "name": "Indiana"}
    assert result["scenario"] is None
    assert [p["year"] for p in result["series"]] == list(range(2020, 2061, 5))
    assert result["series"][0] == {"year": 2020, "value": 6788799, "datatype": "estimate"}
    assert result["series"][1] == {"year": 2025, "value": 6907017, "datatype": "projection"}
    assert result["series"][-1] == {"year": 2060, "value": 7168182, "datatype": "projection"}
    assert all(p["datatype"] == "projection" for p in result["series"][1:])
    assert result["source"]["vintage"] == "July 2024"
    assert result["source"]["base_year"] == 2023
    assert result["source"]["horizon_year"] == 2060
    assert "through 2023" in result["source"]["method_notes"]
    assert "population anchor is 2020" in result["source"]["method_notes"]
    assert result["source"]["retrieved_at"] == next(
        e["retrieved_at"] for e in indiana.fetch.read_manifest(indiana.RAW_DIR)
        if e["file"] == indiana.FILE
    )


def test_county_uses_its_own_source_and_horizon_without_filling_gaps():
    county = server.get_forecast("IN", "county", "Hamilton", "population")
    fips = server.get_forecast("IN", "county", "18057", "population")
    assert county == fips
    assert county["source"]["base_year"] == 2023
    assert county["source"]["horizon_year"] == 2050
    assert [p["year"] for p in county["series"]] == list(range(2020, 2051, 5))
    assert county["series"][-1] == {"year": 2050, "value": 529505, "datatype": "projection"}
    assert county["series"][0]["datatype"] == "estimate"
    for start, end in ((2023, 2023), (2026, 2029), (2051, 2060)):
        result = server.get_forecast("IN", "county", "Hamilton", "population",
                                     start_year=start, end_year=end)
        assert result["status"] == "empty_range"
        assert result["available_end_year"] == 2050


def test_all_counties_match_census_and_published_totals_are_not_reconciled():
    conn = store.connect()
    try:
        counties = conn.execute(
            "SELECT geo_id, COUNT(*) FROM observations WHERE state='IN' "
            "AND geo_level='county' GROUP BY geo_id"
        ).fetchall()
        assert len(counties) == 92
        assert all(row[1] == 7 for row in counties)
        differences = conn.execute(
            "SELECT s.year, SUM(c.value)-s.value FROM observations s "
            "JOIN observations c ON c.state=s.state AND c.year=s.year "
            "AND c.geo_level='county' AND c.variable='population' "
            "WHERE s.state='IN' AND s.geo_level='state' AND s.variable='population' "
            "GROUP BY s.year ORDER BY s.year"
        ).fetchall()
        assert dict(differences) == {2020: 0, 2025: 55, 2030: 79, 2035: 130,
                                     2040: 70, 2045: 75, 2050: 103}
    finally:
        conn.close()
    for name, gid, value in (("DeKalb", "18033", 46245), ("LaPorte", "18091", 104811),
                             ("St. Joseph", "18141", 271797), ("Marion", "18097", 1011523)):
        result = server.get_forecast("IN", "county", name, "population")
        assert result["geo"]["id"] == gid
        assert result["series"][-1]["value"] == value


def test_unpublished_unloaded_and_unknown_products_stay_distinct():
    place = server.get_forecast("IN", "place", "Indianapolis", "population")
    metro = server.get_forecast("IN", "msa", "Indianapolis", "population")
    assert place["status"] == "not_published"
    assert metro["status"] == "not_loaded"
    assert "series" not in place
    for level, geo in (("state", "IN"), ("county", "Marion")):
        for variable in ("households", "employment"):
            assert server.get_forecast("IN", level, geo, variable)["status"] == "coverage_unknown"
        assert server.get_components("IN", level, geo)["status"] == "coverage_unknown"
    state = server.list_states()["states"]["IN"]
    assert state["variables"]["population"]["county"]["load_status"] == "loaded"
    assert state["variables"]["population"]["msa"]["load_status"] == "not_loaded"
    described = server.describe_source("IN")
    assert described["variables"] == state["variables"]
    assert described["review"]["status"] == "never_reviewed"


@pytest.mark.parametrize("old,new,error", [
    (b"<th>Total</th>", b"<th>Percent</th>", "header"),
    (b"<td>Hamilton County</td>", b"<td>Invented County</td>", "unknown geography"),
    (b"<td>2060</td>", b"<td>2061</td>", "unexpected geography/year"),
    (b"6,907,017", b"-1", "invalid population value"),
    (b"6,907,017", b"NaN", "invalid population value"),
    (b"6,907,017", b"6,907,017.5", "invalid population value"),
    (b"6,907,017", b"6,90,7017", "invalid population value"),
    (b"(Vintage 2022).", b"(Vintage 2024).", "estimate labels"),
])
def test_parser_rejects_changed_semantics_and_invalid_values(old, new, error):
    body = _body()
    assert old in body
    with pytest.raises(ValueError, match=error):
        indiana.parse(body.replace(old, new, 1))


def test_parser_rejects_missing_duplicate_and_truncated_data():
    body = _body()
    row = re.search(rb"<tr><td>Hamilton County</td>.*?</tr>", body).group()
    with pytest.raises(ValueError, match="incomplete geography/year"):
        indiana.parse(body.replace(row, b"", 1))
    with pytest.raises(ValueError, match="duplicate"):
        indiana.parse(body.replace(row, row + row, 1))
    with pytest.raises(ValueError, match="incomplete population table"):
        indiana.parse(body.replace(b"</table>", b"", 1))


def test_acquire_rejects_soft_200_error_without_writing(monkeypatch, tmp_path):
    monkeypatch.setattr(indiana, "RAW_DIR", tmp_path / "in")
    monkeypatch.setattr(indiana, "urlopen", lambda *a, **k: io.BytesIO(b"<html>Service unavailable</html>"))
    with pytest.raises(ValueError, match="not the expected population table"):
        indiana.acquire()
    assert not indiana.RAW_DIR.exists()


def test_acquire_records_post_provenance_and_reuses_immutable_snapshots(monkeypatch, tmp_path):
    body = _body()
    references = {url: (indiana.RAW_DIR / name).read_bytes() for name, url, _ in indiana.REFERENCES}
    def respond(request, **kwargs):
        assert request.get_method() == "POST"
        assert request.data == indiana.urlencode(indiana.FORM).encode()
        return io.BytesIO(body)
    monkeypatch.setattr(indiana, "urlopen", respond)
    monkeypatch.setattr(indiana.fetch, "get_bytes", lambda url: references[url])
    monkeypatch.setattr(indiana, "RAW_DIR", tmp_path / "in")
    indiana.acquire()
    entries = indiana.fetch.read_manifest(indiana.RAW_DIR)
    table = next(e for e in entries if e["file"] == indiana.FILE)
    assert table["request_form"] == indiana.FORM
    assert table["request_method"] == "POST"
    assert table["records"] == 653
    def unexpected(*args, **kwargs):
        pytest.fail("existing snapshots should be reused without a network request")
    monkeypatch.setattr(indiana, "urlopen", unexpected)
    monkeypatch.setattr(indiana.fetch, "get_bytes", unexpected)
    indiana.acquire()
    assert indiana.fetch.read_manifest(indiana.RAW_DIR) == entries
    assert (indiana.RAW_DIR / indiana.FILE).read_bytes() == body
