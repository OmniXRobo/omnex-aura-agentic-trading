"""M3 causal-feature and conservative-fill acceptance tests; all data is synthetic."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aura.api import create_app
from aura.backtest import (
    BacktestRequest,
    Dataset,
    ResearchBar,
    ResearchConfig,
    exit_for_bar,
    metrics,
    persist_backtest,
    run_backtest,
    signals,
    volume_for_risk,
)
from aura.config import Settings
from aura.features import ema, features, sma
from aura.store import Store

BASE = 1700000400
CONFIG = dict(
    strategy="ema_cross_v1",
    fast_period=2,
    slow_period=3,
    volatility_period=2,
    stop_atr=1,
    reward_risk=2,
    contract_size=100,
    volume_min=0.01,
    volume_max=100,
    volume_step=0.01,
    commission_roundtrip_per_lot=0,
    slippage=0,
    swap_cost_per_lot_day=0,
    max_spread=2,
)


def make_bar(i, close=100, **kw):
    return ResearchBar(
        **(
            dict(
                open_time=BASE + i * 60,
                open=100,
                high=max(101, close),
                low=min(99, close),
                close=close,
                spread=1,
            )
            | kw
        )
    )


def dataset(bars=None, **kw):
    return Dataset(
        **(
            dict(
                label="synthetic-test",
                source="fixture",
                interval_seconds=60,
                as_of=BASE + 20000,
                bars=bars or [make_bar(i) for i in range(3)],
            )
            | kw
        )
    )


def request(bars=None, **kw):
    return BacktestRequest(dataset=dataset(bars), config=ResearchConfig(**(CONFIG | kw)))


def force_signal(monkeypatch, side="buy"):
    monkeypatch.setattr(
        "aura.backtest.signals",
        lambda data, config, computed: [None, side] + [None] * (len(data.bars) - 2),
    )


def test_m3_01_sma_ema_known_values_and_warmup():
    assert sma([1, 2, 3, 4], 3) == [None, None, 2, 3]
    assert ema([1, 2, 3, 4], 3) == [None, None, 2, 3]
    assert ema([1, 2], 3) == [None, None]
    for function in (sma, ema):
        with pytest.raises(ValueError):
            function([1, 2], 0)


def test_m3_02_causal_prefix_invariance():
    bars = [make_bar(i, 100 + i * 0.1) for i in range(30)]
    full = features(bars, 2, 3, 2)
    for length in (3, 7, 15, 29):
        assert full[:length] == features(bars[:length], 2, 3, 2)
    cfg = ResearchConfig(**CONFIG)
    assert signals(dataset(bars), cfg, full)[:15] == signals(dataset(bars[:15]), cfg, full[:15])


def test_m3_03_flat_rsi_atr_bollinger():
    result = features([make_bar(i) for i in range(4)], 2, 3, 2)
    assert result[-1]["rsi_sma"] == 50
    assert result[-1]["atr_sma"] == 2
    assert result[-1]["bollinger_lower"] == result[-1]["bollinger_upper"] == 100


def test_m3_04_ordered_closed_datasets():
    with pytest.raises(ValidationError):
        dataset([make_bar(0), make_bar(0), make_bar(1)])
    with pytest.raises(ValidationError):
        dataset(as_of=BASE + 60)
    with pytest.raises(ValidationError):
        dataset(source="mt5_live")
    with pytest.raises(ValidationError):
        ResearchBar(**(make_bar(0).model_dump() | {"high": 1}))


@pytest.mark.parametrize(
    "changes",
    [
        dict(risk_percent=2),
        dict(fast_period=4),
        dict(volume_min=200),
        dict(commission_roundtrip_per_lot=-1),
        dict(slippage=float("inf")),
        dict(strategy="martingale"),
    ],
)
def test_m3_05_invalid_strategy_or_cost_assumptions(changes):
    with pytest.raises(ValidationError):
        ResearchConfig(**(CONFIG | changes))


def test_m3_06_stop_first_when_both_hit_and_next_bar_entry(monkeypatch):
    force_signal(monkeypatch)
    result = run_backtest(request([make_bar(0), make_bar(1), make_bar(2, high=106, low=95)]))
    trade = result["trades"][0]
    assert trade["entry_time"] == BASE + 120
    assert trade["signal_close_time"] == trade["entry_time"]
    assert trade["entry"] == 101 and trade["stop_loss"] == 99 and trade["take_profit"] == 105
    assert trade["exit"] == 99 and trade["exit_reason"] == "stop"
    assert trade["net_profit"] == pytest.approx(-24)
    assert not result["promotion_eligible"] and not result["execution_allowed"]


def test_m3_07_buy_target_uses_bid_exit(monkeypatch):
    force_signal(monkeypatch)
    trade = run_backtest(request([make_bar(0), make_bar(1), make_bar(2, high=106, low=100)]))[
        "trades"
    ][0]
    assert trade["entry"] == 101 and trade["exit"] == 105
    assert trade["net_profit"] == pytest.approx(48)


def test_m3_08_short_target_uses_ask_exit(monkeypatch):
    force_signal(monkeypatch, "sell")
    trade = run_backtest(request([make_bar(0), make_bar(1), make_bar(2, high=100, low=95)]))[
        "trades"
    ][0]
    assert trade["entry"] == 100 and trade["exit"] == 96
    assert trade["net_profit"] == pytest.approx(48)


@pytest.mark.parametrize("side,opening,expected", [("buy", 90, 89.9), ("sell", 110, 111.1)])
def test_m3_09_adverse_gap_slippage(side, opening, expected):
    position = dict(
        side=side, stop_loss=99 if side == "buy" else 102, take_profit=105 if side == "buy" else 96
    )
    bar = make_bar(0, close=opening, open=opening, high=opening + 1, low=opening - 1)
    price, reason = exit_for_bar(position, bar, 0.1)
    assert price == pytest.approx(expected) and reason == "stop_gap"


def test_m3_10_volume_rounding_and_stop_budget(monkeypatch):
    force_signal(monkeypatch)
    config = ResearchConfig(**(CONFIG | dict(slippage=0.1, commission_roundtrip_per_lot=7)))
    volume = volume_for_risk(10000, 2, config)
    assert volume == 0.11
    assert volume * (210 + 7) <= 25
    result = run_backtest(
        request(
            [make_bar(0), make_bar(1), make_bar(2, high=106, low=95)],
            slippage=0.1,
            commission_roundtrip_per_lot=7,
        )
    )
    trade = result["trades"][0]
    assert trade["commission"] == pytest.approx(0.77)
    assert trade["net_profit"] == pytest.approx(-23.87)


def test_m3_11_explicit_swap_and_exit_bound(monkeypatch):
    force_signal(monkeypatch)
    # Enter before UTC midnight, exit at the next bar close across midnight.
    boundary = (BASE // 86400 + 1) * 86400
    bars = [
        make_bar(i, open_time=boundary - 180 + i * 60, high=100.1, low=99.9, spread=0.01)
        for i in range(3)
    ]
    result = run_backtest(request(bars, stop_atr=10, swap_cost_per_lot_day=3))
    trade = result["trades"][0]
    assert trade["exit_reason"] == "end_of_sample"
    assert trade["swap_cost"] == pytest.approx(3 * trade["volume"])
    assert trade["net_profit"] == pytest.approx(trade["gross_profit"] - trade["swap_cost"])


def test_m3_12_no_trade_or_insufficient_volume(monkeypatch):
    assert run_backtest(request())["metrics"]["trade_count"] == 0
    force_signal(monkeypatch)
    assert run_backtest(request(volume_min=1))["metrics"]["trade_count"] == 0


def test_m3_13_gaps_and_spread_skip_entries(monkeypatch):
    force_signal(monkeypatch)
    bars = [make_bar(0), make_bar(1), make_bar(3)]
    result = run_backtest(request(bars))
    assert result["skipped_entries"] == 1 and result["metrics"]["trade_count"] == 0
    bars = [make_bar(0), make_bar(1), make_bar(2, spread=3)]
    assert run_backtest(request(bars))["skipped_entries"] == 1


def test_m3_14_only_one_trade_at_a_time_no_backdated_reentry(monkeypatch):
    monkeypatch.setattr(
        "aura.backtest.signals", lambda data, config, computed: [None] + ["buy"] * 5
    )
    bars = [make_bar(i, high=100.1, low=99.9, spread=0.01) for i in range(6)]
    result = run_backtest(request(bars, stop_atr=10))
    assert len(result["trades"]) == 1
    assert result["trades"][0]["exit_reason"] == "end_of_sample"


def test_m3_15_drawdown_halts_new_entries(monkeypatch):
    monkeypatch.setattr(
        "aura.backtest.signals", lambda data, config, computed: [None] + ["buy"] * 5
    )
    bars = [make_bar(i, high=106, low=95) if i >= 2 else make_bar(i) for i in range(6)]
    result = run_backtest(request(bars, max_drawdown_percent=0.1))
    assert result["drawdown_entry_halt"] and len(result["trades"]) == 1


def test_m3_16_metrics_empty_and_loss_cases():
    assert metrics([], 10000)["win_rate"] is None
    assert metrics([{"net_profit": 10}], 10000)["profit_factor_unbounded"]
    result = metrics([{"net_profit": 100}, {"net_profit": -50}], 10000)
    assert result["expectancy"] == 25 and result["profit_factor"] == 2
    assert result["max_closed_trade_drawdown_percent"] == pytest.approx(50 / 10100 * 100)


def test_m3_17_immutable_dataset_reproducibility(monkeypatch):
    force_signal(monkeypatch)
    req = request()
    original = deepcopy(req.model_dump())
    a, b = run_backtest(req), run_backtest(req)
    assert a == b and req.model_dump() == original
    assert run_backtest(request(slippage=0.2))["request_hash"] != a["request_hash"]


def test_m3_18_persistence_keeps_request_and_research_only_memory(tmp_path):
    store = Store(tmp_path)
    result = persist_backtest(store, request())
    record = Store(tmp_path).records("historical")[0]
    assert record["id"] == result["record_id"]
    assert record["payload"]["request"]["dataset"]["source"] == "fixture"
    assert record["payload"]["result"]["request_hash"] == result["request_hash"]
    assert store.records("virtual") == store.records("demo") == []


def test_m3_19_channel_breakout_excludes_current_bar_in_channel():
    bars = [make_bar(i) for i in range(6)] + [make_bar(6, close=103)]
    cfg = ResearchConfig(**(CONFIG | {"strategy": "channel_breakout_v1"}))
    computed = features(bars, 2, 3, 2)
    assert signals(dataset(bars), cfg, computed)[-1] == "buy"


def test_m3_20_authenticated_backtest_workflow(tmp_path):
    admin, viewer = "a" * 40, "b" * 40
    with TestClient(create_app(Settings(tmp_path, admin, viewer))) as client:
        payload = request().model_dump(mode="json")
        assert client.post("/v1/research/backtest", json=payload).status_code == 401
        assert (
            client.post(
                "/v1/research/backtest", json=payload, headers={"Authorization": "Bearer " + viewer}
            ).status_code
            == 403
        )
        result = client.post(
            "/v1/research/backtest", json=payload, headers={"Authorization": "Bearer " + admin}
        )
        assert result.status_code == 200 and not result.json()["execution_allowed"]
        assert (
            client.post(
                "/v1/research/backtest",
                json=payload | {"live_enabled": True},
                headers={"Authorization": "Bearer " + admin},
            ).status_code
            == 422
        )


def test_m3_21_extreme_slippage_rejected_before_simulation():
    with pytest.raises(ValidationError):
        request(slippage=100)


def test_m3_22_runnable_fixture_contains_no_promotion(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    sample = Path("examples/backtest_fixture.json")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "aura.research",
            "--request",
            str(sample),
            "--data-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(result.stdout)
    assert report["data_source"] == "fixture"
    assert report["metrics"]["trade_count"] > 0
    assert report["promotion_eligible"] is False
    assert report["execution_allowed"] is False
    assert Store(tmp_path).records("historical")[0]["kind"] == "backtest"
