"""Iowa archival state-demographer PDF: checked OCR, old horizon and exact grid."""
import io
from functools import lru_cache

import pytest
from pypdf import PdfReader, PdfWriter

from sdo_mcp import server, store
from sdo_mcp.ingest import ia


@lru_cache
def _body():
    return (ia.RAW_DIR / ia.FILE).read_bytes()


@lru_cache
def _summary():
    return PdfReader(io.BytesIO(_body())).pages[4].extract_text()


def test_original_state_county_grid_and_explicit_history_boundary():
    rows = ia.parse(_body())
    assert len(rows) == 500
    assert {row['geo_id'] for row in rows if row['geo_level'] == 'county'} == set(ia._counties().values())
    assert {row['year'] for row in rows} == {1980, 1985, 1990, 1995, 2000}
    assert sum(row['datatype'] == 'estimate' for row in rows) == 100
    assert all(row['datatype'] == ('estimate' if row['year'] == 1980 else 'projection') for row in rows)
    assert all(row['source_id'] == ia.SOURCE_ID for row in rows)
    assert tuple(row['value'] for row in rows if row['geo_level'] == 'state') == ia.STATE_VALUES
    totals = ia.parse_summary(_summary())
    assert totals['ADAIR'] == (9509, 9100, 8700, 8500, 8300)
    assert totals['POLK'] == (303170, 309900, 316100, 321600, 326900)
    assert totals['OSCEOLA'] == (8371, 8100, 7900, 7800, 7800)
    assert totals['UNION'] == (13858, 14000, 14100, 14200, 14400)
    assert totals['FAYETTE'] == (25488, 24700, 24200, 24000, 23900)
    assert 'REGION 1' not in totals
    assert tuple(sum(totals[name][i] for name in ia._counties()) - ia.STATE_VALUES[i]
                 for i in range(5)) == (0, 500, -300, 400, 100)


def test_offline_load_checks_all_published_values_and_source_metadata(tmp_path):
    conn = store.connect(tmp_path / 'iowa.sqlite', create=True)
    try:
        store.init_db(conn)
        ia.load(conn)
        ia.verify(conn)
        source = dict(conn.execute('SELECT * FROM sources WHERE state="IA"').fetchone())
        assert source['base_year'] == 1980 and source['horizon_year'] == 2000
        assert source['vintage'] == 'July 1984 (archival edition)'
        assert source['retrieved_at'] == '2026-10-02' and source['source_url'] == ia.URL
        assert 'entire projected 1985-2000 horizon is in the past' in source['method_notes']
        assert 'December 1989' in source['method_notes']
        assert 'No explicit data license' in source['license']
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
        conn.execute("UPDATE observations SET value=value+100 WHERE geo_id='19153' AND year=2000")
        with pytest.raises(ValueError, match='loaded observations'):
            ia.verify(conn)
    finally:
        conn.close()


@pytest.mark.parametrize('old,new', [
    ('JULY 1984', 'JULY 1989'),
    ('AREA 1980 1985 1990 1995 2000', 'AREA 1980 1985 1990 1995 2001'),
    ('2,965,000', '2,965,100'), ('309,900', '309,800'),
    ('9,509', '-9509'), ('9,509', 'NaN'), ('9,509', '9509.5'), ('9,509', ''),
    ('ADAIR', 'MISSING'), ('HAPELLO', 'HAPELL'), ('WRIGHT', 'ADAIR'),
    ('8,:wo', '8,:w0'), ('211,000', '211,100'),
])
def test_source_changes_missing_cells_and_unknown_ocr_are_rejected(old, new):
    text = _summary()
    assert old in text
    with pytest.raises(ValueError, match='IA:'):
        ia.parse_summary(text.replace(old, new, 1))


def test_extra_or_duplicate_geography_rows_rejected():
    for suffix in ('\nADAIR 9509 9100 8700 8500 8300', '\nUnknown 1 2 3 4 5'):
        with pytest.raises(ValueError, match='IA:'):
            ia.parse_summary(_summary() + suffix)


@pytest.mark.parametrize('body', [b'<html>Service unavailable</html>', b'%PDF-broken', b'[]'])
def test_soft_200_pdf_rejected(body):
    with pytest.raises(ValueError, match='readable PDF'):
        ia.parse(body)


def test_wrong_readable_pdf_and_missing_pages_rejected():
    writer = PdfWriter()
    writer.add_blank_page(612, 792)
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(ValueError, match='page count'):
        ia.parse(output.getvalue())


def test_reuse_is_offline_and_preserves_retrieval_date(monkeypatch):
    before = (ia.RAW_DIR / 'manifest.json').read_bytes()
    monkeypatch.setattr(ia.fetch, 'get_bytes', lambda *_: pytest.fail('unexpected network call'))
    ia.acquire()
    assert (ia.RAW_DIR / 'manifest.json').read_bytes() == before


@pytest.mark.parametrize('failed_file', list(ia.FILES))
def test_bad_report_or_evidence_archives_nothing(tmp_path, monkeypatch, failed_file):
    bodies = {url: (ia.RAW_DIR / name).read_bytes() for name, url in ia.FILES.items()}
    bodies[ia.FILES[failed_file]] = b'<html>temporary error</html>'
    raw = tmp_path / 'ia'
    monkeypatch.setattr(ia, 'RAW_DIR', raw)
    monkeypatch.setattr(ia.fetch, 'get_bytes', lambda url: bodies[url])
    with pytest.raises(ValueError):
        ia.acquire()
    assert not raw.exists()


def test_served_archival_edition_and_unknown_additional_products():
    result = server.get_forecast('IA', 'state', 'Iowa', 'population')
    assert result['status'] == 'ok' and result['scenario'] is None
    assert result['series'] == [dict(year=year, value=value, datatype='estimate' if year == 1980 else 'projection')
                                for year, value in zip(ia.YEARS, ia.STATE_VALUES)]
    assert result['source']['vintage'] == ia.VINTAGE
    assert server.get_forecast('IA', 'county', 'Polk', 'population')['series'][-1]['value'] == 326900
    assert server.get_forecast('IA', 'county', '19153', 'population')['status'] == 'ok'
    assert server.get_forecast('IA', 'state', 'IA', 'population', 2001, 2060)['status'] == 'empty_range'
    assert server.get_forecast('IA', 'state', 'IA', 'population', 1986, 1989)['status'] == 'empty_range'
    assert server.get_forecast('IA', 'state', 'IA', 'population', scenario='medium')['status'] == 'error'
    for variable in ('households', 'employment'):
        assert server.get_forecast('IA', 'state', 'IA', variable)['status'] == 'coverage_unknown'
    assert server.get_forecast('IA', 'place', 'Des Moines', 'population')['status'] == 'coverage_unknown'
    assert server.get_components('IA', 'IA')['status'] == 'coverage_unknown'
    assert server.describe_source('IA')['review']['status'] == 'never_reviewed'
