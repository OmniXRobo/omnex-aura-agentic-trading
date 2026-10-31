"""Clock-driven virtual diagnostic windows; no wall-clock sleeps or broker access."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from pydantic import ValidationError
from test_market_data import CONTRACT, NOW
from test_virtual_ledger import config, intent, quote

from aura.market import GoldContract
from aura.store import Store
from aura.virtual import VirtualLedger
from aura.virtual_evaluation import DAY, EvaluationPlan, VirtualEvaluator


def setup(tmp_path, trades=True, **change):
    store = Store(tmp_path)
    clock = [NOW]
    ledger = VirtualLedger(store, "evaluation-fixture", config(), GoldContract(**CONTRACT),
                           clock=lambda: clock[0])
    if trades:
        store.set_kill(False)
        for index, price in enumerate((3010, 2990, 3010)):
            clock[0] = NOW + index * 10000
            ledger.apply(f"open-{index}", quote(clock[0]), intent(intent_id=f"intent-{index}",
                created_msc=clock[0], expires_msc=clock[0] + 1000))
            clock[0] += 100
            ledger.apply(f"close-{index}", quote(clock[0], price, price + .2))
        store.set_kill(True)
    plan = EvaluationPlan(**(dict(session=ledger.session, anchor_msc=NOW) | change))
    return VirtualEvaluator(store, plan), ledger, clock


def test_ev01_due_boundary_and_grace(tmp_path):
    evaluator, _, _ = setup(tmp_path)
    assert not evaluator.run_due(NOW + 2 * DAY + 59999)["reports"]
    report = evaluator.run_due(NOW + 2 * DAY + 60000)["reports"][0]
    assert report["days"] == 2 and report["closed_trades"] == 3
    assert report["net_closed_pnl"] == "8.3800"
    assert report["wins"] == 2 and report["losses"] == 1
    assert Decimal(report["closed_trade_commission"]) == Decimal("0.42")
    assert report["closed_trade_swap_debits"] == "0.00"
    assert "insufficient_closed_trades" in report["quality_flags"]
    assert not report["promotion_allowed"] and not report["execution_allowed"]
    assert not report["entries_enabled"]


def test_ev02_restart_replay_and_both_rolling_lengths(tmp_path):
    evaluator, ledger, _ = setup(tmp_path)
    assert len(evaluator.run_due(NOW + 3 * DAY + 60000)["reports"]) == 3
    restarted = VirtualEvaluator(ledger.store, evaluator.plan)
    assert not restarted.run_due(NOW + 3 * DAY + 60000)["reports"]
    reports = restarted.reports()
    assert [(r["days"], r["end_msc"]) for r in reports] == [
        (2, NOW + 2 * DAY), (2, NOW + 3 * DAY), (3, NOW + 3 * DAY)]
    assert reports[1]["closed_trades"] == 0  # Trades are outside this rolling interval.


def test_ev03_concurrent_schedulers_do_not_duplicate(tmp_path):
    evaluator, ledger, _ = setup(tmp_path)
    other = VirtualEvaluator(ledger.store, evaluator.plan)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda e: e.run_due(NOW + 2 * DAY + 60000), [evaluator, other]))
    assert sum(len(r["reports"]) for r in results) == 1
    assert len(evaluator.reports()) == 1


def test_ev04_report_failure_rolls_back_due_advance(tmp_path):
    evaluator, ledger, _ = setup(tmp_path)
    with ledger.store.connect("virtual") as db:
        db.execute("CREATE TRIGGER fail_report BEFORE INSERT ON virtual_eval_reports "
                   "BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        evaluator.run_due(NOW + 2 * DAY + 60000)
    assert not evaluator.reports()
    with ledger.store.connect("virtual") as db:
        db.execute("DROP TRIGGER fail_report")
    assert len(evaluator.run_due(NOW + 2 * DAY + 60000)["reports"]) == 1


def test_ev05_empty_window_does_not_claim_profitability(tmp_path):
    evaluator, ledger, _ = setup(tmp_path, False)
    report = evaluator.run_due(NOW + 2 * DAY + 60000)["reports"][0]
    assert report["closed_trades"] == report["quote_events"] == 0
    assert report["win_rate"] is report["expectancy"] is report["profit_factor"] is None
    assert "no_observations" in report["quality_flags"]
    assert ledger.store.killed()


def test_ev06_clock_regression_and_immutable_configuration(tmp_path):
    evaluator, ledger, _ = setup(tmp_path)
    evaluator.run_due(NOW + DAY)
    with pytest.raises(ValueError, match="backwards"):
        evaluator.run_due(NOW)
    with pytest.raises(ValueError, match="immutable"):
        VirtualEvaluator(ledger.store, evaluator.plan.model_copy(update={"min_closed_trades": 1}))


def test_ev07_index_and_catchup_are_bounded(tmp_path):
    evaluator, _, _ = setup(tmp_path)
    first = evaluator.run_due(NOW + 10 * DAY, index_batch=2)
    assert first["state"] == "indexing" and not first["reports"]
    assert evaluator.run_due(NOW + 10 * DAY, index_batch=2)["state"] == "indexing"
    assert len(evaluator.run_due(NOW + 10 * DAY, index_batch=2, max_reports=1)["reports"]) == 1
    assert len(evaluator.reports()) == 1


def test_ev08_reports_append_only_and_memories_separate(tmp_path):
    evaluator, ledger, _ = setup(tmp_path)
    evaluator.run_due(NOW + 2 * DAY + 60000)
    with pytest.raises(sqlite3.IntegrityError):
        with ledger.store.connect("virtual") as db:
            db.execute("DELETE FROM virtual_eval_reports")
    assert ledger.store.records("historical") == ledger.store.records("demo") == []


def test_ev09_late_evidence_is_flagged_without_rewriting_reports(tmp_path):
    evaluator, ledger, clock = setup(tmp_path, False)
    original = evaluator.run_due(NOW + 2 * DAY + 60000)["reports"][0]
    clock[0] = NOW + DAY
    ledger.apply("late-observation", quote(clock[0]))
    result = evaluator.run_due(NOW + 3 * DAY + 60000)
    assert result["late_evidence_count_cumulative"] == 1
    assert evaluator.reports()[0] == original
    assert any("late_evidence_after_prior_report" in r["quality_flags"] for r in result["reports"])


def test_ev10_cost_metrics_do_not_double_count_overlapping_reports(tmp_path):
    evaluator, _, _ = setup(tmp_path)
    reports = evaluator.run_due(NOW + 3 * DAY + 60000)["reports"]
    assert reports[0]["net_closed_pnl"] == reports[2]["net_closed_pnl"]
    assert reports[0]["evidence_digest"] == reports[2]["evidence_digest"]
    # They overlap and are separate diagnostics, never a sum or portfolio backtest.
    assert reports[1]["net_closed_pnl"] == "0"


@pytest.mark.parametrize("change", [dict(windows_days=[]), dict(windows_days=[3, 2]),
    dict(windows_days=[2, 2]), dict(windows_days=[4]), dict(grace_seconds=4),
    dict(min_closed_trades=0), dict(stride_days=0)])
def test_ev11_invalid_plan(change):
    with pytest.raises(ValidationError):
        EvaluationPlan(**(dict(session="test", anchor_msc=NOW) | change))


def test_ev12_cli_saved_report_listing(tmp_path, monkeypatch, capsys):
    import sys

    from aura.evaluate_virtual import main

    evaluator, _, _ = setup(tmp_path)
    evaluator.run_due(NOW + 2 * DAY + 60000)
    plan = tmp_path / "plan.json"
    plan.write_text(evaluator.plan.model_dump_json())
    monkeypatch.setattr(sys, "argv", ["evaluate_virtual", "--data-dir", str(tmp_path),
                                      "--plan", str(plan), "--list"])
    main()
    report = json.loads(capsys.readouterr().out)
    assert len(report["reports"]) == 1 and not report["promotion_allowed"]


def test_ev13_source_gaps_are_conservative_cumulative_evidence(tmp_path):
    from aura.virtual_consumer import SCHEMA

    evaluator, ledger, _ = setup(tmp_path)
    with ledger.store.connect("virtual") as db:
        db.executescript(SCHEMA)
        db.execute("INSERT INTO virtual_source_events VALUES (?,?,?,?)",
                   (ledger.session, 1, "fixture-gap", "skipped_stale_gap"))
    report = evaluator.run_due(NOW + 2 * DAY + 60000)["reports"][0]
    assert report["source_gap_count_cumulative"] == 1
    assert "source_data_gaps_cumulative" in report["quality_flags"]
    assert not report["promotion_allowed"]


def test_ev14_half_open_window_and_crossing_position(tmp_path):
    evaluator, ledger, clock = setup(tmp_path, False)
    ledger.store.set_kill(False)
    # An entry at exactly the window end belongs to the next window, not this one.
    clock[0] = NOW + 2 * DAY
    ledger.apply("boundary", quote(clock[0]), intent(created_msc=clock[0], expires_msc=clock[0] + 1000))
    first = evaluator.run_due(NOW + 2 * DAY + 60000)["reports"][0]
    assert first["quote_events"] == 0
    later = evaluator.run_due(NOW + 3 * DAY + 60000)["reports"]
    assert all("position_crosses_window_boundary" in r["quality_flags"] for r in later)


def test_ev15_fixture_cli_isolated_no_sleep_or_existing_data_change(tmp_path, monkeypatch, capsys):
    from aura.virtual_evaluation_fixture import main

    monkeypatch.chdir(tmp_path)
    main()
    report = json.loads(capsys.readouterr().out)
    assert report["reports_before_due"] == report["restart_new_reports"] == 0
    assert report["reports_created"] == 3 and report["window_lengths"] == [2, 3]
    assert report["all_reports_diagnostic"] and report["emergency_stop_active"]
    assert not report["existing_data_modified"] and not report["promotion_allowed"]
    assert not list(tmp_path.iterdir())


def test_ev16_missing_index_checkpoint_blocks_reports(tmp_path):
    evaluator, ledger, _ = setup(tmp_path)
    evaluator.run_due(NOW + DAY)
    with ledger.store.connect("virtual") as db:
        db.execute("UPDATE virtual_eval_plans SET indexed_id=999999 WHERE session=?", (ledger.session,))
    with pytest.raises(ValueError, match="checkpoint missing"):
        evaluator.run_due(NOW + 2 * DAY + 60000)
    assert not evaluator.reports()
