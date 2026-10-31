"""Verified local SQLite snapshots and quarantined restore. No trading or network calls."""

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
import uuid
from contextlib import ExitStack, closing
from pathlib import Path

from . import __version__
from .operations import directory_lock

MEMORIES = ('historical', 'virtual', 'demo')
FILES = tuple(f'{name}.db' for name in MEMORIES)


def file_digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def inspect_database(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError('Expected a regular memory database')
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=2)) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Memory database integrity failure')
        versions = [row[0] for row in db.execute('SELECT version FROM schema_version ORDER BY version')]
        if 1 not in versions or any(type(v) is not int or v < 1 or v > 9 for v in versions):
            raise ValueError('Unsupported memory schema version')
        if db.execute("SELECT value FROM controls WHERE name='kill_switch'").fetchone() not in [(0,), (1,)]:
            raise ValueError('Missing or invalid safety control')
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {'records', 'audit', 'jobs', 'controls'}
        if not required <= tables:
            raise ValueError('Missing foundation tables')
        # Only known table names enter SQL; no arbitrary manifest SQL is executed.
        selected = required | {'market_events', 'virtual_sessions', 'virtual_events',
                               'virtual_eval_reports', 'strategy_versions', 'strategy_events'}
        counts = {name: db.execute(f'SELECT count(*) FROM {name}').fetchone()[0]
                  for name in sorted(selected & tables)}
    return dict(size=path.stat().st_size, sha256=file_digest(path), schemas=versions, counts=counts)


def write_json(path, payload):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    if os.name != 'nt':
        path.chmod(0o600)


def _validate_manifest(directory):
    manifest_path = directory / 'manifest.json'
    if manifest_path.is_symlink() or manifest_path.stat().st_size > 65536:
        raise ValueError('Invalid backup manifest')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('format') != 1 or set(manifest.get('files', {})) != set(FILES):
        raise ValueError('Unsupported backup format or memory set')
    if not re.fullmatch(r'[0-9a-f]{32}', manifest.get('backup_id', '')):
        raise ValueError('Invalid backup identifier')
    if (manifest.get('encrypted') is not False or manifest.get('execution_allowed') is not False
            or not re.fullmatch(r'\d+\.\d+\.\d+', manifest.get('application_version', ''))):
        raise ValueError('Invalid backup provenance')
    for name in FILES:
        actual = inspect_database(directory / name)
        if actual != manifest['files'][name]:
            raise ValueError('Backup content or metadata mismatch')
    return manifest


def verify_backup(directory):
    directory = Path(directory).resolve()
    # A published snapshot is standalone: sidecar WAL/journal files may not override it.
    if set(p.name for p in directory.iterdir()) != set(FILES) | {'manifest.json'}:
        raise ValueError('Unexpected files in backup bundle')
    return _validate_manifest(directory)


def publish_directory(stage, target, completion_file):
    """Reserve a new directory exclusively; publish its completion marker last."""
    target.mkdir(mode=0o700)  # No empty/nonempty existing directory is ever replaced.
    published = []
    try:
        paths = sorted(stage.iterdir(), key=lambda p: p.name == completion_file)
        for path in paths:
            destination = target / path.name
            # Exclusive creation is portable, including filesystems without hardlinks.
            with path.open('rb') as source, destination.open('xb') as output:
                published.append(destination)
                shutil.copyfileobj(source, output, length=1024*1024)
                output.flush()
                os.fsync(output.fileno())
            if os.name != 'nt':
                destination.chmod(0o600)
    except BaseException:
        for path in reversed(published):
            path.unlink(missing_ok=True)
        try:
            target.rmdir()
        except OSError:
            pass
        raise
    shutil.rmtree(stage, ignore_errors=True)


