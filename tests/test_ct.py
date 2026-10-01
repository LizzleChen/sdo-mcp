"""Connecticut's old edition, historical boundaries and strict CSV grid."""
import io
import json
from functools import lru_cache

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import ct


@lru_cache
def _body():
    return (ct.RAW_DIR / ct.DATA_FILE).read_bytes()


def test_state_old_projection_years_and_metadata():
    result = server.get_forecast('CT', 'state', 'CT', 'population')
    assert result['status'] == 'ok'
    assert result['series'] == [dict(year=y, value=v, datatype='projection') for y, v in
        zip(ct.YEARS, (3593301, 3604603, 3618763, 3633994, 3645370, 3654015), strict=True)]
    assert result['source']['base_year'] == 2010
    assert result['source']['vintage'] == 'September 19, 2017 (revised)'
    assert result['source']['horizon_year'] == 2040
    assert result['source']['retrieved_at'] == '2026-10-01'
    assert '2023 metadata change is not a new model vintage' in result['source']['method_notes']
    assert result['source']['license'] == 'CC BY-SA 3.0'


@pytest.mark.parametrize('name,gid,value', [('Fairfield', '09001', 905219), ('Tolland', '09013', 154560), ('Windham', '09015', 134876)])
def test_historical_counties(name, gid, value):
    result = server.get_forecast('CT', 'county', name, 'population', 2040, 2040)
    assert result == server.get_forecast('CT', 'county', gid, 'population', 2040, 2040)
    assert result['series'] == [dict(year=2040, value=value, datatype='projection')]
    assert result['source']['vintage'] == 'June 29, 2018 (2017 model)'


def test_cogs_remain_distinct_from_modern_county_equivalents():
    result = server.get_forecast('CT', 'cog', 'Southeastern CT', 'population', 2040, 2040)
    assert result['series'] == [dict(year=2040, value=303785, datatype='projection')]
    assert result == server.get_forecast('CT', 'cog', 'ct-cog-southeastern-ct', 'population', 2040, 2040)
    assert server.get_forecast('CT', 'county', '09180', 'population')['status'] == 'error'
    assert server.get_forecast('CT', 'county', 'Southeastern CT', 'population')['status'] == 'error'
    assert server.get_forecast('CT', 'cog', 'Metropolitan', 'population')['status'] == 'ok'
    conn = store.connect()
    try:
        ct.verify(conn)
        assert conn.execute("SELECT COUNT(*) FROM geographies WHERE state='CT' AND geo_level='county'").fetchone()[0] == 8
        assert conn.execute("SELECT COUNT(*) FROM geographies WHERE state='CT' AND geo_level='cog'").fetchone()[0] == 9
    finally:
        conn.close()


def test_no_generated_years_or_unverified_products():
    assert server.get_forecast('CT', 'state', 'CT', 'population', 2026, 2029)['status'] == 'empty_range'
    assert server.get_forecast('CT', 'state', 'CT', 'population', 2041, 2050)['status'] == 'empty_range'
    assert server.get_forecast('CT', 'county_subdivision', 'Hartford', 'population')['status'] == 'not_loaded'
    for variable in ('households', 'employment'):
        assert server.get_forecast('CT', 'state', 'CT', variable)['status'] == 'coverage_unknown'
    assert server.get_components('CT', 'CT')['status'] == 'coverage_unknown'
    assert server.describe_source('CT')['review']['status'] == 'never_reviewed'


@pytest.mark.parametrize('old,new,error', [
    ('Year,Geography_Type', 'Period,Geography_Type', 'header'),
    ('2015,State', '2016,State', 'year'),
    ('2015,State,Connecticut', '2015,County,Connecticut', 'geography'),
    ('191445', '-1', 'integer'), ('191445', 'NaN', 'integer'),
    ('191445', '191.445', 'integer'), ('191445', '191450', 'sex totals'),
    ('3593301', '3593302', 'difference'),
])
def test_bad_table_rejected(old, new, error):
    body = _body()
    assert old.encode() in body
    with pytest.raises(ValueError, match=error):
        ct.parse(body.replace(old.encode(), new.encode(), 1))


def test_duplicate_missing_and_extra_rows_rejected():
    lines = _body().splitlines(keepends=True)
    for body, error in ((b''.join(lines[:-1]), 'incomplete'), (_body() + lines[1], 'duplicate'),
                        (_body() + b'2015,State,Connecticut,Total,1,2,3,4\n', 'malformed')):
        with pytest.raises(ValueError, match=error):
            ct.parse(body)


@pytest.mark.parametrize('body', [b'<html>200 OK temporary error</html>', b'[]', b''])
def test_soft_200_rejected(body):
    with pytest.raises(ValueError):
        ct.parse(body)


def test_changed_source_edition_rejected():
    name = 'dataset_metadata_2026-10-01.json'
    meta = json.loads((ct.RAW_DIR / name).read_bytes())
    meta['description'] = meta['description'].replace('September 19, 2017', 'September 19, 2023')
    with pytest.raises(ValueError, match='metadata'):
        ct._validate_evidence(name, json.dumps(meta).encode())


def test_snapshot_reuse_and_failed_download_preservation(tmp_path, monkeypatch):
    before = (ct.RAW_DIR / 'manifest.json').read_bytes()
    monkeypatch.setattr(ct.fetch, 'get_bytes', lambda *_: pytest.fail('unexpected network'))
    ct.acquire()
    assert (ct.RAW_DIR / 'manifest.json').read_bytes() == before
    original = ct.RAW_DIR
    bodies = {url: (original / name).read_bytes() for name, url in ct.FILES.items()}
    bodies[ct.URL] = b'<html>Service unavailable</html>'
    target = tmp_path / 'ct'
    monkeypatch.setattr(ct, 'RAW_DIR', target)
    monkeypatch.setattr(ct.fetch, 'get_bytes', lambda url: bodies[url])
    with pytest.raises(ValueError):
        ct.acquire()
    assert not target.exists()
