"""DPC summary series, adoption date, and product boundaries."""

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import de


@pytest.mark.parametrize("variable,values", [
    ("population", [989948, 1045328, 1083164, 1112376, 1135170, 1151585, 1171796]),
    ("households", [388107, 412721, 427959, 436300, 438982, 438132, 438806]),
    ("employment", [451132, 461246, 468487, 474209, 479132, 485261, 494222]),
])
def test_state_products_are_distinct(variable, values):
    result = server.get_forecast("DE", "state", "Delaware", variable)
    assert result["status"] == "ok"
    assert result["series"] == [
        {"year": year, "value": value,
         "datatype": "estimate" if year == 2020 else "projection"}
        for year, value in zip(range(2020, 2051, 5), values)
    ]
    source = result["source"]
    assert source["base_year"] == 2020
    assert source["horizon_year"] == 2050
    assert "readopted December 2025" in source["vintage"]
    assert source["url"] == de.WORKBOOK_URL
    assert source["retrieved_at"] == next(e["retrieved_at"] for e in de.fetch.read_manifest(de.RAW_DIR)
                                          if e["file"] == "DPC-2024v0-report.xls")
    if variable == "employment":
        assert "place of work" in source["method_notes"]


@pytest.mark.parametrize("name,gid,pop,jobs", [
    ("Kent", "10001", 213228, 81236),
    ("New Castle", "10003", 589023, 282773),
    ("Sussex", "10005", 369545, 130213),
])
def test_county_names_and_fips(name, gid, pop, jobs):
    for variable, value in (("population", pop), ("employment", jobs)):
        result = server.get_forecast("DE", "county", name, variable, start_year=2050)
        assert result == server.get_forecast("DE", "county", gid, variable, start_year=2050)
        assert result["series"] == [{"year": 2050, "value": value, "datatype": "projection"}]


def test_exact_grid_and_unloaded_products():
    conn = store.connect()
    try:
        de.verify(conn)
        assert conn.execute("SELECT COUNT(*) FROM observations WHERE state='DE'").fetchone()[0] == 84
    finally:
        conn.close()
    assert server.get_forecast("DE", "county", "Kent", "population", start_year=2026,
                               end_year=2029)["status"] == "empty_range"
    assert server.get_forecast("DE", "place", "Dover", "population")["status"] == "not_loaded"
    assert server.get_forecast("DE", "state", "DE", "population", scenario="high")["status"] == "error"
    assert server.get_components("DE", "Kent")["status"] == "coverage_unknown"
    assert server.describe_source("DE")["review"]["status"] == "never_reviewed"


@pytest.mark.parametrize("body", [b"<html>error</html>", b"[]", b"PKbroken"])
def test_soft_200_rejected(body):
    with pytest.raises(ValueError, match="readable XLS"):
        de.parse_workbook(body)


def test_reuses_snapshots_without_network(monkeypatch):
    before = (de.RAW_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(de.fetch, "get_bytes", lambda *_args: pytest.fail("unexpected network call"))
    de.acquire()
    assert (de.RAW_DIR / "manifest.json").read_bytes() == before
