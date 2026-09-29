"""Indiana's official July 2024 IBRC population projections.

STATS Indiana serves HTML tables via a POST-only query. Archive the original
response, validate its contents (not just HTTP success), and load only its
published totals: 2020 estimates and five-year projections from 2025 onward.
"""

from __future__ import annotations

import sys
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "in"
FILE = "population_2024.html"
URL = "https://www.stats.indiana.edu/pop_proj/pop_proj.asp"
FORM = dict(geotype="a", geo="S18;CL___", year="All", datacode="tb", geo_label="All IN Counties")
METHOD_URL = "https://www.stats.indiana.edu/about/pop-projections-2025-60.asp"
EDITION_URL = "https://www.stats.indiana.edu/topic/projections.asp"
COVERAGE_URL = "https://www.stats.indiana.edu/topic/population.asp"
REFERENCES = (
    ("methodology_2024.html", METHOD_URL, "Methodology for Indiana State and County Population Projections"),
    ("projection_edition_2024.html", EDITION_URL, "Released in July 2024"),
    ("population_coverage_2026-09-28.html", COVERAGE_URL, "Indiana Places (Cities and Towns)"),
)
STATE_SOURCE_ID = "in-pop-state-2024"
COUNTY_SOURCE_ID = "in-pop-county-2024"
AGENCY = "Indiana Business Research Center, Kelley School of Business, Indiana University (STATS Indiana)"
LICENSE = "No explicit data license identified on the reviewed pages; cite IBRC and STATS Indiana."
HEADER = ["Area", "Year", "Total", "Preschool 0-4", "School Age 5-19",
          "College Age 20-24", "Young Adult 25-44", "Older Adult 45-64", "Seniors 65+"]


class _TableParser(HTMLParser):
    """Read only the publisher's formatted table, rejecting broken structure."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None
        self.in_table = False
        self.table_count = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.in_table:
                raise ValueError("IN table: nested table")
            if "formatted" in dict(attrs).get("class", "").split():
                self.in_table = True
                self.table_count += 1
        if not self.in_table:
            return
        if tag == "tr":
            if self.row is not None:
                raise ValueError("IN table: unclosed row")
            self.row = []
        elif tag in ("th", "td"):
            if self.row is None or self.cell is not None:
                raise ValueError("IN table: malformed cell")
            self.cell = []
        elif tag == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_data(self, text):
        if self.cell is not None:
            self.cell.append(text)

    def handle_endtag(self, tag):
        if not self.in_table:
            return
        if tag in ("th", "td"):
            if self.cell is None:
                raise ValueError("IN table: unmatched cell end")
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr":
            if self.row is None or self.cell is not None:
                raise ValueError("IN table: malformed row end")
            self.rows.append(self.row)
            self.row = None
        elif tag == "table":
            if self.row is not None:
                raise ValueError("IN table: unclosed row")
            self.in_table = False


def _geographies() -> dict[str, tuple[str, str]]:
    geos = {"Indiana state": ("state", "18")}
    for line in COUNTY_FILE.read_text().splitlines()[1:]:
        parts = line.split("|")
        if parts[0] == "IN":
            geos[parts[4]] = ("county", parts[1] + parts[2])
    if len(geos) != 93:
        raise ValueError("IN: expected 92 Census counties and the state")
    return geos


def parse(body: bytes) -> list[dict]:
    """Require the complete edition's geography/year grid before accepting it."""
    text = body.decode("utf-8")
    if ("Indiana Population Projections" not in text or
            "2020 data are U.S. Census Bureau population estimates (Vintage 2022)." not in text):
        raise ValueError("IN: response is not the expected population table with estimate labels")
    parser = _TableParser()
    parser.feed(text)
    parser.close()
    if (parser.in_table or parser.table_count != 1 or not parser.rows or
            parser.rows[0] != HEADER):
        raise ValueError("IN: unexpected or incomplete population table/header")
    geos = _geographies()
    expected = {(name, year) for name, (level, _) in geos.items()
                for year in range(2020, 2061 if level == "state" else 2051, 5)}
    seen = set()
    observations = []
    for row in parser.rows[1:]:
        if len(row) != len(HEADER):
            raise ValueError("IN: malformed population row")
        name, year_text, *numbers = row
        if name not in geos or not year_text.isascii() or not year_text.isdecimal():
            raise ValueError(f"IN: unknown geography/year {name!r}/{year_text!r}")
        year = int(year_text)
        key = (name, year)
        if key in seen or key not in expected:
            raise ValueError(f"IN: duplicate or unexpected geography/year {key!r}")
        seen.add(key)
        values = []
        for number in numbers:
            # Require the exact integer formatting supplied by the table.
            digits = number.replace(",", "")
            if not digits.isascii() or not digits.isdecimal() or number != f"{int(digits):,}":
                raise ValueError(f"IN: invalid population value {number!r}")
            values.append(int(digits))
        level, gid = geos[name]
        observations.append(dict(
            state="IN", geo_level=level, geo_id=gid, year=year,
            variable="population", value=values[0],
            datatype="estimate" if year == 2020 else "projection",
            source_id=STATE_SOURCE_ID if level == "state" else COUNTY_SOURCE_ID,
        ))
    if seen != expected:
        raise ValueError(f"IN: incomplete geography/year grid; missing {len(expected - seen)} observations")
    return observations


