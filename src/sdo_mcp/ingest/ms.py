"""Mississippi SDC's May 2019 preliminary state population PDF, 2020-2050.

The currently linked PDF is byte-identical to the publisher's archived 2019
release. Archived original methods establish the 2010 launch and release date.
"""
from __future__ import annotations

import io
import re
import sys
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source

RAW_DIR = REPO_ROOT / "data" / "raw" / "ms"
CATALOG_URL = "https://olemiss.edu/departments/libarts/population-studies/statedatacenterofmississippi/"
URL = "https://www.dropbox.com/scl/fi/z6fsf9i8vdd4kya20eqzt/State-of-Mississippi-Population-Projections-2020-2050.pdf?dl=1&rlkey=j2au553lzdzbtu0mdf7njflt7"
FILE = "state_population_2020-2050_may2019.pdf"
METHOD_FILE = "projection_methods_may2019.pdf"
FILES = {
    FILE: URL,
    METHOD_FILE: "https://web.archive.org/web/20190917012609id_/https://sdc.olemiss.edu/wp-content/uploads/sites/143/2019/05/Mississippi-Population-Projection-Methodology-2.pdf",
    "projection_catalog_2026-10-02.html": CATALOG_URL,
    "projection_catalog_archived2019.html": "https://web.archive.org/web/20190501000000id_/http://sdc.olemiss.edu/population-projections/",
}
SOURCE_ID = "ms-pop-preliminary-may2019"
AGENCY = "State Data Center of Mississippi, Center for Population Studies, University of Mississippi"
VINTAGE = "May 2, 2019 (preliminary)"
YEARS = (2020, 2025, 2030, 2035, 2040, 2045, 2050)
AGES = tuple(f"{age} - {age + 4}" for age in range(0, 85, 5)) + ("85 +",)
# All seven TOTAL / TOTAL / BOTH SEXES figures read from original rendered pages.
STATE_VALUES = (3066382, 3095026, 3104159, 3099766, 3082567, 3078363, 3064588)
# Published age sums minus published totals, across the nine columns. The
# methods explicitly warn that independently rounded counts need not add.
AGE_DIFFERENCES = ((0, 3, 0, 1, 0, 0, -1, -1, -2),
                   (0, 1, 2, 1, 0, -1, 0, 1, -1),
                   (1, -2, 0, -2, 1, 0, 1, 0, 0),
                   (1, 1, -2, 1, 0, -1, 0, 2, 1),
                   (-2, 0, 1, 1, 2, -1, 0, 0, 0),
                   (0, 1, -1, 2, 1, 0, 0, 1, 1),
                   (-1, 0, -1, 1, -1, 1, -1, 1, -1))


def _integer(token: str) -> int:
    if not re.fullmatch(r"(?:0|[1-9]\d{0,2}(?:,\d{3})*|[1-9]\d*)", token):
        raise ValueError("MS: invalid nonnegative integer population")
    return int(token.replace(",", ""))


def _parse_page(text: str, year: int) -> int:
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    indices = [i for i, line in enumerate(lines) if line.startswith("TOTAL ")]
    if len(indices) != 1:
        raise ValueError("MS: missing or duplicate population total")
    start = indices[0]
    if " ".join(lines[:start]) != " ".join(["BOTH SEXES MALE FEMALE"] * 3):
        raise ValueError("MS: unexpected sex-column header")
    data = lines[start:start + 19]
    footer = " ".join(lines[start + 19:])
    if footer not in (f"WHITE NONWHITE TOTAL Mississippi - {year}", f"Mississippi - {year} WHITE NONWHITE TOTAL"):
        raise ValueError("MS: unexpected state, race header or year grid")
    values = []
    for line, label in zip(data, ("TOTAL", *AGES), strict=True):
        fields = line.rsplit(" ", 9)
        if len(fields) != 10 or fields[0] != label:
            raise ValueError("MS: incomplete or changed age/column grid")
        cells = tuple(_integer(token) for token in fields[1:])
        # Each race/sex figure is rounded independently, allowing one-person
        # differences. These checks also catch column-order mistakes.
        if any(abs(cells[i + 1] + cells[i + 2] - cells[i]) > 1 for i in (0, 3, 6)):
            raise ValueError("MS: sex cells disagree beyond published rounding")
        if any(abs(cells[i] + cells[i + 3] - cells[i + 6]) > 1 for i in range(3)):
            raise ValueError("MS: race cells disagree beyond published rounding")
        values.append(cells)
    if len(values) != 19:
        raise ValueError("MS: incomplete age grid")
    differences = tuple(sum(row[i] for row in values[1:]) - values[0][i] for i in range(9))
    if differences != AGE_DIFFERENCES[YEARS.index(year)]:
        raise ValueError("MS: age/total rounding differences changed")
    return values[0][6]


def parse(body: bytes) -> list[dict]:
    from pypdf import PdfReader
    fetch.validate_pdf(body, "MS state population")
    reader = PdfReader(io.BytesIO(body))
    if len(reader.pages) != 7:
        raise ValueError("MS: incomplete state/year page grid")
    totals = tuple(_parse_page(page.extract_text() or "", year) for page, year in zip(reader.pages, YEARS, strict=True))
    if totals != STATE_VALUES:
        raise ValueError("MS: totals differ from independently rendered release")
    return [dict(state="MS", geo_level="state", geo_id="28", year=year, variable="population", value=value,
                 datatype="projection", source_id=SOURCE_ID)
            for year, value in zip(YEARS, totals, strict=True)]


