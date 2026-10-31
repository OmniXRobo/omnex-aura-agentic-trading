"""Observation-only quote consumer CLI; never imports MT5 or enables entries."""

import argparse
import json
import os
import time
from pathlib import Path

from pydantic import Field

from .collector import AccountBinding
from .market import Feed, GoldContract, MarketModel
from .market_store import MarketStore
from .store import Store
from .virtual import VirtualConfig, VirtualLedger
from .virtual_consumer import ConsumerError, VirtualQuoteConsumer


class ConsumerConfig(MarketModel):
    session: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    feed: Feed
    symbol: str = Field(min_length=1, max_length=64)
    costs: VirtualConfig


def main():
    parser = argparse.ArgumentParser(description="Observation-only virtual quote consumer")
    parser.add_argument("--data-dir", type=Path, default=Path(os.getenv("AURA_DATA_DIR", "data")))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=1)
    parser.add_argument("--batch", type=int, default=100)
    args = parser.parse_args()
    if not .2 <= args.interval <= 60 or not 1 <= args.batch <= 100:
        parser.error("Interval .2–60 seconds and batch 1–100 required")
    try:
        cfg = ConsumerConfig.model_validate_json(args.config.read_text())
        if cfg.feed.source != "mt5_demo" or cfg.costs.evidence_source != "demo_observation":
            raise ConsumerError("demo_observation_config_required")
        login, server = os.getenv("AURA_MT5_EXPECTED_LOGIN", ""), os.getenv("AURA_MT5_EXPECTED_SERVER", "")
        if not login.isdigit() or not server:
            raise ConsumerError("explicit_expected_demo_identity_required")
        store = Store(args.data_dir)
        market = MarketStore(store)
        contracts = market.events(cfg.feed.key, cfg.symbol, "contract", limit=1)
        if not contracts:
            raise ConsumerError("collect_fresh_contract_and_quote_first")
        ledger = VirtualLedger(store, cfg.session, cfg.costs, GoldContract.model_validate(contracts[0]["data"]))
        consumer = VirtualQuoteConsumer(market, ledger, cfg.feed, AccountBinding(int(login), server))
        while True:
            counts = {}
            try:
                for _ in range(args.batch):
                    result = consumer.step()
                    state = result["state"]
                    counts[state] = counts.get(state, 0) + 1
                    if state == "idle":
                        break
                print(json.dumps(dict(states=counts, entries_enabled=False,
                                      execution_allowed=False)), flush=True)
            except ConsumerError as error:
                print(json.dumps(dict(error=error.code, entries_enabled=False,
                                      execution_allowed=False)), flush=True)
                if not args.watch:
                    raise SystemExit(1) from None
            if not args.watch:
                break
            time.sleep(args.interval)
    except ConsumerError as error:
        print(json.dumps(dict(error=error.code, entries_enabled=False, execution_allowed=False)))
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        return
    except Exception:
        # Config/native storage errors may contain private paths or account information.
        print(json.dumps(dict(error="consumer_configuration_or_storage_failure",
                              entries_enabled=False, execution_allowed=False)))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
