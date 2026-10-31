"""Local scheduled virtual diagnostics; does not operate a trading consumer."""

import argparse
import json
import os
import time
from pathlib import Path

from .store import Store
from .virtual_evaluation import EvaluationPlan, VirtualEvaluator


def main():
    parser = argparse.ArgumentParser(description="Persistent rolling virtual evaluation")
    parser.add_argument("--data-dir", type=Path, default=Path(os.getenv("AURA_DATA_DIR", "data")))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=30)
    parser.add_argument("--list", action="store_true", help="Print saved immutable reports")
    args = parser.parse_args()
    if not 1 <= args.interval <= 60:
        parser.error("Interval must be one to 60 seconds")
    try:
        evaluator = VirtualEvaluator(Store(args.data_dir), EvaluationPlan.model_validate_json(args.plan.read_text()))
        if args.list:
            print(json.dumps(dict(reports=evaluator.reports(), execution_allowed=False, promotion_allowed=False)))
            return
        while True:
            print(json.dumps(evaluator.run_due()), flush=True)
            if not args.watch:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return
    except Exception:
        print(json.dumps(dict(error="virtual_evaluation_configuration_or_evidence_failure",
                              execution_allowed=False, promotion_allowed=False)))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
