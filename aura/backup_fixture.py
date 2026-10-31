"""Temporary three-memory backup/restore smoke check; never uses operational data."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .backup import create_backup, restore_backup, verify_backup
from .store import Store


def run_fixture():
    with TemporaryDirectory(prefix='aura-backup-fixture-') as temporary:
        root = Path(temporary)
        store = Store(root/'source')
        for memory in ('historical', 'virtual', 'demo'):
            store.record(memory, 'backup_fixture', dict(source='synthetic_fixture', memory=memory))
        # Prove the restore forces ON even when the original research control was OFF.
        store.set_kill(False)
        bundle = create_backup(store.directory, root/'backups')
        verified = verify_backup(bundle)
        restored = Store(restore_backup(bundle, root/'restored'))
        return dict(evidence_source='synthetic_fixture', memories_verified=len(verified['files']),
                    records_preserved=all(store.records(m) == restored.records(m) for m in
                                          ('historical', 'virtual', 'demo')),
                    restored_emergency_stop_active=restored.killed(),
                    original_control_unchanged=not store.killed(), backup_verified=True,
                    execution_allowed=False, existing_data_modified=False,
                    fixture_storage='temporary_removed_on_exit')


def main():
    print(json.dumps(run_fixture()))


if __name__ == '__main__':
    main()
