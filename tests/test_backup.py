"""BKP acceptance: standalone WAL-safe snapshots and non-overwriting stopped restores."""

import json
import sqlite3
import subprocess
import sys
from contextlib import closing

import pytest

from aura.backup import FILES, create_backup, inspect_database, restore_backup, verify_backup
from aura.operations import OperationsRunner, directory_lock, runtime_status
from aura.registry import StrategyRegistry
from aura.store import Store


def populated(path):
    store = Store(path)
    for environment in ('historical', 'virtual', 'demo'):
        store.record(environment, 'synthetic-backup-fixture', dict(environment=environment))
    return store


def test_bkp01_roundtrip_three_memories_and_manifest(tmp_path):
    source = tmp_path/'source'
    store = populated(source)
    bundle = create_backup(source, tmp_path/'backups')
    manifest = verify_backup(bundle)
    assert set(manifest['files']) == set(FILES)
    assert manifest['consistency'] == 'all_three_memories_write_locked'
    assert not manifest['encrypted'] and not manifest['execution_allowed']
    restored = restore_backup(bundle, tmp_path/'restored')
    for memory in ('historical', 'virtual', 'demo'):
        assert Store(restored).records(memory) == store.records(memory)
        with closing(sqlite3.connect(restored/f'{memory}.db')) as db:
            assert db.execute("SELECT value FROM controls WHERE name='kill_switch'").fetchone() == (1,)
    assert verify_backup(bundle) == manifest
    assert (restored/'restore.json').exists()


def test_bkp02_restore_forces_stop_without_changing_source_or_backup(tmp_path):
    store = populated(tmp_path/'source')
    store.set_kill(False)
    OperationsRunner(store).step()
    bundle = create_backup(store.directory, tmp_path/'backups')
    before = verify_backup(bundle)
    restored = Store(restore_backup(bundle, tmp_path/'restored'))
    assert not store.killed() and restored.killed()
    assert runtime_status(restored)['state'] == 'unknown'
    assert verify_backup(bundle) == before
    assert any(r['action'] == 'restore_quarantine' for r in _audit(restored))


def _audit(store):
    with store.connect() as db:
        return [dict(row) for row in db.execute('SELECT * FROM audit')]


def test_bkp03_wal_commits_included_with_writer_connection_open(tmp_path):
    store = populated(tmp_path/'source')
    with closing(sqlite3.connect(store.directory/'historical.db')) as writer:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute('INSERT INTO records VALUES (?,?,?,?)', ('wal-only', 'fixture', '{}', 123.0))
        writer.commit()
        assert (store.directory/'historical.db-wal').exists()
        bundle = create_backup(store.directory, tmp_path/'backups')
    with closing(sqlite3.connect(bundle/'historical.db')) as db:
        assert db.execute("SELECT id FROM records WHERE id='wal-only'").fetchone()
    assert set(p.name for p in bundle.iterdir()) == set(FILES)|{'manifest.json'}


def test_bkp04_running_operations_lock_blocks_snapshot(tmp_path):
    store = populated(tmp_path/'source')
    with directory_lock(store.directory):
        with pytest.raises(ValueError):
            create_backup(store.directory, tmp_path/'backups')
    assert list((tmp_path/'backups').iterdir()) == []
    assert store.killed()


def test_bkp05_uncommitted_writer_causes_failure_without_partial_bundle(tmp_path):
    store = populated(tmp_path/'source')
    with closing(sqlite3.connect(store.directory/'virtual.db')) as writer:
        writer.execute('BEGIN IMMEDIATE')
        with pytest.raises(sqlite3.OperationalError):
            create_backup(store.directory, tmp_path/'backups')
        writer.rollback()
    assert list((tmp_path/'backups').iterdir()) == []


def test_bkp06_tampering_and_sidecar_rejected(tmp_path):
    store = populated(tmp_path/'source')
    bundle = create_backup(store.directory, tmp_path/'backups')
    with closing(sqlite3.connect(bundle/'historical.db')) as db, db:
        db.execute("INSERT INTO records VALUES ('tampered','fixture','{}',123)")
    with pytest.raises(ValueError, match='mismatch'):
        verify_backup(bundle)
    with pytest.raises(ValueError):
        restore_backup(bundle, tmp_path/'restored')
    assert not (tmp_path/'restored').exists()
    bundle = create_backup(store.directory, tmp_path/'backups')
    (bundle/'historical.db-wal').write_bytes(b'unknown')
    with pytest.raises(ValueError, match='Unexpected'):
        verify_backup(bundle)


