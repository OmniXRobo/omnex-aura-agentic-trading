"""REG acceptance: immutable research lineage, authorization and atomic transitions."""

import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aura.api import create_app
from aura.config import Settings
from aura.registry import RegistryAction, RegistryConflict, StrategyRegistry, StrategyVersion
from aura.store import Store


def spec(**updates):
    return StrategyVersion(**(dict(version_id='gold-v1', strategy_id='gold-research', family='breakout',
        hypothesis='Synthetic research hypothesis only', entry_method='Closed bar breakout for research',
        exit_method='Bounded stop and take profit research', cost_assumptions='Include spread commission slippage',
        risk_percent=.25) | updates))


def action(revision=1, **updates):
    return RegistryAction(**(dict(operation_id='operation-1', expected_revision=revision,
                                 action='annotate', reason='Synthetic research note only') | updates))


@pytest.fixture
def registry(tmp_path):
    return StrategyRegistry(Store(tmp_path))


def test_reg01_immutable_replay_lineage_and_restart(registry):
    original = registry.create(spec())
    assert registry.create(spec()) == original
    with pytest.raises(RegistryConflict):
        registry.create(spec(risk_percent=.1))
    child = registry.create(spec(version_id='gold-v2', parent_version='gold-v1'))
    assert child['spec']['parent_version'] == 'gold-v1'
    assert StrategyRegistry(Store(registry.store.directory)).get('gold-v2') == child
    with pytest.raises(RegistryConflict):
        registry.create(spec(version_id='bad', strategy_id='other', parent_version='gold-v1'))
    with pytest.raises(RegistryConflict):
        registry.create(spec(version_id='bad', parent_version='missing'))
    assert registry.store.killed()


def test_reg02_atomic_event_replay_and_stale_revision(registry):
    registry.create(spec())
    updated = registry.apply('gold-v1', action())
    assert updated['revision'] == 2
    assert registry.apply('gold-v1', action()) == updated
    with pytest.raises(RegistryConflict):
        registry.apply('gold-v1', action(reason='Different operation input here'))
    with pytest.raises(RegistryConflict):
        registry.apply('gold-v1', action(operation_id='other'))
    assert registry.get('gold-v1')['revision'] == 2


def test_reg03_concurrent_writers_only_one_revision_wins(registry):
    registry.create(spec())
    def append(index):
        try:
            registry.apply('gold-v1', action(operation_id=f'writer-{index}'))
            return True
        except RegistryConflict:
            return False
    with ThreadPoolExecutor(2) as executor:
        assert sum(executor.map(append, [1, 2])) == 1
    assert registry.get('gold-v1')['revision'] == 2


def test_reg04_review_requires_both_reference_types_and_never_approves(registry):
    registry.create(spec())
    with pytest.raises(RegistryConflict):
        registry.apply('gold-v1', action(action='request_review'))
    for revision, kind in enumerate(['backtest', 'validation'], 1):
        identifier = registry.store.record('historical', kind, dict(source='fixture', result='unverified'))
        registry.apply('gold-v1', action(revision, operation_id=kind, action='attach_evidence', record_id=identifier))
    result = registry.apply('gold-v1', action(3, action='request_review'))
    assert result['state'] == 'review_requested'
    assert not result['promotion_allowed'] and not result['execution_allowed']
    assert result['evidence_interpretation'] == 'references_only_not_strategy_validation'
    with pytest.raises(RegistryConflict):
        registry.apply('gold-v1', action(4, operation_id='post-review', action='attach_evidence', record_id=identifier))


def test_reg05_evidence_mutation_or_deletion_detected(registry):
    registry.create(spec())
    identifier = registry.store.record('historical', 'backtest', dict(source='fixture'))
    registry.apply('gold-v1', action(action='attach_evidence', record_id=identifier))
    with registry.store.connect() as db:
        db.execute('UPDATE records SET payload=? WHERE id=?', ('{}', identifier))
    with pytest.raises(RegistryConflict, match='changed'):
        registry.get('gold-v1')
    with pytest.raises(RegistryConflict):
        registry.apply('gold-v1', action(2, operation_id='next'))


def test_reg06_wrong_environment_kind_missing_duplicate_evidence(registry):
    registry.create(spec())
    for env, kind in [('virtual', 'backtest'), ('historical', 'agent_run')]:
        identifier = registry.store.record(env, kind, {})
        with pytest.raises(RegistryConflict):
            registry.apply('gold-v1', action(action='attach_evidence', record_id=identifier))
    identifier = registry.store.record('historical', 'backtest', {})
    registry.apply('gold-v1', action(action='attach_evidence', record_id=identifier))
    with pytest.raises(RegistryConflict):
        registry.apply('gold-v1', action(2, operation_id='duplicate', action='attach_evidence', record_id=identifier))


