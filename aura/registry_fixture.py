"""Isolated synthetic registry smoke check; temporary data is removed on exit."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .registry import RegistryAction, StrategyRegistry, StrategyVersion
from .store import Store


def run_fixture():
    with TemporaryDirectory(prefix='aura-registry-fixture-') as directory:
        store = Store(Path(directory))
        registry = StrategyRegistry(store)
        spec = StrategyVersion(version_id='fixture-v1', strategy_id='fixture-only', family='breakout',
                               hypothesis='Synthetic fixture hypothesis; not a market signal',
                               entry_method='Description only; no executable strategy implementation',
                               exit_method='Description only; protective stops required in future tests',
                               cost_assumptions='Costs must be independently measured before research',
                               risk_percent=.25)
        first = registry.create(spec)
        replay = registry.create(spec)
        registry.apply('fixture-v1', RegistryAction(operation_id='fixture-suspend', expected_revision=1,
                       action='suspend', reason='Synthetic suspension for persistence verification'))
        registry.create(StrategyVersion.model_validate(spec.model_dump() | dict(version_id='fixture-v2',
                                                                                parent_version='fixture-v1')))
        restored = StrategyRegistry(Store(Path(directory)))
        return dict(evidence_source='synthetic_fixture', versions=len(restored.list()),
                    replay_identical=first == replay, parent_state=restored.get('fixture-v1')['state'],
                    child_state=restored.get('fixture-v2')['state'], emergency_stop_active=store.killed(),
                    promotion_allowed=False, execution_allowed=False, existing_data_modified=False,
                    fixture_storage='temporary_removed_on_exit')


def main():
    print(json.dumps(run_fixture()))


if __name__ == '__main__':
    main()
