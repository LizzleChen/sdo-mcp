"""UNO CPAR's adopted August 2022 Nebraska state/county population product."""

from __future__ import annotations

import argparse
import io
import re
from datetime import date
from pathlib import Path

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "ne"
AGENCY_URL = "https://www.unomaha.edu/college-of-public-affairs-and-community-service/center-for-public-affairs-research/"
CATALOG_URL = AGENCY_URL + "programs/data-for-policy-and-decision-makers.php"
SDC_URL = AGENCY_URL + "programs/nebraska-state-data-center.php"
REPOSITORY_URL = "https://digitalcommons.unomaha.edu/cparpubarchives/643/"
REPORT_URL = "https://uofnebraska.sharepoint.com/:b:/s/UNOCenterforPublicAffairsResearch2/IQArysrd74RcR7lkqZFVHOVBAa7xSaM0iYr5KGXLHaEKDU4"
REPORT_FILE = "population_aug2022.pdf"
CATALOG_FILE = "projection_catalog_2026-09-30.html"
SDC_FILE = "state_data_center_2026-09-30.html"
REPOSITORY_FILE = "repository_record_2026-09-30.html"
FILES = {REPORT_FILE: REPORT_URL, CATALOG_FILE: CATALOG_URL,
         SDC_FILE: SDC_URL, REPOSITORY_FILE: REPOSITORY_URL}
SOURCE_ID = "ne-pop-aug2022"
AGENCY = "University of Nebraska at Omaha, Center for Public Affairs Research (Nebraska State Data Center)"
TITLE = "Population Projections for Nebraska Counties 2020 to 2050"
YEARS = (2020, 2030, 2040, 2050)
TABLE_YEARS = (1990, 2000, 2010, *YEARS)
HEADER = "County 1990 Population 2000 Population 2010 Population 2020 Population 2030 Projected 2040 Projected 2050 Projected"


def _counties() -> dict[str, str]:
    counties = {}
    for line in COUNTY_FILE.read_text().splitlines()[1:]:
        fields = line.split("|")
        if fields[0] == "NE":
            # The PDF joins the words in BoxButte and KeyaPaha.
            counties[fields[4].removesuffix(" County").replace(" ", "")] = fields[1] + fields[2]
    if len(counties) != 93:
        raise ValueError("NE: expected 93 Census counties")
    return counties


