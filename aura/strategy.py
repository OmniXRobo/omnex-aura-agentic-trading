"""Local research registry CLI. Does not evaluate or execute strategy descriptions."""

import argparse
import json
import os
from pathlib import Path

from .registry import RegistryAction, StrategyRegistry, StrategyVersion
from .store import Store


def main():
    parser = argparse.ArgumentParser(description='Immutable research strategy registry')
    parser.add_argument('--data-dir', type=Path, default=Path(os.getenv('AURA_DATA_DIR', 'data')))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--spec', type=Path, help='Register a new immutable specification JSON')
    group.add_argument('--action', type=Path, help='Append a review action JSON; requires --version')
    group.add_argument('--show', help='Show a saved version and its review history')
    group.add_argument('--list', action='store_true')
    parser.add_argument('--version', help='Version targeted by --action')
    args = parser.parse_args()
    if bool(args.action) != bool(args.version):
        parser.error('--version is required only with --action')
    try:
        # Validate file inputs before creating a data directory or opening storage.
        spec = StrategyVersion.model_validate_json(args.spec.read_text()) if args.spec else None
        action = RegistryAction.model_validate_json(args.action.read_text()) if args.action else None
        registry = StrategyRegistry(Store(args.data_dir.resolve()))
        if spec:
            result = registry.create(spec)
        elif action:
            result = registry.apply(args.version, action)
        elif args.show:
            result = registry.get(args.show)
        else:
            result = registry.list()
        print(json.dumps(result, allow_nan=False))
    except Exception:
        print('Registry configuration, evidence or revision conflict. No execution or promotion authorized.')
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
