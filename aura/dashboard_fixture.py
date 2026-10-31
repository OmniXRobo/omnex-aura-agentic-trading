"""Synthetic dashboard seed, restricted to a new empty temporary directory."""

import asyncio
import math
import time
from pathlib import Path

from .agents import Orchestrator, Snapshot
from .market import Candle, Feed, GoldContract, Quote
from .market_store import MarketStore
from .store import Store
from .virtual import VirtualConfig, VirtualIntent, VirtualLedger
from .virtual_evaluation import DAY, EvaluationPlan, VirtualEvaluator


def seed_dashboard(directory):
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("Dashboard fixture requires an empty directory")
    store = Store(directory)
    store.record("historical", "dashboard_fixture", {"synthetic": True})
    now = int(time.time() * 1000)
    feed = Feed(broker="Synthetic", source="fixture", stream="gold-observations")
    contract = GoldContract(
        symbol="XAUUSD", currency_base="XAU", currency_profit="USD", digits=2, point=.01,
        trade_tick_size=.01, trade_tick_value=1, trade_contract_size=100,
        volume_min=.01, volume_max=100, volume_step=.01, trade_stops_level=10,
        trade_freeze_level=0, trade_mode=4, filling_mode=1, swap_mode=1,
        swap_long=-2, swap_short=1,
    )
    market = MarketStore(store)
    market.append(feed, contract, now)
    for index in range(100):
        bid = round(3000 + index * .035 + math.sin(index / 8) * 1.8 + math.cos(index / 3) * .18, 2)
        market.append(feed, Quote(symbol="XAUUSD", time_msc=now - (100 - index) * 10000,
                                  bid=bid, ask=round(bid + .25, 2), flags=6), now)
    last_minute = now // 60000 * 60
    for index in range(50):
        opening = last_minute - (50 - index) * 60
        price = round(3000 + index * .06 + math.sin(index / 6) * 1.5, 2)
        market.append(feed, Candle(symbol="XAUUSD", timeframe="M1", open_time=opening,
                                   open=price, close=price + .15, high=price + .4,
                                   low=price - .3, tick_volume=20, spread_points=25, real_volume=0), now)
    market.set_status(feed, "healthy", "Synthetic fixture heartbeat only", now)
    cfg = VirtualConfig(evidence_source="fixture", commission_per_lot_side=7,
                        slippage_price="0.1", swap_debit_per_lot_utc_day=1)
    store.set_kill(False, actor="temporary-dashboard-fixture")
    clock = [now - 180000]
    ledger = VirtualLedger(store, "synthetic-gold-v1", cfg, contract, clock=lambda: clock[0])
    def signal(identifier):
        return VirtualIntent(intent_id=identifier, strategy_version="fixture-only-v1",
                             reason="Synthetic dashboard evidence", side="buy", volume="0.01",
                             stop_loss=2995, take_profit=3010, created_msc=clock[0],
                             expires_msc=clock[0] + 1000, news_blackout=False)
    ledger.apply("entry-1", Quote(symbol="XAUUSD", time_msc=clock[0], bid=3000, ask=3000.2, flags=6), signal("fixture-1"))
    clock[0] = now - 120000
    ledger.apply("exit-1", Quote(symbol="XAUUSD", time_msc=clock[0], bid=3010, ask=3010.2, flags=6))
    clock[0] = now - 30000
    ledger.apply("entry-2", Quote(symbol="XAUUSD", time_msc=clock[0], bid=3000, ask=3000.2, flags=6), signal("fixture-2"))
    store.set_kill(True, actor="temporary-dashboard-fixture")
    evaluator = VirtualEvaluator(store, EvaluationPlan(session=ledger.session, anchor_msc=now - 3 * DAY - 60000))
    evaluator.run_due(now)
    asyncio.run(Orchestrator(store).run(Snapshot(prices=[3000, 3001, 3001.5], tick_age_seconds=1, source="fixture")))
    return store
