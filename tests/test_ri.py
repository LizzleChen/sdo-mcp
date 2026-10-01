"""Rhode Island published state and municipal forecasts and their identities."""
import io
from functools import lru_cache

import pytest
from pypdf import PdfReader, PdfWriter

from sdo_mcp import server, store
from sdo_mcp.ingest import ri


@lru_cache
def _geos():
    return ri.parse_geographies((ri.RAW_DIR / 'census_cousubs_2025.txt').read_bytes())


@lru_cache
def _text():
    return PdfReader(ri.RAW_DIR / ri.FILE).pages[0].extract_text()


def test_state_published_total_and_unknown_base():
    result = server.get_forecast('RI', 'state', 'Rhode Island', 'population')
    assert result['status'] == 'ok'
    assert result['series'] == [dict(year=y, value=v, datatype='projection') for y, v in zip(ri.YEARS, ri.STATE_VALUES, strict=True)]
    assert result['source']['base_year'] is None
    assert result['source']['vintage'] == 'February 27, 2026 (revised)'
    assert result['source']['horizon_year'] == 2050
    assert result['source']['retrieved_at'] == '2026-10-01'
    assert 'base_year is therefore null' in result['source']['method_notes']


@pytest.mark.parametrize('name,gid,year,value', [
    ('Barrington', '4400105140', 2050, 17299),
    ('East Providence', '4400722960', 2050, 44994),
    ('North Kingstown', '4400951580', 2025, 27916),
    ('Providence', '4400759000', 2050, 201447),
    ('Woonsocket', '4400780780', 2050, 42240),
])
def test_municipal_names_and_ten_digit_ids(name, gid, year, value):
    result = server.get_forecast('RI', 'county_subdivision', name, 'population', year, year)
    assert result == server.get_forecast('RI', 'county_subdivision', gid, 'population', year, year)
    assert result['series'] == [dict(year=year, value=value, datatype='projection')]
    assert result['geo']['level'] == 'county_subdivision'


def test_exact_full_name_beats_partial_candidates():
    result = server.get_forecast('RI', 'county_subdivision', 'Providence', 'population')
    assert result['geo']['id'] == '4400759000'
    ambiguous = server.get_forecast('RI', 'county_subdivision', 'Kingstown', 'population')
    assert ambiguous['status'] == 'error'
    assert len(ambiguous['candidates']) == 2
    assert server.get_forecast('RI', 'county_subdivision', '4459000', 'population')['status'] == 'error'
    assert server.get_forecast('RI', 'county_subdivision', '4400500000', 'population')['status'] == 'error'


def test_complete_grid_no_derived_counties_or_generated_points():
    conn = store.connect()
    try:
        ri.verify(conn)
        assert conn.execute("SELECT COUNT(*) FROM observations WHERE state='RI' AND geo_level='county'").fetchone()[0] == 0
    finally:
        conn.close()
    assert server.get_forecast('RI', 'county', 'Providence', 'population')['status'] == 'coverage_unknown'
    assert server.get_forecast('RI', 'place', 'Providence', 'population')['status'] == 'coverage_unknown'
    for bounds in ((2026, 2029), (2020, 2024), (2051, 2060)):
        assert server.get_forecast('RI', 'state', 'RI', 'population', *bounds)['status'] == 'empty_range'
    for variable in ('households', 'employment'):
        assert server.get_forecast('RI', 'state', 'RI', variable)['status'] == 'coverage_unknown'
    assert server.get_components('RI', 'RI')['status'] == 'coverage_unknown'
    assert server.describe_source('RI')['review']['status'] == 'never_reviewed'


@pytest.mark.parametrize('old,new,error', [
    ('City/Town', 'Municipality', 'header'), ('Revised 2/27/26', 'Revised 2/27/25', 'edition'),
    ('Barrington', 'Unknown Town', 'unknown'), ('Barrington', 'Bristol', 'duplicate'),
    ('17,267', '-1', 'integer'), ('17,267', 'NaN', 'integer'), ('17,267', '17.267', 'integer'),
    ('17,267', '17,268', 'difference'), ('1,134,854', '1,134,855', 'state totals'),
])
def test_corrupt_pdf_table_rejected(old, new, error):
    text = _text()
    assert old in text
    with pytest.raises(ValueError, match=error):
        ri.parse_table(text.replace(old, new, 1), _geos())


def test_missing_municipality_rejected():
    text = '\n'.join(line for line in _text().splitlines() if not line.startswith('Westerly '))
    with pytest.raises(ValueError, match='incomplete'):
        ri.parse_table(text, _geos())


@pytest.mark.parametrize('old,new,error', [
    ('USPS|GEOID|', 'ST|ID|', 'header'), ('4400105140', '445140', 'invalid'),
    ('Barrington town', 'Barrington city', 'invalid'),
    ('Barrington town', 'Unknown town', 'invalid'),
    ('4400500000', '4400500001', 'undefined'),
])
def test_corrupt_geography_reference_rejected(old, new, error):
    body = (ri.RAW_DIR / 'census_cousubs_2025.txt').read_bytes()
    with pytest.raises(ValueError, match=error):
        ri.parse_geographies(body.replace(old.encode(), new.encode()))


@pytest.mark.parametrize('body', [b'<html>Service unavailable</html>', b'%PDF-broken', b'[]'])
def test_soft_200_rejected(body):
    with pytest.raises(ValueError, match='readable'):
        ri.parse(body, _geos())


def test_wrong_readable_pdf_rejected():
    writer = PdfWriter(); writer.add_blank_page(612, 792)
    output = io.BytesIO(); writer.write(output)
    with pytest.raises(ValueError, match='header'):
        ri.parse(output.getvalue(), _geos())


def test_snapshot_reuse_and_failed_acquisition(tmp_path, monkeypatch):
    before = (ri.RAW_DIR / 'manifest.json').read_bytes()
    monkeypatch.setattr(ri.fetch, 'get_bytes', lambda *_: pytest.fail('unexpected network'))
    ri.acquire()
    assert (ri.RAW_DIR / 'manifest.json').read_bytes() == before
    original = ri.RAW_DIR
    bodies = {url: (original / name).read_bytes() for name, url in ri.FILES.items()}
    bodies[ri.GEO_URL] = b'<html>temporary error</html>'
    target = tmp_path / 'ri'
    monkeypatch.setattr(ri, 'RAW_DIR', target)
    monkeypatch.setattr(ri.fetch, 'get_bytes', lambda url: bodies[url])
    with pytest.raises(ValueError):
        ri.acquire()
    assert not target.exists()
