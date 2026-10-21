import json
import sqlite3

import pytest

from sdo_mcp import bundle, server


@pytest.fixture(scope='module')
def bundled(db_path, tmp_path_factory):
    return bundle.bundle_database(db_path, tmp_path_factory.mktemp('bundle') / 'sdo.sqlite')


def test_bundle_preserves_all_served_data(bundled, db_path, monkeypatch):
    with sqlite3.connect(bundled) as conn:
        conn.execute('ATTACH DATABASE ? AS full', (str(db_path),))
        for table in ('observations', 'sources', 'geographies', 'coverage'):
            a = f'SELECT * FROM main.{table}'
            b = f'SELECT * FROM full.{table}'
            if table == 'observations':
                b += f' WHERE {bundle.TOTALS}'
            assert not conn.execute(f'{a} EXCEPT {b}').fetchall()
            assert not conn.execute(f'{b} EXCEPT {a}').fetchall()
        metadata = json.loads(conn.execute('SELECT metadata FROM release_metadata').fetchone()[0])
    assert metadata['release_version'] == bundle.package_version()
    full_result = server.get_forecast('CO', 'county', 'Douglas', 'population')
    monkeypatch.setenv('SDO_DB', str(bundled))
    assert server.get_forecast('CO', 'county', 'Douglas', 'population') == full_result
    assert bundled.stat().st_size < db_path.stat().st_size / 5
    assert bundled.stat().st_mode & 0o044 == 0o044


def test_invalid_source_preserves_existing_bundle(tmp_path):
    source = tmp_path / 'error-page.sqlite'
    source.write_text('<html>government error</html>')
    output = tmp_path / 'sdo.sqlite'
    output.write_bytes(b'previous bundled copy')
    with pytest.raises(ValueError):
        bundle.bundle_database(source, output)
    assert output.read_bytes() == b'previous bundled copy'


def test_failed_check_leaves_no_partial_bundle(db_path, tmp_path, monkeypatch):
    output = tmp_path / 'sdo.sqlite'
    output.write_bytes(b'previous bundled copy')
    checked = []

    def reject_compact_copy(path):
        checked.append(path)
        if len(checked) > 1:
            raise ValueError('compact copy rejected')
        return path

    monkeypatch.setattr(bundle, 'validate_database', reject_compact_copy)
    with pytest.raises(ValueError, match='compact copy rejected'):
        bundle.bundle_database(db_path, output)
    assert output.read_bytes() == b'previous bundled copy'
    assert [p.name for p in tmp_path.iterdir()] == ['sdo.sqlite']
