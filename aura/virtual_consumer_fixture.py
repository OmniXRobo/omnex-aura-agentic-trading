"""Temporary collector-to-virtual observation exercise; never arms entries."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .collector import AccountBinding
from .market import Feed, GoldContract, Quote
from .market_store import MarketStore
from .store import Store
from .virtual import VirtualConfig, VirtualLedger
from .virtual_consumer import VirtualQuoteConsumer


def run_fixture():
    now = 1700000400000
    contract = GoldContract(
        symbol="XAUUSD", currency_base="XAU", currency_profit="USD", digits=2, point=.01,
        trade_tick_size=.01, trade_tick_value=1, trade_contract_size=100,
        volume_min=.01, volume_max=100, volume_step=.01, trade_stops_level=10,
        trade_freeze_level=0, trade_mode=4, filling_mode=1, swap_mode=1,
        swap_long=-2, swap_short=1,
    )
    cfg = VirtualConfig(evidence_source="fixture", commission_per_lot_side=7,
                        slippage_price="0.1", swap_debit_per_lot_utc_day=1)
    feed = Feed(broker="Fixture", source="fixture", stream="synthetic")
    binding = AccountBinding(12345, "Fixture-Demo")
    with TemporaryDirectory(prefix="aura-consumer-fixture-") as directory:
        store = Store(Path(directory))
        market = MarketStore(store)
        market.bind(feed, binding.login, binding.server)
        market.bind_quote_time(feed, 0)
        market.append(feed, contract, now)
        for offset in range(3):
            market.append(feed, Quote(symbol="XAUUSD", time_msc=now + offset * 100,
                                      bid=3000 + offset * .1, ask=3000.2 + offset * .1,
                                      flags=6), now + offset * 100)
        market.set_status(feed, "healthy", "Synthetic fixture", now + 200)
        ledger = VirtualLedger(store, "observer", cfg, contract, clock=lambda: now + 200)
        consumer = VirtualQuoteConsumer(market, ledger, feed, binding)
        states = [consumer.step()["state"] for _ in range(3)]
        restarted = VirtualLedger(Store(Path(directory)), "observer", cfg, contract,
                                  clock=lambda: now + 200)
        cursor = VirtualQuoteConsumer(market, restarted, feed, binding).step()
        return dict(evidence_source="synthetic_fixture", states=states,
                    restart_state=cursor["state"], ledger_events=len(restarted.events()),
                    position_open=restarted.snapshot()["position"] is not None,
                    emergency_stop_unchanged=store.killed(), entries_enabled=False,
                    execution_allowed=False, existing_data_modified=False)


def main():
    print(json.dumps(run_fixture(), indent=2))


if __name__ == "__main__":
    main()
