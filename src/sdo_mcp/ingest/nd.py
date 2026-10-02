"""North Dakota's February 2024 state and county population summary tables."""
from __future__ import annotations

import io
import re
import sys
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "nd"
URL = "https://www.medialibrary.nd.gov/assetbank-nd/assetfile/137073.pdf"
CATALOG_URL = "https://www.commerce.nd.gov/economic-development-finance/state-data-center"
FILE = "population_2020-2050_feb2024.pdf"
CATALOG_FILE = "state_data_center_catalog_2026-10-02.html"
FILES = {FILE: URL, CATALOG_FILE: CATALOG_URL}
SOURCE_ID = "nd-pop-feb2024-summary"
AGENCY = "North Dakota Department of Commerce, State Data Center"
VINTAGE = "February 6, 2024"
YEARS = tuple(range(2020, 2051, 5))
SUMMARY_PAGES = (9, 10)  # printed pages 10-11
CHECK_PAGE = 13  # printed page 14, Both Sexes Total
STATE_VALUES = (779094, 796989, 831543, 865397, 890424, 925101, 957194)
COUNTY_STATE_DIFFERENCES = (0, -1, 0, 1, 4, 2, 2)


def _geographies() -> dict[str, str]:
    geos = {p[4]: p[1] + p[2] for line in COUNTY_FILE.read_text().splitlines()[1:]
            if (p := line.split("|"))[0] == "ND"}
    if len(geos) != 53:
        raise ValueError("ND: expected all 53 Census counties")
    return geos | {"North Dakota Totals": "38"}


def _integer(token: str) -> int:
    if not re.fullmatch(r"(?:0|[1-9]\d{0,2}(?:,\d{3})*|[1-9]\d*)", token):
        raise ValueError(f"ND: invalid or suppressed integer population {token!r}")
    return int(token.replace(",", ""))


def _text_tokens(page) -> list[str]:
    """Keep original text-show cells; generated text spaces split kerning digits.

    The original PDF uses a separate Tj/TJ operation for each numeric cell.
    Joining glyph strings inside TJ and ignoring spacing adjustments recovers
    that cell exactly, without guessing whitespace or reconstructing values.
    """
    tokens = []
    for operands, operator in page.get_contents().operations:
        if operator == b"TJ":
            if any(not isinstance(value, (str, int, float)) for value in operands[0]):
                raise ValueError("ND: undecodable PDF text cell")
            text = "".join(value for value in operands[0] if isinstance(value, str))
        elif operator == b"Tj":
            if not isinstance(operands[0], str):
                raise ValueError("ND: undecodable PDF text cell")
            text = operands[0]
        elif operator in (b"'", b'"'):
            raise ValueError("ND: changed PDF text operation layout")
        else:
            continue
        if text.strip():
            tokens.append(text.strip())
    return tokens