def create_backup(source, destination_root):
    source, destination_root = Path(source).resolve(), Path(destination_root).resolve()
    if not source.is_dir() or destination_root == source or source in destination_root.parents:
        raise ValueError('Backup destination must be outside the source directory')
    for name in FILES:
        if not (source / name).is_file() or (source / name).is_symlink():
            raise ValueError('All three existing memory databases are required')
    identifier = uuid.uuid4().hex
    destination_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    stage, target = destination_root / ('.incomplete-'+identifier), destination_root / ('aura-'+identifier)
    stage.mkdir(mode=0o700)
    try:
        with directory_lock(source), ExitStack() as stack:
            # Lock every memory against writers before taking any snapshot. Backup reads
            # use separate connections so SQLite's backup API never copies a write txn.
            for name in FILES:
                lock = sqlite3.connect(source / name, timeout=2)
                stack.callback(lock.close)
                lock.execute('BEGIN IMMEDIATE')
            metadata = {}
            for name in FILES:
                source_db = sqlite3.connect((source / name).as_uri()+'?mode=ro', uri=True)
                target_db = sqlite3.connect(stage / name)
                try:
                    source_db.backup(target_db)
                    target_db.execute('PRAGMA journal_mode=DELETE')
                finally:
                    source_db.close()
                    target_db.close()
                if os.name != 'nt':
                    (stage / name).chmod(0o600)
                metadata[name] = inspect_database(stage / name)
            write_json(stage / 'manifest.json', dict(format=1, backup_id=identifier,
                application_version=__version__, created_msc=int(time.time()*1000), files=metadata,
                consistency='all_three_memories_write_locked', encrypted=False, execution_allowed=False))
            verify_backup(stage)
        publish_directory(stage, target, 'manifest.json')
        return target
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def restore_backup(bundle, destination):
    bundle, destination = Path(bundle).resolve(), Path(destination).resolve()
    if destination.exists() or bundle == destination or bundle in destination.parents:
        raise ValueError('Restore requires a new, nonexistent destination outside the bundle')
    manifest = verify_backup(bundle)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.parent / ('.restore-incomplete-'+uuid.uuid4().hex)
    stage.mkdir(mode=0o700)
    try:
        for name in FILES:
            shutil.copyfile(bundle / name, stage / name)
            if os.name != 'nt':
                (stage / name).chmod(0o600)
        write_json(stage / 'manifest.json', manifest)
        verify_backup(stage)  # Recheck copied bytes before modifying safety state.
        (stage / 'manifest.json').unlink()
        for name in FILES:
            with closing(sqlite3.connect(stage / name)) as db, db:
                db.execute("UPDATE controls SET value=1 WHERE name='kill_switch'")
                if db.execute("SELECT 1 FROM sqlite_master WHERE name='operations_runtime'").fetchone():
                    db.execute('DELETE FROM operations_runtime')
                db.execute('INSERT INTO audit(actor,action,payload,created) VALUES (?,?,?,?)',
                    ('backup-restore', 'restore_quarantine', json.dumps(dict(backup_id=manifest['backup_id'])), time.time()))
            # Ensure no WAL contents are left outside the restored memory file.
            with closing(sqlite3.connect(stage / name)) as db, db:
                db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                db.execute('PRAGMA journal_mode=DELETE')
        for name in FILES:
            with closing(sqlite3.connect(stage / name)) as db:
                if db.execute("SELECT value FROM controls WHERE name='kill_switch'").fetchone() != (1,):
                    raise ValueError('Restored safety state is not stopped')
        write_json(stage / 'restore.json', dict(format=1, backup_id=manifest['backup_id'],
            restored_msc=int(time.time()*1000), source_application_version=manifest['application_version'],
            application_version=__version__, kill_switch=True, workers_started=False,
            execution_allowed=False, files={name: inspect_database(stage / name) for name in FILES}))
        publish_directory(stage, destination, 'restore.json')
        return destination
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main():
    parser = argparse.ArgumentParser(description='Local backup verification and quarantined restore')
    commands = parser.add_subparsers(dest='command', required=True)
    backup = commands.add_parser('create')
    backup.add_argument('--data-dir', type=Path, required=True)
    backup.add_argument('--destination', type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('--backup', type=Path, required=True)
    restore = commands.add_parser('restore')
    restore.add_argument('--backup', type=Path, required=True)
    restore.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'create':
            result = dict(backup=str(create_backup(args.data_dir, args.destination)), encrypted=False)
        elif args.command == 'verify':
            manifest = verify_backup(args.backup)
            result = dict(verified=True, backup_id=manifest['backup_id'])
        else:
            result = dict(restored=str(restore_backup(args.backup, args.destination)), kill_switch=True,
                          workers_started=False)
        print(json.dumps(result | dict(execution_allowed=False)))
    except Exception:
        print('Backup/restore verification, lock, schema or destination failure. No target was overwritten.')
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
