"""Independent local emergency stop; does not require a running API or AI."""

import argparse
from pathlib import Path

from .store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    Store(args.data_dir).set_kill(True)
    print("Emergency stop persisted. Broker execution is disabled in this release.")


if __name__ == "__main__":
    main()
