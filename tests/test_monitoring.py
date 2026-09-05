"""Review reminders never stand in for evidence or actual loaded numbers."""

from datetime import date
import json
import sqlite3

import pytest

from sdo_mcp import monitoring, notes, server, store


def test_review_schedule():
    assert set(monitoring.POLICIES) == set(notes.STATES)
    for state in notes.STATES:
        assert monitoring.review_status(state, reviews={})['status'] == 'never_reviewed'
    reviews = {'WA': {'reviewed_on': '2026-09-05', 'findings': 'State and county products checked separately.',
                      'evidence': ['https://ofm.wa.gov/']}}
    before = monitoring.review_status('WA', today=date(2026, 12, 3), reviews=reviews)
    assert before['status'] == 'not_due'
    assert before['next_review_due'] == '2026-12-04'
    assert monitoring.review_status('WA', today=date(2026, 12, 4), reviews=reviews)['status'] == 'due'
    with pytest.raises(ValueError, match='after report date'):
        monitoring.review_status('WA', today=date(2026, 9, 4), reviews=reviews)
    reviews['WA']['evidence'] = []
    with pytest.raises(ValueError, match='evidence'):
        monitoring.review_status('WA', reviews=reviews)


def test_inventory_is_database_specific():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    store.init_db(conn)
    conn.execute("INSERT INTO coverage VALUES ('WA', 'components', 'county', 'available', 'Medium only')")
    conn.execute("INSERT INTO coverage VALUES ('WA', 'employment', 'state', 'pdf_only', 'PDF')")
    assert monitoring.coverage_inventory(conn, 'WA')['components']['county']['load_status'] == 'not_loaded'
    conn.execute("INSERT INTO observations VALUES ('WA','county','53001',2025,'births',10,'projection','medium','all','all','all','test')")
    entry = monitoring.coverage_inventory(conn, 'WA')['components']['county']
    assert entry['load_status'] == 'partially_loaded'
    assert entry['loaded_series'][0]['row_count'] == 1
    # Detail rows are not queryable totals and must not make this look complete.
    conn.execute("INSERT INTO observations VALUES ('WA','county','53001',2025,'deaths',3,'projection','medium','0-4','all','all','test')")
    assert monitoring.coverage_inventory(conn, 'WA')['components']['county']['load_status'] == 'partially_loaded'
    for variable in ('deaths', 'net_migration'):
        conn.execute("INSERT INTO observations VALUES ('WA','county','53001',2025,?,3,'projection','medium','all','all','all','test')", (variable,))
    entry = monitoring.coverage_inventory(conn, 'WA')
    assert entry['components']['county']['load_status'] == 'loaded'
    assert entry['employment']['state']['status'] == 'pdf_only'
    assert entry['employment']['state']['load_status'] == 'not_loaded'
    conn.close()


def test_tools_and_report(db_path, capsys, monkeypatch):
    result = server.list_states()
    wa = result['states']['WA']
    assert wa['variables']['components']['county']['load_status'] == 'loaded'
    assert wa['variables']['employment']['state']['load_status'] == 'not_loaded'
    assert wa['variables']['employment']['state']['status'] == 'pdf_only'
    source = server.describe_source('WA')
    assert source['variables'] == wa['variables']
    assert source['review'] == wa['review']
    conn = store.connect(db_path)
    try:
        report = monitoring.report(conn)
    finally:
        conn.close()
    assert set(report) == set(notes.STATES)
    assert report['WA']['variables'] == wa['variables']
    assert report['WA']['sources_loaded']
    monkeypatch.setattr("sys.argv", ["monitoring"])
    monitoring.main()
    assert json.loads(capsys.readouterr().out)['WA']['variables'] == wa['variables']
