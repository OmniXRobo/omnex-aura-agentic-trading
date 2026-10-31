"""Run a bounded batch of deterministic saved virtual report diagnostics."""

import argparse
import json
import os
from pathlib import Path

from .diagnostics import VirtualDiagnostics, read_diagnostics
from .store import Store


def main():
    parser = argparse.ArgumentParser(description='Saved virtual evidence triage; no strategy changes')
    parser.add_argument('--data-dir', type=Path, default=Path(os.getenv('AURA_DATA_DIR', 'data')))
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    try:
        store = Store(args.data_dir.resolve())
        result = read_diagnostics(store) if args.list else VirtualDiagnostics(store).run_batch()
        print(json.dumps(result, allow_nan=False))
    except Exception:
        print('Virtual diagnostic evidence, safety or storage failure; no changes authorized.')
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