def parse_pdf(body: bytes) -> list[dict]:
    """Parse every row of the publisher's table; never construct state totals."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(body))
        if len(reader.pages) != 4 or reader.metadata.title != TITLE:
            raise ValueError("unexpected PDF title or page count")
        pages = [p.extract_text() for p in reader.pages]
    except Exception as exc:
        raise ValueError("NE: response is not the expected readable population PDF") from exc
    intro = " ".join(pages[0].split())
    for marker in ("2020 Census", "regional rivalry", "Hauer (2019)",
                   "model was adopted", "2030, 2040, and 2050"):
        if marker not in intro:
            raise ValueError(f"NE: changed model, base or year description; missing {marker!r}")
    geos = _counties() | {"Nebraska": "31"}
    totals = {}
    for text in pages[1:]:
        # Extraction wraps each column header across two lines. Validate the
        # entire header before using the seven numeric columns that follow it.
        header = re.search(r"\s+".join(map(re.escape, HEADER.split())), text)
        if header is None:
            raise ValueError("NE: changed table year or estimate/projection header")
        for line in text[header.end():].splitlines():
            tokens = line.split()
            if not tokens:
                continue
            if tokens == ["References"]:
                break
            if len(tokens) < 8 or not all(re.fullmatch(r"\d{1,3}(?:,\d{3})*|\d+", token)
                                          for token in tokens[-7:]):
                raise ValueError(f"NE: malformed population table row {line!r}")
            name = "".join(tokens[:-7])
            if name not in geos or name in totals:
                raise ValueError(f"NE: unknown or duplicate geography {name!r}")
            totals[name] = tuple(int(token.replace(",", "")) for token in tokens[-7:])
    if set(totals) != set(geos):
        raise ValueError("NE: incomplete state/county population grid")
    # Source totals are independently rounded; retain the published state row.
    # Historical counts add exactly. Forecast differences are 2, 1 and 3 people.
    expected_differences = (0, 0, 0, 0, 2, 1, 3)
    for i, year in enumerate(TABLE_YEARS):
        difference = totals["Nebraska"][i] - sum(totals[name][i] for name in geos if name != "Nebraska")
        if difference != expected_differences[i]:
            raise ValueError(f"NE: changed county/state reconciliation in {year}")
    return [dict(
        state="NE", geo_level="state" if name == "Nebraska" else "county",
        geo_id=geos[name], year=year, variable="population", value=value,
        datatype="estimate" if year == 2020 else "projection", source_id=SOURCE_ID,
    ) for name, values in totals.items() for year, value in zip(TABLE_YEARS, values) if year >= 2020]


def _validate_reference(body: bytes, filename: str) -> None:
    text = " ".join(body.decode("utf-8", "replace").lower().split())
    markers = {
        CATALOG_FILE: ("<html", "8-17-22", "at the request of the nebraska legislature",
                       "population projections for nebraska counties 2020 to 2050"),
        SDC_FILE: ("<html", "center for public affairs research", "lead agency of the state data center program"),
        REPOSITORY_FILE: ("<html", "population projections for nebraska counties 2020 to 2050",
                          "josie gatti schafer", "tara grell", 'content="2022"'),
    }[filename]
    if any(marker not in text for marker in markers):
        raise ValueError(f"NE: invalid producer or edition reference {filename}")


def _validate_all(bodies: dict[str, bytes]) -> list[dict]:
    rows = parse_pdf(bodies[REPORT_FILE])
    for name in (CATALOG_FILE, SDC_FILE, REPOSITORY_FILE):
        _validate_reference(bodies[name], name)
    return rows


def acquire(source_file: Path | None = None) -> None:
    """Reuse originals; support the publisher's browser-only public PDF download."""
    if (RAW_DIR / "manifest.json").exists():
        if set(e["file"] for e in fetch.read_manifest(RAW_DIR)) != set(FILES):
            raise ValueError("NE: incomplete saved snapshot manifest")
        _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("NE acquire: reused validated August 2022 snapshots")
        return
    if source_file is None:
        raise ValueError("NE: download the public PDF from REPORT_URL in a browser, then pass --source-file; direct SharePoint and DigitalCommons PDF requests returned 403 at acquisition")
    bodies = {REPORT_FILE: source_file.read_bytes()}
    # Validate the user-supplied publisher file before downloading references.
    parse_pdf(bodies[REPORT_FILE])
    for name in (CATALOG_FILE, SDC_FILE, REPOSITORY_FILE):
        bodies[name] = fetch.get_bytes(FILES[name])
    rows = _validate_all(bodies)
    entries = []
    for name, url in FILES.items():
        body = bodies[name]
        fetch.write_snapshot(RAW_DIR / name, body)
        entries.append(dict(file=name, source=url, retrieved_at=date.today().isoformat(),
                            sha256=fetch.sha256(body), records=len(rows) if name == REPORT_FILE else None,
                            note="Original UNO CPAR August 2022 publication or publisher reference. PDF acquired using the current catalog's public SharePoint browser download; June 2025 PDF modification metadata is not a new model vintage. CPAR expressly adopts Hauer/SEDAC regional-rivalry projections at the legislature's request."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    rows = _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
    upsert_source(
        conn, source_id=SOURCE_ID, state="NE", agency=AGENCY,
        product_name="Population Projections for Nebraska Counties 2020 to 2050",
        vintage="August 2022", base_year=2020, horizon_year=2050,
        source_url=REPORT_URL, retrieved_at=entries[REPORT_FILE]["retrieved_at"],
        license="No explicit data license identified; cite UNO CPAR and its cited Hauer/SEDAC model.",
        citation="Schafer, Josie Gatti and Grell, Tara. Population Projections for Nebraska Counties 2020 to 2050. UNO Center for Public Affairs Research, August 2022. Hauer/SEDAC regional-rivalry model adopted by CPAR.",
        method_notes=(
            "UNO CPAR, Nebraska's State Data Center lead, released this edition at the Nebraska "
            "legislature's request (catalog dated August 17, 2022). CPAR expressly adopted the "
            "Hauer/SEDAC regional-rivalry model after comparing six models; these figures are an "
            "adopted national model, not a newly generated CPAR cohort-component forecast. The "
            "report publishes a separate Nebraska row and all 93 counties. The 2020 Census counts "
            "are labeled estimate in MCP; 2030, 2040 and 2050 are projections. No annual interpolation "
            "or unpublished statewide sum is generated. Rounded county sums differ from the published "
            "state projection by 2, 1 and 3 people respectively, and both are retained unchanged. "
            "The report's June 2025 modification metadata does not identify a new forecast vintage. "
            "Household, components, subcounty and eligible CPAR employment forecasts were not "
            "established in this catalog/report survey, so their publication coverage remains unknown."
        ),
    )
    insert_observations(conn, rows)
    conn.commit()
    print(f"NE load: {len(rows)} observations")


def verify(conn) -> None:
    fixtures = {("31", 2020): (1961504, "estimate"),
                ("31", 2030): (1995774, "projection"),
                ("31", 2050): (2031075, "projection"),
                ("31013", 2050): (10267, "projection"),
                ("31055", 2050): (660606, "projection"),
                ("31075", 2030): (639, "projection"),
                ("31103", 2050): (514, "projection"),
                ("31153", 2040): (232217, "projection")}
    for (gid, year), expected in fixtures.items():
        row = conn.execute("SELECT value,datatype FROM observations WHERE state='NE' "
                           "AND variable='population' AND geo_id=? AND year=?", (gid, year)).fetchone()
        assert tuple(row) == expected, f"NE fixture {gid}/{year}"
    shape = conn.execute("SELECT COUNT(*),COUNT(DISTINCT geo_id),COUNT(DISTINCT year),"
                         "MIN(year),MAX(year),SUM(datatype='estimate') FROM observations WHERE state='NE'").fetchone()
    assert tuple(shape) == (376, 94, 4, 2020, 2050, 94)
    print("NE verify: state row, 93 counties and checked PDF anchors ok")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquire", action="store_true")
    parser.add_argument("--source-file", type=Path)
    args = parser.parse_args()
    if args.acquire:
        acquire(args.source_file)
    else:
        parser.print_help()
