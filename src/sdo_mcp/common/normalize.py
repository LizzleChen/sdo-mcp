"""Shared normalization: datatype wording and FIPS helpers."""

from __future__ import annotations

# Each state words its estimate/projection flag differently — CO alone uses
# Estimate/Projection, Estimate/Forecast, and ESTIMATE/PROJECTION on different
# endpoints. Everything collapses to exactly two values; anything unrecognized
# is an ingest error, never a silent default.
_DATATYPE = {
    "estimate": "estimate",
    "estimates": "estimate",
    "projection": "projection",
    "projections": "projection",
    "forecast": "projection",
}


def norm_datatype(raw: str) -> str:
    try:
        return _DATATYPE[raw.strip().lower()]
    except KeyError:
        raise ValueError(f"unrecognized datatype flag: {raw!r}") from None


def county_geo_id(state_fips: str, county_code: int | str) -> str:
    """5-digit county FIPS from a state prefix + county code (CO's API uses
    bare 3-digit codes like 35, not 08035)."""
    return f"{state_fips}{int(county_code):03d}"