def test_reg07_suspend_archive_and_child_version(registry):
    registry.create(spec())
    assert registry.apply('gold-v1', action(action='suspend'))['state'] == 'suspended'
    with pytest.raises(RegistryConflict):
        registry.apply('gold-v1', action(2, operation_id='review', action='request_review'))
    assert registry.apply('gold-v1', action(2, operation_id='archive', action='archive'))['state'] == 'archived'
    with pytest.raises(RegistryConflict):
        registry.apply('gold-v1', action(3, operation_id='after-archive'))
    assert registry.create(spec(version_id='gold-v2', parent_version='gold-v1'))['state'] == 'draft'


def test_reg08_database_history_append_only_and_atomic_audit(registry, monkeypatch):
    registry.create(spec())
    for table in ['strategy_versions', 'strategy_events']:
        with registry.store.connect() as db:
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(f'DELETE FROM {table}')
    def fail(*args):
        raise ValueError('Injected audit failure')
    monkeypatch.setattr(registry, '_audit', fail)
    with pytest.raises(ValueError):
        registry.apply('gold-v1', action())
    assert registry.get('gold-v1')['revision'] == 1


@pytest.mark.parametrize('updates', [dict(risk_percent=1), dict(risk_percent=float('nan')),
    dict(sizing='double_after_loss'), dict(symbol='EURUSD'), dict(execution_allowed=True)])
def test_reg09_prohibited_spec_contract(updates):
    with pytest.raises(ValidationError):
        spec(**updates)


def test_reg10_auth_and_dashboard_projection(tmp_path):
    admin, viewer = 'a'*40, 'b'*40
    auth, read = {'Authorization': 'Bearer '+admin}, {'Authorization': 'Bearer '+viewer}
    with TestClient(create_app(Settings(tmp_path, admin, viewer))) as client:
        assert client.get('/v1/strategies').status_code == 401
        assert client.post('/v1/strategies', headers=read, json=spec().model_dump()).status_code == 403
        response = client.post('/v1/strategies', headers=auth, json=spec().model_dump())
        assert response.status_code == 200
        assert client.get('/v1/strategies/gold-v1', headers=read).json()['state'] == 'draft'
        assert client.post('/v1/strategies/gold-v1/actions', headers=auth,
                           json=action().model_dump() | dict(action='promote_live')).status_code == 422
        assert client.get('/v1/strategies?limit=101', headers=read).status_code == 422
        data = client.get('/v1/dashboard/overview', headers=read).json()
        assert data['strategies'][0]['spec']['version_id'] == 'gold-v1'
        assert 'events' not in data['strategies'][0]
        assert data['kill_switch'] and not data['live_enabled']


def test_reg11_cli_creates_only_research_and_rejects_bad_input(tmp_path):
    path = tmp_path / 'spec.json'
    path.write_text(spec().model_dump_json())
    command = [sys.executable, '-m', 'aura.strategy', '--data-dir', str(tmp_path / 'data')]
    result = subprocess.run(command+['--spec', str(path)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0
    assert not json.loads(result.stdout)['execution_allowed']
    result = subprocess.run(command+['--show', 'gold-v1'], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0 and json.loads(result.stdout)['state'] == 'draft'
    assert Store(tmp_path / 'data').killed()


def test_reg12_reject_extra_record_and_bound_event_growth(registry):
    registry.create(spec())
    with pytest.raises(RegistryConflict):
        registry.apply('gold-v1', action(record_id='unexpected'))
    for revision in range(1, 100):
        registry.apply('gold-v1', action(revision, operation_id=f'note-{revision}'))
    with pytest.raises(RegistryConflict, match='limit'):
        registry.apply('gold-v1', action(100, operation_id='too-many'))
    assert registry.get('gold-v1')['revision'] == 100


def test_reg13_isolated_fixture():
    from aura.registry_fixture import run_fixture

    result = run_fixture()
    assert result['versions'] == 2 and result['replay_identical']
    assert result['parent_state'] == 'suspended' and result['child_state'] == 'draft'
    assert result['emergency_stop_active']
    assert not result['existing_data_modified'] and not result['promotion_allowed']
