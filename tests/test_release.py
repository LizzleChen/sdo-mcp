import gzip
import json
import sqlite3

import pytest

from sdo_mcp import install, release, server


@pytest.fixture(scope='module')
def prepared(db_path, tmp_path_factory):
    output = tmp_path_factory.mktemp('release')
    folder = release.prepare_release(db_path, output, '2026-09-05-test')
    metadata = json.loads((folder / 'manifest.json').read_text())
    return folder, metadata


def test_release_preserves_all_served_data(prepared, db_path, tmp_path, monkeypatch):
    folder, metadata = prepared
    archive = folder / metadata['file']
    installed = install.install_release(archive, metadata['sha256'], tmp_path / 'installed.sqlite')
    assert release.file_sha256(installed) == metadata['database_sha256']
    with sqlite3.connect(installed) as conn:
        conn.execute('ATTACH DATABASE ? AS full', (str(db_path),))
        for table in ('observations', 'sources', 'geographies', 'coverage'):
            a = f'SELECT * FROM main.{table}'
            b = f'SELECT * FROM full.{table}'
            if table == 'observations':
                b += f' WHERE {release.TOTALS}'
            assert not conn.execute(f'{a} EXCEPT {b}').fetchall()
            assert not conn.execute(f'{b} EXCEPT {a}').fetchall()
        assert json.loads(conn.execute('SELECT metadata FROM release_metadata').fetchone()[0])['release_version'] == '2026-09-05-test'
    full_result = server.get_forecast('CO', 'county', 'Douglas', 'population')
    monkeypatch.setenv('SDO_DB', str(installed))
    assert server.get_forecast('CO', 'county', 'Douglas', 'population') == full_result
    assert metadata['database_size_bytes'] < db_path.stat().st_size / 5


def test_release_version_cannot_be_overwritten(prepared, db_path):
    folder, metadata = prepared
    with pytest.raises(FileExistsError):
        release.prepare_release(db_path, folder.parent, folder.name)
    assert release.file_sha256(folder / metadata['file']) == metadata['sha256']


def test_bad_archive_preserves_installed_database(prepared, tmp_path, monkeypatch):
    folder, metadata = prepared
    archive = folder / metadata['file']
    destination = tmp_path / 'installed.sqlite'
    destination.write_bytes(b'previous working database')
    with pytest.raises(ValueError, match='fingerprint mismatch'):
        install.install_release(archive, '0' * 64, destination)
    monkeypatch.setattr(install, 'MAX_DATABASE_BYTES', 100)
    with pytest.raises(ValueError, match='expanded release exceeds'):
        install.install_release(archive, metadata['sha256'], destination)
    assert destination.read_bytes() == b'previous working database'


def test_valid_fingerprint_does_not_accept_invalid_database(tmp_path):
    archive = tmp_path / 'bad.gz'
    archive.write_bytes(gzip.compress(b'<html>government error</html>'))
    destination = tmp_path / 'installed.sqlite'
    destination.write_bytes(b'previous working database')
    with pytest.raises(ValueError):
        install.install_release(archive, release.file_sha256(archive), destination)
    assert destination.read_bytes() == b'previous working database'
