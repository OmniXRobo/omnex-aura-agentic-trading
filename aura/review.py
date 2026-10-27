"""Run a local research-review committee with no keys, network or execution capability."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from .review_types import ReviewContext
from .reviews import ReviewCoordinator, default_gateway
from .store import Store


def main():
    parser = argparse.ArgumentParser(
        description="Local deterministic review workflow; not LLM inference"
    )
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path(os.getenv("AURA_DATA_DIR", "data")))
    args = parser.parse_args()
    context = ReviewContext.model_validate_json(args.request.read_text())
    store = Store(args.data_dir)
    result = asyncio.run(ReviewCoordinator(store, default_gateway(store)).run(context))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
