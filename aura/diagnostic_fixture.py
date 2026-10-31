"""Temporary real-evaluator-to-diagnostic integration exercise with synthetic quotes."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .dashboard_fixture import seed_dashboard
from .diagnostics import VirtualDiagnostics, read_diagnostics


def run_fixture():
    with TemporaryDirectory(prefix='aura-diagnostic-fixture-') as directory:
        store = seed_dashboard(Path(directory))
        first = VirtualDiagnostics(store).run_batch()
        replay = VirtualDiagnostics(store).run_batch()
        reports = read_diagnostics(store)
        return dict(evidence_source='synthetic_fixture', diagnostics_created=first['created'],
                    replay_new_diagnostics=replay['created'],
                    all_synthetic=all(r['source'] == 'fixture' for r in reports),
                    all_review_only=all(r['conclusion'] == 'research_review_only' for r in reports),
                    emergency_stop_active=store.killed(), strategy_changes_applied=False,
                    promotion_allowed=False, entries_enabled=False, execution_allowed=False,
                    existing_data_modified=False, fixture_storage='temporary_removed_on_exit')


def main():
    print(json.dumps(run_fixture()))


if __name__ == '__main__':
    main()
