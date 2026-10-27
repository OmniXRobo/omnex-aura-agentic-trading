"""Local offline research CLI. Does not require broker/API credentials."""

import argparse
import json
import os
from pathlib import Path

from .backtest import BacktestRequest, persist_backtest
from .store import Store


def main():
    parser = argparse.ArgumentParser(description="Run and persist a research-only bar backtest")
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path(os.getenv("AURA_DATA_DIR", "data")))
    args = parser.parse_args()
    request = BacktestRequest.model_validate_json(args.request.read_text())
    result = persist_backtest(Store(args.data_dir), request)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "record_id",
                    "request_hash",
                    "engine_version",
                    "dataset_label",
                    "data_source",
                    "strategy",
                    "metrics",
                    "assumptions",
                    "promotion_eligible",
                    "execution_allowed",
                )
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