def _validate_methods(body: bytes) -> None:
    from pypdf import PdfReader
    fetch.validate_pdf(body, "MS population methods")
    reader = PdfReader(io.BytesIO(body))
    if len(reader.pages) != 3:
        raise ValueError("MS: unexpected methods page grid")
    text = " ".join(" ".join((page.extract_text() or "").split()) for page in reader.pages)
    if any(marker not in text for marker in (
            "COUNTY AND STATE POPULATION PROJECTIONS FOR MISSISSIPPI, 2020 – 2050",
            "The State Data Center of Mississippi", "May 2, 2019", "Preliminary State Population Projections",
            "The launch year for the projections was 2010", "2000 and 2010 United States Census",
            "Due to rounding", "cohort component method")):
        raise ValueError("MS: unexpected producer, release edition or 2010 launch year")


def _validate_all(bodies: dict[str, bytes]) -> list[dict]:
    rows = parse(bodies[FILE])
    _validate_methods(bodies[METHOD_FILE])
    for name, markers in (
        ("projection_catalog_2026-10-02.html", ("State Data Center of Mississippi", "State-of-Mississippi-Population-Projections-2020-2050.pdf", "cohort component", "county")),
        ("projection_catalog_archived2019.html", ("State-of-Mississippi-Population-Projections-2020-2050.pdf", "Mississippi-Population-Projection-Methodology-2.pdf", "county level and place based population projections", "upon request"))):
        text = " ".join(bodies[name].decode("utf-8", "replace").split())
        if "<html" not in text.lower() or any(marker not in text for marker in markers):
            raise ValueError("MS: invalid publisher catalog or deferred geography evidence")
    return rows


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if {e["file"] for e in entries} != set(FILES):
            raise ValueError("MS: incomplete saved manifest")
        _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("MS acquire: reused validated May 2019 snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    rows = _validate_all(bodies)
    entries = []
    for name, url in FILES.items():
        fetch.write_snapshot(RAW_DIR / name, bodies[name])
        entries.append(dict(file=name, source=url, retrieved_at=date.today().isoformat(), sha256=fetch.sha256(bodies[name]),
                            records=len(rows) if name == FILE else None,
                            note="Original publisher bytes. Current linked table is byte-identical to archived September 2019 original; archived methods establish May 2, 2019 preliminary edition and 2010 launch. County/place projections on request are not loaded."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    if set(entries) != set(FILES):
        raise ValueError("MS: incomplete saved manifest")
    rows = _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
    if not conn.execute("SELECT 1 FROM geographies WHERE state='MS' AND geo_level='state' AND geo_id='28'").fetchone():
        raise ValueError("MS: state geography is not seeded")
    upsert_source(conn, source_id=SOURCE_ID, state="MS", agency=AGENCY,
        product_name="Preliminary State Population Projections 2020-2050: state TOTAL, both sexes and all races",
        vintage=VINTAGE, base_year=2010, horizon_year=2050, source_url=URL,
        retrieved_at=entries[FILE]["retrieved_at"],
        license="No explicit data license identified; cite the State Data Center of Mississippi, University of Mississippi.",
        citation="State Data Center of Mississippi, Center for Population Studies, University of Mississippi. Preliminary State Population Projections 2020-2050 (May 2, 2019 methods), pages 1-7, TOTAL / TOTAL / BOTH SEXES.",
        method_notes=("The currently linked seven-page PDF is byte-identical to the original archived 2019 publication. "
            "The original May 2, 2019 methods identify the edition as preliminary and explicitly set the launch year to 2010, with a 2000-2010 Census base period. "
            "It is not a forecast rebased to the 2020 Census. All seven published 2020-2050 five-year points remain projections, including past projection years; no 2010 row is fabricated. "
            "Units are independently rounded whole persons. This adapter selects only the statewide TOTAL race / BOTH SEXES column's TOTAL row, retaining its published values. "
            "Age, sex and source-specific race columns independently check totals, with documented rounding differences of up to three persons; no adjustment is applied. "
            "The cohort-component model holds fertility and survival rates constant and uses gross migration inputs from the 2000/2010 Census. "
            "The publisher explicitly offers county and place-based projections upon request, but only the downloadable state table is loaded; no correspondence was undertaken. "
            "Population and housing unit estimates are not household forecasts. Published household counts, complete future components and eligible SDO jobs coverage remain unverified."))
    insert_observations(conn, rows)
    conn.commit()
    print(f"MS load: {len(rows)} observations")


def verify(conn) -> None:
    rows = conn.execute("SELECT * FROM observations WHERE state='MS'").fetchall()
    assert len(rows) == 7 and {(r["geo_id"], r["year"]) for r in rows} == {("28", year) for year in YEARS}
    assert all(r["geo_level"] == "state" and r["scenario"] == "" and r["datatype"] == "projection"
               and r["variable"] == "population" and r["source_id"] == SOURCE_ID
               and r["age_group"] == r["sex"] == r["race"] == "all"
               and r["value"] >= 0 and float(r["value"]).is_integer() for r in rows)
    values = {r["year"]: r["value"] for r in rows}
    assert tuple(values[year] for year in YEARS) == STATE_VALUES
    source = conn.execute("SELECT * FROM sources WHERE source_id=?", (SOURCE_ID,)).fetchone()
    assert source["base_year"] == 2010 and source["horizon_year"] == 2050 and source["vintage"] == VINTAGE
    print("MS verify: seven rendered state totals, 2010 base, May 2019 edition and projection labels ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.ms --acquire")