def _validate_reference(body: bytes, marker: str) -> None:
    text = body.decode("utf-8")
    if "<html" not in text.lower() or marker not in text:
        raise ValueError(f"IN: unexpected reference page, missing {marker!r}")


def acquire() -> None:
    """Save this edition once; later editions need new filenames.

    Responses include generation timestamps. Reuse validated saved originals
    rather than replacing identical data with a newly timestamped response.
    """
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        required = {FILE} | {name for name, _, _ in REFERENCES}
        if not required <= {e["file"] for e in entries}:
            raise ValueError("IN: incomplete saved manifest")
        parse((RAW_DIR / FILE).read_bytes())
        for name, _, marker in REFERENCES:
            _validate_reference((RAW_DIR / name).read_bytes(), marker)
        print("IN acquire: reused validated July 2024 snapshots")
        return
    request = Request(URL, data=urlencode(FORM).encode(), headers=fetch.UA)
    with urlopen(request, timeout=120) as response:
        body = response.read()
    rows = parse(body)
    downloads = [(FILE, URL, body, len(rows))]
    for name, url, marker in REFERENCES:
        reference = fetch.get_bytes(url)
        _validate_reference(reference, marker)
        downloads.append((name, url, reference, None))
    entries = []
    for name, url, body, count in downloads:
        fetch.write_snapshot(RAW_DIR / name, body)
        entry = dict(file=name, source=url, retrieved_at=date.today().isoformat(),
                     sha256=fetch.sha256(body), records=count,
                     note="Original STATS Indiana HTML response; July 2024 population edition and supporting evidence.")
        if name == FILE:
            entry.update(request_method="POST", request_form=FORM)
        entries.append(entry)
    fetch.write_manifest(RAW_DIR, entries)
    print(f"IN acquire: {len(rows)} published totals and three reference pages")


def load(conn) -> None:
    entries = fetch.read_manifest(RAW_DIR)
    retrieved = next(e["retrieved_at"] for e in entries if e["file"] == FILE)
    rows = parse((RAW_DIR / FILE).read_bytes())
    actual = {(r["geo_level"], r["geo_id"]) for r in conn.execute(
        "SELECT geo_level, geo_id FROM geographies WHERE state='IN'"
    )}
    if actual != set(_geographies().values()):
        raise ValueError("IN: seeded geographies do not match the source geography set")
    shared_notes = (
        "Published five-year totals only; no intermediate years are generated. "
        "The 2020 rows are explicitly labelled Census Vintage 2022 estimates; all 2025+ rows are projections. "
        "County sums exceed published state projections by 55 to 130 people depending on year; "
        "the cause is not stated in the table. Both are retained without reconciliation. "
        f"The query at {URL} requires POST with geotype=a, geo=S18;CL___, year=All, datacode=tb, "
        "geo_label=All IN Counties; geoagg and use_pct omitted. "
    )
    for source_id, level, base_year, horizon, method in (
        (STATE_SOURCE_ID, "state", 2023, 2060,
         "The statewide method names 2020 (Vintage 2022) as the population base. "
         "It incorporates observed births, deaths, migration and other estimates through 2023 "
         "to project 2025, then uses the cohort-component method. In this MCP, base_year=2023 "
         "identifies the last underlying estimate year; the model's population anchor is 2020. "
         "The table does not publish a 2023 observation."),
        (COUNTY_SOURCE_ID, "county", 2023, 2050,
         "The county method explicitly uses 2023 Census population estimates to project 2025, "
         "then a mixed-method approach controlled to state projections. The 2023 base values "
         "are not published in this table and are not manufactured; its only historical rows are 2020."),
    ):
        upsert_source(
            conn, source_id=source_id, state="IN", agency=AGENCY,
            product_name=f"Indiana {level.title()} Population Projections, 2025-{horizon}",
            vintage="July 2024", base_year=base_year, horizon_year=horizon,
            source_url="https://www.stats.indiana.edu/pop_proj/", retrieved_at=retrieved, license=LICENSE,
            citation="Indiana Business Research Center, Indiana University. Indiana Population Projections, July 2024. STATS Indiana.",
            method_notes=shared_notes + method + f" Methodology: {METHOD_URL}",
        )
    count = insert_observations(conn, rows)
    conn.commit()
    print(f"IN load: {count} observations")


FIXTURES = [
    ("18", 2020, 6788799, "estimate"),
    ("18", 2025, 6907017, "projection"),
    ("18", 2060, 7168182, "projection"),
    ("18057", 2030, 417426, "projection"),
    ("18057", 2050, 529505, "projection"),
    ("18097", 2050, 1011523, "projection"),
    ("18033", 2050, 46245, "projection"),
]


def verify(conn) -> None:
    for gid, year, value, datatype in FIXTURES:
        row = conn.execute(
            "SELECT value, datatype FROM observations WHERE state='IN' AND geo_id=? "
            "AND year=? AND variable='population'", (gid, year),
        ).fetchone()
        assert row is not None and tuple(row) == (value, datatype), f"IN fixture: {gid}/{year}"
    shape = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT geo_id), MIN(year), MAX(year), "
        "SUM(datatype='estimate') FROM observations WHERE state='IN'"
    ).fetchone()
    assert tuple(shape) == (653, 93, 2020, 2060, 93)
    print(f"IN verify: {len(FIXTURES)} fixtures and complete state/county grid ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.in --acquire")
