"""Offline chronological-validation command; never connects to a broker/provider."""

import argparse
import json
import os
from pathlib import Path

from .backtest import ResearchConflict
from .store import Store
from .validation import HoldoutConflict, ValidationRequest, persist_validation


def main():
    parser = argparse.ArgumentParser(description="Run reserved-holdout research validation")
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path(os.getenv("AURA_DATA_DIR", "data")))
    args = parser.parse_args()
    request = ValidationRequest.model_validate_json(args.request.read_text())
    try:
        result = persist_validation(Store(args.data_dir), request)
    except (HoldoutConflict, ResearchConflict) as error:
        parser.error(str(error))
    summary = {
        key: result[key]
        for key in (
            "record_id",
            "replayed",
            "request_hash",
            "validation_version",
            "dataset_label",
            "data_source",
            "development_test_summary",
            "development_bootstrap",
            "evidence_status",
            "promotion_eligible",
            "execution_allowed",
        )
    }
    summary["fold_count"] = len(result["folds"])
    summary["final_holdout"] = result["final_holdout"]["evaluation"]
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
