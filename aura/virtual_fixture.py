"""Isolated synthetic virtual-ledger smoke. Never reads or changes VPS trading data."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .market import GoldContract, Quote
from .store import Store
from .virtual import VirtualConfig, VirtualIntent, VirtualLedger


def run_fixture():
    contract = GoldContract(
        symbol="XAUUSD", currency_base="XAU", currency_profit="USD", digits=2, point=.01,
        trade_tick_size=.01, trade_tick_value=1, trade_contract_size=100,
        volume_min=.01, volume_max=100, volume_step=.01, trade_stops_level=10,
        trade_freeze_level=0, trade_mode=4, filling_mode=1, swap_mode=1,
        swap_long=-2, swap_short=1,
    )
    config = VirtualConfig(evidence_source="fixture", commission_per_lot_side=7,
                           slippage_price="0.1", swap_debit_per_lot_utc_day=1)
    now = 1700000400000
    first = Quote(symbol="XAUUSD", time_msc=now, bid=3000, ask=3000.2, flags=6)
    signal = VirtualIntent(intent_id="synthetic-1", strategy_version="fixture-only-v1",
                           reason="Deterministic ledger smoke; not a market signal",
                           side="buy", volume="0.01", stop_loss=2995, take_profit=3010,
                           news_blackout=False, created_msc=now, expires_msc=now + 60000)
    with TemporaryDirectory(prefix="aura-virtual-fixture-") as directory:
        store = Store(Path(directory))
        # Only this new temporary fixture store is armed. Existing VPS controls are untouched.
        store.set_kill(False, actor="isolated-fixture")
        ledger = VirtualLedger(store, "synthetic", config, contract, clock=lambda: now)
        opened = ledger.apply("open", first, signal)
        restarted = VirtualLedger(Store(Path(directory)), "synthetic", config, contract,
                                  clock=lambda: now + 1000)
        replay = restarted.apply("open", first, signal)
        closed = restarted.apply("target", Quote(symbol="XAUUSD", time_msc=now + 1000,
                                                 bid=3010, ask=3010.2, flags=6))
        return dict(evidence_source="synthetic_fixture", entry=opened["action"],
                    restart_replay_identical=replay == opened, exit=closed["action"],
                    final_cash=closed["state"]["cash"],
                    net_pnl=closed["details"]["net_pnl"],
                    ledger_events=len(restarted.events()), execution_allowed=False,
                    existing_data_modified=False, fixture_storage="temporary_removed_on_exit")


def main():
    print(json.dumps(run_fixture(), indent=2))


if __name__ == "__main__":
    main()
