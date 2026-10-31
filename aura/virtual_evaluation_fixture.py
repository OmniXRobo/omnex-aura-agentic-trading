"""Isolated logical-clock evaluation exercise; never waits days or touches VPS data."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .market import GoldContract, Quote
from .store import Store
from .virtual import VirtualConfig, VirtualIntent, VirtualLedger
from .virtual_evaluation import DAY, EvaluationPlan, VirtualEvaluator


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
    with TemporaryDirectory(prefix="aura-evaluation-fixture-") as directory:
        store = Store(Path(directory))
        # Only this new temporary fixture store permits its one synthetic entry.
        store.set_kill(False, actor="isolated-evaluation-fixture")
        ledger = VirtualLedger(store, "synthetic-evaluation", cfg, contract, clock=lambda: now)
        ledger.apply("entry", Quote(symbol="XAUUSD", time_msc=now, bid=3000, ask=3000.2, flags=6),
                     VirtualIntent(intent_id="synthetic-1", strategy_version="fixture-v1",
                                   reason="Synthetic accounting only", side="buy", volume="0.01",
                                   stop_loss=2995, take_profit=3010, created_msc=now,
                                   expires_msc=now + 1000, news_blackout=False))
        ledger.clock = lambda: now + 100
        ledger.apply("exit", Quote(symbol="XAUUSD", time_msc=now + 100,
                                   bid=3010, ask=3010.2, flags=6))
        store.set_kill(True, actor="isolated-evaluation-fixture")
        plan = EvaluationPlan(session=ledger.session, anchor_msc=now)
        evaluator = VirtualEvaluator(store, plan)
        early = evaluator.run_due(now + DAY)
        first = evaluator.run_due(now + 2 * DAY + 60000)
        restarted = VirtualEvaluator(Store(Path(directory)), plan)
        replay = restarted.run_due(now + 2 * DAY + 60000)
        later = restarted.run_due(now + 3 * DAY + 60000)
        reports = first["reports"] + later["reports"]
        return dict(evidence_source="synthetic_fixture", reports_before_due=len(early["reports"]),
                    reports_created=len(reports), window_lengths=sorted({r["days"] for r in reports}),
                    restart_new_reports=len(replay["reports"]),
                    all_reports_diagnostic=all("insufficient_closed_trades" in r["quality_flags"] for r in reports),
                    emergency_stop_active=store.killed(), existing_data_modified=False,
                    promotion_allowed=False, entries_enabled=False, execution_allowed=False)


def main():
    print(json.dumps(run_fixture(), indent=2))


if __name__ == "__main__":
    main()
