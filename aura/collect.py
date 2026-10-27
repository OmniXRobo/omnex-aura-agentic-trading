"""Windows command line collector; uses an already signed-in demo MT5 session."""

import argparse
import importlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from .collector import AccountBinding, Collector, MarketDataError
from .market import Feed
from .market_store import MarketStore
from .store import Store


def main():
    parser = argparse.ArgumentParser(description="Read-only MT5 demo market collector")
    parser.add_argument("--data-dir", type=Path, default=Path(os.getenv("AURA_DATA_DIR", "data")))
    parser.add_argument("--broker", required=True, choices=["Exness", "Equiti", "MultiBank"])
    parser.add_argument("--stream", default="demo-1")
    parser.add_argument("--symbol")
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=1)
    parser.add_argument("--history-from")
    parser.add_argument("--history-to")
    parser.add_argument("--timeframe", default="M1")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("The official MT5 terminal connector must run on Windows")
    if not 0.2 <= args.interval <= 60:
        parser.error("Polling interval must be between 0.2 and 60 seconds")
    if bool(args.history_from) != bool(args.history_to):
        parser.error("Both history boundaries are required")
    path = os.getenv("AURA_MT5_TERMINAL_PATH", "")
    server = os.getenv("AURA_MT5_EXPECTED_SERVER", "")
    login = os.getenv("AURA_MT5_EXPECTED_LOGIN", "")
    if not path or not server or not login.isdigit():
        parser.error("Configure terminal path and explicit expected demo account/server")
    mt5 = importlib.import_module("MetaTrader5")
    if not mt5.initialize(path=path):
        raise SystemExit("MT5 initialization failed")
    try:
        collector = Collector(
            mt5,
            MarketStore(Store(args.data_dir)),
            Feed(broker=args.broker, source="mt5_demo", stream=args.stream),
            AccountBinding(int(login), server),
        )
        if args.discover:
            print(json.dumps({"candidates": collector.discover(), "execution_allowed": False}))
            return
        if not args.symbol:
            parser.error("Select an explicit symbol after discovery")
        if args.history_from:
            result = collector.history(
                args.symbol,
                args.timeframe,
                datetime.fromisoformat(args.history_from),
                datetime.fromisoformat(args.history_to),
            )
            print(json.dumps(result))
            return
        while True:
            try:
                print(json.dumps(collector.poll(args.symbol)), flush=True)
            except MarketDataError as error:
                print(str(error), file=sys.stderr, flush=True)
                if not args.watch:
                    raise SystemExit(1) from None
            if not args.watch:
                break
            # Re-check terminal health and account binding on every loop. The supervisor
            # must restart the process if the native terminal session needs reinitialization.
            time.sleep(args.interval)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
