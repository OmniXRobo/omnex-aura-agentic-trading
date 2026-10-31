"""DIA acceptance: real evaluator input, immutable triage, bounded recovery and auth."""

import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from aura.api import create_app
from aura.backup import create_backup, restore_backup
from aura.config import Settings
from aura.dashboard_fixture import seed_dashboard
from aura.diagnostic_fixture import run_fixture
from aura.diagnostics import DiagnosticError, VirtualDiagnostics, read_diagnostics, triage
from aura.operations import OperationsRunner, runtime_status
from aura.store import Store


@pytest.fixture
def store(tmp_path):
    return seed_dashboard(tmp_path)


def source(store):
    with store.connect('virtual') as db:
        return json.loads(db.execute('SELECT payload FROM virtual_eval_reports ORDER BY rowid LIMIT 1').fetchone()[0])


def test_dia01_real_evaluator_restart_and_source_unchanged(store):
    before = source(store)
    assert VirtualDiagnostics(store).run_batch()['created'] == 3
    assert VirtualDiagnostics(Store(store.directory)).run_batch()['created'] == 0
    reports = read_diagnostics(store)
    assert len(reports) == 3
    assert source(store) == before and store.killed()
    assert all(r['source'] == 'fixture' and not r['promotion_allowed'] for r in reports)
    assert all(r['statistical_drift'] == 'not_tested' for r in reports)
    assert any(f['code'] == 'insufficient_sample' for r in reports for f in r['findings'])


def test_dia02_bounded_batches_and_concurrent_cursor(store):
    engine = VirtualDiagnostics(store)
    assert engine.run_batch(1)['created'] == 1
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(lambda _: engine.run_batch(1), range(2)))
    assert sum(r['created'] for r in results) == 2
    assert len(read_diagnostics(store)) == 3
    assert engine.run_batch()['created'] == 0


def test_dia03_negative_pnl_is_review_not_causal_claim(store):
    report = source(store)
    report.update(closed_trades=1, losses=1, wins=0, flat_trades=0, quote_events=2,
                  net_closed_pnl='-5', closed_trade_commission='1')
    result = triage(report)
    assert {'negative_net_pnl', 'costs_present'} <= {f['code'] for f in result['findings']}
    assert result['causal_diagnosis'] == 'not_established'
    assert not result['risk_changes_applied'] and not result['strategy_changes_applied']


@pytest.mark.parametrize('updates', [dict(execution_allowed=True), dict(net_closed_pnl='NaN'),
    dict(closed_trades=True), dict(closed_trade_commission='-1'), dict(days=7),
    dict(source='live'), dict(quality_flags='invalid')])
def test_dia04_invalid_or_prohibited_evidence_rejected(store, updates):
    with pytest.raises(DiagnosticError):
        triage(source(store) | updates)


def test_dia05_append_only_and_original_digest_checked(store):
    engine = VirtualDiagnostics(store)
    engine.run_batch()
    with store.connect('virtual') as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('DELETE FROM virtual_diagnostics')
        # Simulate local administrator bypass of an original evidence trigger.
        db.execute('DROP TRIGGER virtual_eval_reports_no_update')
        db.execute("UPDATE virtual_eval_reports SET payload='{}' WHERE rowid=1")
    with pytest.raises(DiagnosticError, match='changed'):
        read_diagnostics(store)


def test_dia06_failed_batch_rolls_back_cursor_and_reports(store, monkeypatch):
    import aura.diagnostics as module

    engine = VirtualDiagnostics(store)
    original = module.triage
    calls = []
    def fail_second(report):
        calls.append(1)
        if len(calls) == 2:
            raise DiagnosticError('Injected invalid evidence')
        return original(report)
    monkeypatch.setattr(module, 'triage', fail_second)
    with pytest.raises(DiagnosticError):
        engine.run_batch()
    with store.connect('virtual') as db:
        assert db.execute('SELECT count(*) FROM virtual_diagnostics').fetchone()[0] == 0
        assert db.execute('SELECT source_row FROM virtual_diagnostic_cursor').fetchone()[0] == 0
    monkeypatch.setattr(module, 'triage', original)
    assert engine.run_batch()['created'] == 3


def test_dia07_runner_processes_reports_and_blocks_repeated_failures(store):
    runner = OperationsRunner(store)
    runner.step()
    assert len(read_diagnostics(store)) == 3
    runner.diagnostics = Mock()
    runner.diagnostics.run_batch.side_effect = ValueError('private-marker')
    for _ in range(5):
        runner.step()
    assert runner.diagnostics.run_batch.call_count == 3
    status = runtime_status(store)
    assert status['state'] == 'degraded' and status['tasks'][-1]['state'] == 'blocked'
    assert 'private-marker' not in json.dumps(status)
    assert store.killed()


def test_dia08_auth_and_dashboard(store):
    admin, viewer = 'a'*40, 'b'*40
    auth, read = {'Authorization': 'Bearer '+admin}, {'Authorization': 'Bearer '+viewer}
    with TestClient(create_app(Settings(store.directory, admin, viewer))) as client:
        assert client.get('/v1/virtual/diagnostics').status_code == 401
        assert client.post('/v1/virtual/diagnostics/run', headers=read).status_code == 403
        assert client.post('/v1/virtual/diagnostics/run', headers=auth).json()['created'] == 3
        assert len(client.get('/v1/virtual/diagnostics', headers=read).json()) == 3
        assert len(client.get('/v1/dashboard/overview', headers=read).json()['diagnostics']) == 3
        assert client.get('/v1/virtual/diagnostics?limit=101', headers=read).status_code == 422


def test_dia09_empty_missing_safety_and_limits(tmp_path):
    store = Store(tmp_path)
    assert read_diagnostics(store) == []
    engine = VirtualDiagnostics(store)
    assert engine.run_batch()['state'] == 'no_evaluations'
    with pytest.raises(ValueError):
        engine.run_batch(0)
    with store.connect() as db:
        db.execute('DELETE FROM controls')
    with pytest.raises(RuntimeError):
        engine.run_batch()


def test_dia10_cli_fixture_and_recovery_schema(store, tmp_path):
    result = subprocess.run([sys.executable, '-m', 'aura.diagnose_virtual', '--data-dir', str(store.directory)],
                             capture_output=True, text=True, timeout=20)
    assert result.returncode == 0 and json.loads(result.stdout)['created'] == 3
    bundle = create_backup(store.directory, tmp_path.parent / (tmp_path.name+'-backup'))
    restored = Store(restore_backup(bundle, tmp_path.parent / (tmp_path.name+'-restored')))
    assert len(read_diagnostics(restored)) == 3 and restored.killed()
    assert VirtualDiagnostics(restored).run_batch()['created'] == 0
    result = run_fixture()
    assert result['diagnostics_created'] == 3 and result['replay_new_diagnostics'] == 0
    assert result['all_review_only'] and result['emergency_stop_active']


def test_dia11_malformed_json_and_unknown_flags_fail_safely(store):
    from aura.diagnostics import parse_payload

    for value in ('{invalid', '[]', 'null'):
        with pytest.raises(DiagnosticError):
            parse_payload(value)
    report = source(store)
    report['quality_flags'].append('new_future_flag')
    result = triage(report)
    assert 'unrecognized_quality_flag' in {f['code'] for f in result['findings']}
    assert not result['promotion_allowed']