def _parse_summary(pages: list[list[str]]) -> list[dict]:
    if len(pages) != 2:
        raise ValueError("ND: incomplete summary pages")
    rows, seen = [], set()
    geos = _geographies()
    expected_order = list(geos)
    for page_index, original in enumerate(pages):
        tokens = list(original)
        if not tokens or tokens[0] != str(10 + page_index):
            raise ValueError("ND: unexpected summary page number")
        tokens.pop(0)
        if page_index == 0:
            if len(tokens) < 2 or "SUMMARY OF PROJECTIONS" not in tokens[-2] or tokens[-1] != "COUNTIES":
                raise ValueError("ND: unexpected county table title")
            tokens = tokens[:-2]
        if tokens[-7:] != [str(y) for y in YEARS]:
            raise ValueError("ND: unexpected table year grid")
        tokens = tokens[:-7]
        # One original geography label wraps over two text-show operations.
        while "Golden Valley" in tokens:
            index = tokens.index("Golden Valley")
            if tokens[index + 1:index + 2] != ["County"]:
                raise ValueError("ND: malformed Golden Valley county label")
            tokens[index:index + 2] = ["Golden Valley County"]
        if len(tokens) != 27 * 8:
            raise ValueError("ND: incomplete summary geography/year grid")
        for start in range(0, len(tokens), 8):
            name, *cells = tokens[start:start + 8]
            if name not in geos:
                raise ValueError(f"ND: unknown geography {name!r}")
            if name in seen:
                raise ValueError("ND: duplicate geography")
            if name != expected_order[len(seen)]:
                raise ValueError("ND: unexpected geography roster/order")
            seen.add(name)
            gid = geos[name]
            rows.extend(dict(state="ND", geo_level="state" if gid == "38" else "county", geo_id=gid,
                             year=year, variable="population", value=_integer(cell),
                             datatype="estimate" if year == 2020 else "projection", source_id=SOURCE_ID)
                        for year, cell in zip(YEARS, cells, strict=True))
    if seen != set(geos):
        raise ValueError("ND: incomplete geography roster")
    values = {(r["geo_id"], r["year"]): r["value"] for r in rows}
    if tuple(values["38", y] for y in YEARS) != STATE_VALUES:
        raise ValueError("ND: published summary state totals changed")
    for year, difference in zip(YEARS, COUNTY_STATE_DIFFERENCES, strict=True):
        if sum(r["value"] for r in rows if r["geo_level"] == "county" and r["year"] == year) - values["38", year] != difference:
            raise ValueError("ND: county/state rounding difference changed")
    return rows


def _validate_edition(text: str, methods: str) -> None:
    title, method = " ".join(text.split()), " ".join(methods.split())
    if ("2024" not in title or "Prepared February 6, 2024" not in title or "AND COUNTIES" not in title
            or "North Dakota Department of Commerce" not in title or "State Data Center" not in title
            or "each county in Census 2020" not in method or "modified version" not in method):
        raise ValueError("ND: unexpected producer, edition or Census base")


def _check_state_table(tokens: list[str]) -> tuple[int, ...]:
    if (not tokens or tokens[0] != "14" or "BOTH SEXES" not in tokens or tokens.count("Total") != 1
            or "Group" not in tokens
            or [str(y) for y in YEARS] != tokens[tokens.index("Group") + 1:tokens.index("Group") + 8]):
        raise ValueError("ND: unexpected independent state check table")
    start = tokens.index("Total") + 1
    values = tuple(_integer(t) for t in tokens[start:start + 7])
    if values != STATE_VALUES:
        raise ValueError("ND: independent Both Sexes state Total disagrees")
    return values


def parse(body: bytes) -> list[dict]:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(body))
        if not reader.pages:
            raise ValueError("empty PDF")
    except Exception as exc:
        raise ValueError("ND: response is not a readable population PDF") from exc
    if len(reader.pages) != 16:
        raise ValueError("ND: unexpected report page count")
    _validate_edition(reader.pages[0].extract_text() or "", reader.pages[4].extract_text() or "")
    rows = _parse_summary([_text_tokens(reader.pages[i]) for i in SUMMARY_PAGES])
    _check_state_table(_text_tokens(reader.pages[CHECK_PAGE]))
    return rows