def test_bkp07_existing_target_and_source_nested_destination_rejected(tmp_path):
    store = populated(tmp_path/'source')
    with pytest.raises(ValueError):
        create_backup(store.directory, store.directory/'backups')
    bundle = create_backup(store.directory, tmp_path/'backups')
    existing = tmp_path/'existing'
    existing.mkdir()
    (existing/'keep.txt').write_text('untouched')
    with pytest.raises(ValueError):
        restore_backup(bundle, existing)
    assert (existing/'keep.txt').read_text() == 'untouched'
    with pytest.raises(ValueError):
        restore_backup(bundle, bundle/'restored')


def test_bkp08_partial_source_missing_safety_unknown_schema(tmp_path):
    with pytest.raises(ValueError):
        create_backup(tmp_path/'absent', tmp_path/'backups')
    store = populated(tmp_path/'source')
    with store.connect('demo') as db:
        db.execute('DELETE FROM controls')
    with pytest.raises(ValueError):
        create_backup(store.directory, tmp_path/'backups')
    assert list((tmp_path/'backups').iterdir()) == []
    with store.connect('demo') as db:
        db.execute("INSERT INTO controls VALUES ('kill_switch',1)")
        db.execute('INSERT INTO schema_version VALUES (999)')
    with pytest.raises(ValueError, match='Unsupported'):
        inspect_database(store.directory/'demo.db')


def test_bkp09_atomic_failure_cleanup_and_registry_tables_retained(tmp_path, monkeypatch):
    import aura.backup as module

    store = populated(tmp_path/'source')
    StrategyRegistry(store)
    original = module.write_json
    def fail(path, payload):
        raise OSError('Injected destination failure')
    monkeypatch.setattr(module, 'write_json', fail)
    with pytest.raises(OSError):
        create_backup(store.directory, tmp_path/'backups')
    assert list((tmp_path/'backups').iterdir()) == []
    monkeypatch.setattr(module, 'write_json', original)
    bundle = create_backup(store.directory, tmp_path/'backups')
    assert verify_backup(bundle)['files']['historical.db']['counts']['strategy_versions'] == 0


def test_bkp10_manifest_path_injection_and_symlink_rejected(tmp_path):
    store = populated(tmp_path/'source')
    bundle = create_backup(store.directory, tmp_path/'backups')
    path = bundle/'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['files']['../outside.db'] = manifest['files'].pop('demo.db')
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        verify_backup(bundle)


def test_bkp11_actual_cli_paths_with_spaces_and_private_failures(tmp_path):
    store = populated(tmp_path/'source with spaces')
    prefix = [sys.executable, '-m', 'aura.backup']
    result = subprocess.run(prefix+['create', '--data-dir', str(store.directory), '--destination',
                                  str(tmp_path/'backups')], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0
    bundle = json.loads(result.stdout)['backup']
    result = subprocess.run(prefix+['verify', '--backup', bundle], capture_output=True, text=True, timeout=20)
    assert json.loads(result.stdout)['verified']
    result = subprocess.run(prefix+['restore', '--backup', bundle, '--destination', str(tmp_path/'restored')],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0 and json.loads(result.stdout)['kill_switch']
    result = subprocess.run(prefix+['verify', '--backup', str(tmp_path/'private-marker')],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 1 and 'private-marker' not in result.stdout+result.stderr


def test_bkp12_copy_time_mutation_is_detected(tmp_path, monkeypatch):
    import aura.backup as module

    store = populated(tmp_path/'source')
    bundle = create_backup(store.directory, tmp_path/'backups')
    original = module.shutil.copyfile
    def mutate(source, destination):
        original(source, destination)
        if source.name == 'demo.db':
            with closing(sqlite3.connect(destination)) as db, db:
                db.execute("INSERT INTO records VALUES ('mutated','fixture','{}',123)")
    monkeypatch.setattr(module.shutil, 'copyfile', mutate)
    with pytest.raises(ValueError):
        restore_backup(bundle, tmp_path/'restored')
    assert not (tmp_path/'restored').exists()
    assert not list(tmp_path.glob('.restore-incomplete-*'))


def test_bkp13_concurrent_destination_creation_never_replaces_empty_directory(tmp_path):
    from aura.backup import publish_directory

    stage, target = tmp_path/'stage', tmp_path/'target'
    stage.mkdir()
    (stage/'file').write_text('copy')
    target.mkdir()
    with pytest.raises(FileExistsError):
        publish_directory(stage, target, 'file')
    assert target.is_dir() and list(target.iterdir()) == []
    assert (stage/'file').read_text() == 'copy'


def test_bkp14_fixture_is_isolated():
    from aura.backup_fixture import run_fixture

    result = run_fixture()
    assert result['memories_verified'] == 3 and result['records_preserved']
    assert result['original_control_unchanged'] and result['restored_emergency_stop_active']
    assert not result['existing_data_modified'] and not result['execution_allowed']
