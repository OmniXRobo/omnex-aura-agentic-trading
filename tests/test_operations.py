"""OPS acceptance: actual durable queue, exclusion, heartbeat and CLI recovery."""

import json
import subprocess
import sys
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from aura.api import create_app
from aura.config import Settings
from aura.operations import OperationsRunner, directory_lock, runtime_status
from aura.store import Store


def test_ops01_queue_restart_is_idempotent_with_stop_active(tmp_path):
    store = Store(tmp_path)
    store.enqueue('ops-snapshot', 'research.snapshot', dict(prices=[3000, 3001, 3002],
                                                         tick_age_seconds=1, source='fixture'))
    runner = OperationsRunner(store, clock=lambda: 100)
    runner.step()
    assert runtime_status(store, 100)['jobs_processed'] == 1
    OperationsRunner(Store(tmp_path), clock=lambda: 102).step()
    runs = [r for r in store.records('historical') if r['kind'] == 'agent_run']
    assert len(runs) == 1
    assert store.killed()
    assert not runtime_status(store, 102)['execution_allowed']
    with store.connect() as db:
        assert db.execute('SELECT state FROM jobs').fetchone()[0] == 'done'


def test_ops02_exclusive_os_lock_and_recovery(tmp_path):
    command = [sys.executable, '-c',
               'import sys; from pathlib import Path; from aura.operations import directory_lock; '
               'p=Path(sys.argv[1]); '\
               '\nwith directory_lock(p): print("acquired")', str(tmp_path)]
    with directory_lock(tmp_path):
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        assert result.returncode != 0
    result = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0 and result.stdout.strip() == 'acquired'


def test_ops03_heartbeat_stale_future_and_stopped(tmp_path):
    store = Store(tmp_path)
    assert runtime_status(store, 100)['state'] == 'not_started'
    runner = OperationsRunner(store, clock=lambda: 100)
    runner.step()
    assert runtime_status(store, 110)['state'] == 'running'
    assert runtime_status(store, 121)['state'] == 'stale'
    assert runtime_status(store, 99)['state'] == 'stale'
    runner.publish('stopped')
    status = runtime_status(store, 1000)
    assert status['state'] == 'stopped' and status['tasks'][0]['state'] == 'stopped'


def test_ops04_evaluator_retries_are_bounded_and_redacted(tmp_path):
    evaluator = Mock()
    evaluator.run_due.side_effect = ValueError('private-token-and-account-marker')
    store = Store(tmp_path)
    runner = OperationsRunner(store, [evaluator], clock=lambda: 100)
    for _ in range(5):
        runner.step()
    assert evaluator.run_due.call_count == 3
    status = runtime_status(store, 100)
    assert status['state'] == 'degraded'
    assert status['tasks'][1]['state'] == 'blocked'
    assert 'private-token' not in json.dumps(status)
    assert store.killed()


def test_ops05_transient_evaluation_failure_recovers(tmp_path):
    evaluator = Mock()
    evaluator.run_due.side_effect = [ValueError(), {}]
    store = Store(tmp_path)
    runner = OperationsRunner(store, [evaluator], clock=lambda: 100)
    runner.step()
    assert runtime_status(store, 100)['state'] == 'degraded'
    runner.step()
    assert runtime_status(store, 100)['state'] == 'running'


def test_ops06_missing_control_stops_polling(tmp_path):
    store = Store(tmp_path)
    with store.connect() as db:
        db.execute('DELETE FROM controls')
    runner = OperationsRunner(store)
    with pytest.raises(RuntimeError, match='Missing safety'):
        runner.step()
    assert runner.cycles == 0


def test_ops07_actual_cli_once_and_invalid_plan(tmp_path):
    directory = tmp_path / 'data with spaces'
    command = [sys.executable, '-m', 'aura.operations', '--data-dir', str(directory), '--once']
    result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0
    store = Store(directory)
    assert store.killed() and runtime_status(store)['state'] == 'stopped'
    before = len(store.records('historical'))
    bad = tmp_path / 'bad.json'
    bad.write_text('{"secret": "must-not-print"}')
    result = subprocess.run(command + ['--evaluation-plan', str(bad)], capture_output=True,
                            text=True, timeout=20)
    assert result.returncode == 1
    assert 'must-not-print' not in result.stdout + result.stderr
    assert len(store.records('historical')) == before
    assert store.killed()


def test_ops08_dashboard_runner_and_admin_data_path(tmp_path):
    admin, viewer = 'a'*40, 'b'*40
    store = Store(tmp_path)
    OperationsRunner(store).step()
    with TestClient(create_app(Settings(tmp_path, admin, viewer))) as client:
        response = client.get('/v1/dashboard/overview', headers={'Authorization': 'Bearer '+admin})
        assert response.json()['operations']['state'] == 'running'
        assert response.json()['storage']['directory'] == str(tmp_path.resolve())
        response = client.get('/v1/dashboard/overview', headers={'Authorization': 'Bearer '+viewer})
        assert str(tmp_path) not in response.text
        assert response.json()['storage']['directory'] == 'configured local directory'
        assert response.json()['kill_switch']


def test_ops09_real_evaluation_reports_remain_idempotent(tmp_path):
    from aura.dashboard_fixture import seed_dashboard
    from aura.virtual_evaluation import EvaluationPlan, VirtualEvaluator

    store = seed_dashboard(tmp_path)
    with store.connect('virtual') as db:
        plans = [EvaluationPlan.model_validate_json(row[0]) for row in
                 db.execute('SELECT config FROM virtual_eval_plans')]
        before = db.execute('SELECT count(*) FROM virtual_eval_reports').fetchone()[0]
    evaluator = VirtualEvaluator(store, plans[0])
    runner = OperationsRunner(store, [evaluator])
    runner.step()
    runner.step()
    with store.connect('virtual') as db:
        assert db.execute('SELECT count(*) FROM virtual_eval_reports').fetchone()[0] == before
    assert store.killed()


def test_ops10_abrupt_process_exit_releases_lock_and_leaves_stale_heartbeat(tmp_path):
    import time

    command = [sys.executable, '-m', 'aura.operations', '--data-dir', str(tmp_path)]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        store = Store(tmp_path)
        for _ in range(100):
            if runtime_status(store)['state'] == 'running':
                break
            time.sleep(.05)
        assert runtime_status(store)['state'] == 'running'
        process.kill()
        process.wait(timeout=10)
        assert runtime_status(store, time.time()+21)['state'] == 'stale'
        result = subprocess.run(command+['--once'], capture_output=True, timeout=20)
        assert result.returncode == 0
        assert runtime_status(store)['state'] == 'stopped'
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