def _validate(bodies: dict[str, bytes]) -> list[dict]:
    catalog = " ".join(bodies[CATALOG_FILE].decode("utf-8", "replace").split())
    if any(s not in catalog for s in ("<html", "2024 North Dakota State Data Center Population Projections", "137073.pdf", "957,124", "official state population projections")):
        raise ValueError("ND: invalid current publisher catalog or product evidence")
    return parse(bodies[FILE])


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if {e["file"] for e in entries} != set(FILES):
            raise ValueError("ND: incomplete snapshot manifest")
        _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("ND acquire: reused validated February 2024 snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    rows = _validate(bodies)
    entries = []
    for name, body in bodies.items():
        fetch.write_snapshot(RAW_DIR / name, body)
        entries.append(dict(file=name, source=FILES[name], retrieved_at=date.today().isoformat(), sha256=fetch.sha256(body),
                            records=len(rows) if name == FILE else None,
                            note="Original publisher bytes. Printed pp10-11 summary state/county totals independently checked against rendered table and p14 Both Sexes Total. State horizon957,194 retained despite catalog/summary957,124."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    rows = _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
    if {(r["geo_level"], r["geo_id"]) for r in conn.execute("SELECT * FROM geographies WHERE state='ND'")} != {(r["geo_level"], r["geo_id"]) for r in rows}:
        raise ValueError("ND: seeded geographies differ from publication")
    upsert_source(conn, source_id=SOURCE_ID, state="ND", agency=AGENCY,
        product_name="2024 Population Projections of the State, Regions, and Counties: summary state/county totals",
        vintage=VINTAGE, base_year=2020, horizon_year=2050, source_url=URL, retrieved_at=entries[FILE]["retrieved_at"],
        license="No explicit data license identified; cite the North Dakota Department of Commerce State Data Center.",
        citation="North Dakota Department of Commerce – State Data Center. 2024 North Dakota State Data Center Population Projections of the State, Regions, and Counties. Prepared February 6, 2024. Summary of Projections—Counties, printed pp10-11; North Dakota Totals on p11, repeated by Both Sexes Total p14.",
        method_notes=("The selected summary table explicitly publishes the state and all 53 counties in integer persons at five-year points 2020-2050. "
            "2020 Census county age/sex populations anchor the modified cohort-survival-component model; the April 1, 2020 historical counts are marked estimate under this schema, and 2025-2050 remain projections. "
            "No alternatives or interpolated years are loaded. Future reference-day detail is unstated. "
            "State 2050 is 957,194 in the selected p11 North Dakota Totals row, p14 Both Sexes Total and p4 chart; the executive summary and catalog instead say 957,124. "
            "The p4 methods describe county-to-region-to-state aggregation, but published county sums differ from state totals by 0,-1,0,+1,+4,+2,+2 persons for the seven years; no values are balanced. "
            "Region totals and age/sex detail are archived but not served; published detail contains further rounding/historical differences and is not substituted for summary totals. "
            "Printed p6 publishes five-year natural change and net migration, not separate births/deaths; components remain PDF-only and unannualized. "
            "Subcounty population, household-count and eligible SDC jobs publication coverage remain unverified. Workforce ages are population, not jobs."))
    insert_observations(conn, rows)
    conn.commit()
    print(f"ND load: {len(rows)} observations")


# Independently read from rendered original pp10/11 and the repeated p14 Total.
FIXTURES = (("38", 2020, 779094), ("38", 2025, 796989), ("38", 2030, 831543), ("38", 2050, 957194),
            ("38017", 2020, 184525), ("38017", 2025, 194767), ("38017", 2050, 272878),
            ("38087", 2020, 706), ("38087", 2025, 713), ("38087", 2050, 799),
            ("38033", 2050, 1720), ("38105", 2050, 56047))


def verify(conn) -> None:
    rows = conn.execute("SELECT * FROM observations WHERE state='ND'").fetchall()
    ids = set(_geographies().values())
    assert len(rows) == 378 and {(r["geo_id"], r["year"]) for r in rows} == {(gid, y) for gid in ids for y in YEARS}
    assert all(r["geo_level"] == ("state" if r["geo_id"] == "38" else "county")
               and r["datatype"] == ("estimate" if r["year"] == 2020 else "projection") and r["source_id"] == SOURCE_ID
               and r["variable"] == "population" and r["scenario"] == "" and r["age_group"] == r["sex"] == r["race"] == "all"
               and r["value"] >= 0 and float(r["value"]).is_integer() for r in rows)
    values = {(r["geo_id"], r["year"]): r["value"] for r in rows}
    for gid, year, value in FIXTURES:
        assert values[gid, year] == value
    for year, diff in zip(YEARS, COUNTY_STATE_DIFFERENCES, strict=True):
        assert sum(values[gid, year] for gid in ids - {"38"}) - values["38", year] == diff
    print("ND verify: state/all 53 counties, exact grids, rounding and rendered fixtures ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.nd --acquire")
