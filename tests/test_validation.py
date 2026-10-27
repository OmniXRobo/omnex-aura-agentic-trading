"""Chronological validation acceptance tests use synthetic data only."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aura.api import create_app
from aura.backtest import (
    BacktestRequest,
    Dataset,
    ResearchBar,
    ResearchConfig,
    ResearchConflict,
    persist_backtest,
    run_backtest,
)
from aura.config import Settings
from aura.store import Store
from aura.validation import (
    HoldoutConflict,
    ValidationRequest,
    _run_validation,
    bootstrap,
    folds,
    persist_validation,
)

BASE = 1700000400


def experiment():
    bars = [
        ResearchBar(
            open_time=BASE + i * 60,
            open=3000 + i,
            high=3001 + i,
            low=2999.8 + i,
            close=3000.8 + i,
            spread=0.1,
        )
        for i in range(90)
    ]
    cfg = ResearchConfig(
        strategy="channel_breakout_v1",
        fast_period=3,
        slow_period=8,
        volatility_period=5,
        stop_atr=1,
        reward_risk=1,
        contract_size=100,
        volume_min=0.01,
        volume_max=10,
        volume_step=0.01,
        commission_roundtrip_per_lot=7,
        slippage=0.05,
        swap_cost_per_lot_day=1,
        max_spread=0.5,
    )
    data = Dataset(
        label="synthetic-validation-fixture",
        source="fixture",
        interval_seconds=60,
        as_of=BASE + 90 * 60,
        bars=bars,
    )
    return ValidationRequest(
        dataset=data,
        candidates=[cfg],
        train_bars=30,
        test_bars=10,
        holdout_bars=20,
        gap_bars=2,
        min_train_trades=1,
        bootstrap_paths=50,
    )


def changed(req, **kw):
    return ValidationRequest.model_validate(req.model_dump(mode="json") | kw)


def test_v01_chronological_fold_boundaries():
    req = experiment()
    ranges = folds(req)
    assert ranges == [(30, 32, 42), (40, 42, 52), (50, 52, 62)]
    for train_end, start, end in ranges:
        assert train_end + req.gap_bars == start and end <= 70
    assert all(a[2] <= b[1] for a, b in zip(ranges, ranges[1:]))


@pytest.mark.parametrize(
    "change",
    [
        dict(holdout_bars=80),
        dict(gap_bars=0),
        dict(train_bars=10, candidates=[]),
        dict(bootstrap_paths=1001),
    ],
)
def test_v02_invalid_validation_configuration(change):
    with pytest.raises(ValidationError):
        changed(experiment(), **change)


def test_v03_candidate_policy_coherence_and_duplicates():
    req = experiment()
    cfg = req.candidates[0]
    with pytest.raises(ValidationError):
        changed(req, candidates=[cfg, cfg])
    other = cfg.model_copy(update={"commission_roundtrip_per_lot": 8})
    with pytest.raises(ValidationError):
        changed(req, candidates=[cfg, other])
    other = cfg.model_copy(update={"slow_period": 40})
    with pytest.raises(ValidationError):
        changed(req, candidates=[other])


def test_v04_warmup_cannot_open_test_position_early():
    req = experiment()
    start = req.dataset.bars[50].open_time
    result = run_backtest(
        BacktestRequest(dataset=req.dataset, config=req.candidates[0], evaluation_start=start)
    )
    assert result["trades"]
    assert all(t["entry_time"] >= start for t in result["trades"])
    with pytest.raises(ValidationError):
        BacktestRequest(dataset=req.dataset, config=req.candidates[0], evaluation_start=BASE - 1)


def test_v05_holdout_perturbation_cannot_change_training_selection():
    req = experiment()
    result = _run_validation(req)
    values = req.dataset.model_dump(mode="json")
    for i, bar in enumerate(values["bars"][70:]):
        price = 5000 - i * 10
        bar.update(open=price, high=price + 2, low=price - 2, close=price - 1)
    altered = changed(req, dataset=values)
    second = _run_validation(altered)
    assert [f["candidate_scores"] for f in result["folds"]] == [
        f["candidate_scores"] for f in second["folds"]
    ]
    assert (
        result["final_holdout"]["candidate_scores"] == second["final_holdout"]["candidate_scores"]
    )
    assert (
        result["final_holdout"]["evaluation"]["candidate_id"]
        == second["final_holdout"]["evaluation"]["candidate_id"]
    )


def test_v06_every_test_entry_respects_its_window():
    req = experiment()
    report = _run_validation(req)
    assert len(report["folds"]) == 3
    for fold in report["folds"]:
        start, end = fold["test_index_range"]
        for trade in fold["evaluation"]["trades"]:
            assert req.dataset.bars[start].open_time <= trade["entry_time"] < BASE + end * 60
            assert trade["exit_time_upper_bound"] <= BASE + end * 60
    for trade in report["final_holdout"]["evaluation"]["trades"]:
        assert trade["entry_time"] >= BASE + 70 * 60
    assert not report["promotion_eligible"] and not report["execution_allowed"]


def test_v07_no_training_eligible_candidate_means_no_trade():
    result = _run_validation(changed(experiment(), min_train_trades=200))
    assert all(f["evaluation"]["decision"] == "NO TRADE" for f in result["folds"])
    assert result["final_holdout"]["evaluation"]["decision"] == "NO TRADE"
    assert result["development_bootstrap"]["status"] == "no_test_trades"


def test_v08_bootstrap_determinism_constant_and_empty():
    a = bootstrap([-2, 3, 5, -1], 10000, 50, 7)
    assert a == bootstrap([-2, 3, 5, -1], 10000, 50, 7)
    constant = bootstrap([2] * 10, 10000, 50, 7)
    assert constant["mean_trade_percentile_interval"] == [2, 2]
    assert constant["closed_trade_drawdown_p95"] == 0
    assert bootstrap([], 10000)["status"] == "no_test_trades"
    assert bootstrap([-2] * 10, 10000, 50, 7)["closed_trade_drawdown_p95"] > 0


@pytest.mark.parametrize(
    "profits,equity,paths", [([float("inf")], 10000, 50), ([1], 0, 50), ([1], 10000, 0)]
)
def test_v09_invalid_resampling_input(profits, equity, paths):
    with pytest.raises(ValueError):
        bootstrap(profits, equity, paths)


def test_v10_exact_replay_after_restart_does_not_retest(tmp_path, monkeypatch):
    req = experiment()
    first = persist_validation(Store(tmp_path), req)

    def no_retest(_):
        pytest.fail("Cached final holdout must not be evaluated again")

    monkeypatch.setattr("aura.validation._run_validation", no_retest)
    second = persist_validation(Store(tmp_path), req)
    assert second["replayed"] and second["record_id"] == first["record_id"]
    assert len(Store(tmp_path).records("historical")) == 1
    assert Store(tmp_path).records("virtual") == Store(tmp_path).records("demo") == []


def test_v11_retuning_same_holdout_is_blocked(tmp_path):
    req = experiment()
    persist_validation(Store(tmp_path), req)
    for alteration in (
        {"seed": 8},
        {"min_train_trades": 2},
        {"dataset": req.dataset.model_dump() | {"label": "renamed"}},
    ):
        with pytest.raises(HoldoutConflict):
            persist_validation(Store(tmp_path), changed(req, **alteration))


def test_v12_overlapping_but_not_identical_holdout_is_blocked(tmp_path):
    req = experiment()
    persist_validation(Store(tmp_path), req)
    data = req.dataset.model_dump()
    data["bars"] = data["bars"][:-1]
    with pytest.raises(HoldoutConflict):
        persist_validation(Store(tmp_path), changed(req, dataset=data))


def test_v13_failed_validation_keeps_reservation(tmp_path, monkeypatch):
    req = experiment()

    def fails(_):
        raise RuntimeError("synthetic fault")

    monkeypatch.setattr("aura.validation._run_validation", fails)
    with pytest.raises(RuntimeError):
        persist_validation(Store(tmp_path), req)
    with pytest.raises(HoldoutConflict):
        persist_validation(Store(tmp_path), req)
    with Store(tmp_path).connect() as db:
        assert db.execute("SELECT state FROM validation_ledger").fetchone()[0] == "failed"


def test_v14_concurrent_request_cannot_retest_reserved_holdout(tmp_path, monkeypatch):
    entered, release = Event(), Event()

    def blocking(_):
        entered.set()
        assert release.wait(timeout=10)
        return {"execution_allowed": False, "promotion_eligible": False}

    monkeypatch.setattr("aura.validation._run_validation", blocking)
    store = Store(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(persist_validation, store, experiment())
        assert entered.wait(timeout=5)
        try:
            with pytest.raises(HoldoutConflict):
                persist_validation(store, experiment())
        finally:
            release.set()
        assert first.result(timeout=10)["execution_allowed"] is False


def test_v15_exploratory_backtest_cannot_read_reserved_holdout(tmp_path):
    req = experiment()
    store = Store(tmp_path)
    persist_validation(store, req)
    with pytest.raises(ResearchConflict):
        persist_backtest(store, BacktestRequest(dataset=req.dataset, config=req.candidates[0]))


def test_v16_prior_exploratory_exposure_disqualifies_holdout(tmp_path):
    req = experiment()
    store = Store(tmp_path)
    persist_backtest(store, BacktestRequest(dataset=req.dataset, config=req.candidates[0]))
    with pytest.raises(HoldoutConflict):
        persist_validation(store, req)


def test_v17_legacy_backtests_are_indexed_before_holdout_reservation(tmp_path):
    req = experiment()
    store = Store(tmp_path)
    legacy = BacktestRequest(dataset=req.dataset, config=req.candidates[0]).model_dump(mode="json")
    legacy.pop("evaluation_start")
    store.record("historical", "backtest", {"request": legacy, "result": {}})
    with pytest.raises(HoldoutConflict):
        persist_validation(store, req)


def test_v18_corrupt_legacy_evidence_blocks_validation(tmp_path):
    store = Store(tmp_path)
    store.record("historical", "backtest", {"request": {"incomplete": True}})
    for _ in range(2):
        with pytest.raises(ResearchConflict):
            persist_validation(store, experiment())


def test_v19_fresh_future_holdout_is_allowed(tmp_path):
    req = experiment()
    store = Store(tmp_path)
    persist_validation(store, req)
    values = req.dataset.model_dump()
    for bar in values["bars"]:
        bar["open_time"] += 86400
    values["as_of"] += 86400
    fresh = persist_validation(store, changed(req, dataset=values))
    assert fresh["replayed"] is False


def test_v20_api_auth_conflict_and_replay(tmp_path):
    req = experiment()
    payload = req.model_dump(mode="json")
    admin, viewer = "a" * 40, "b" * 40
    auth = {"Authorization": "Bearer " + admin}
    with TestClient(create_app(Settings(tmp_path, admin, viewer))) as client:
        assert client.post("/v1/research/validate", json=payload).status_code == 401
        assert (
            client.post(
                "/v1/research/validate", json=payload, headers={"Authorization": "Bearer " + viewer}
            ).status_code
            == 403
        )
        first = client.post("/v1/research/validate", json=payload, headers=auth)
        assert first.status_code == 200 and not first.json()["execution_allowed"]
        assert client.post("/v1/research/validate", json=payload, headers=auth).json()["replayed"]
        assert (
            client.post(
                "/v1/research/validate", json=payload | {"seed": 8}, headers=auth
            ).status_code
            == 409
        )
        backtest = BacktestRequest(dataset=req.dataset, config=req.candidates[0]).model_dump(
            mode="json"
        )
        assert client.post("/v1/research/backtest", json=backtest, headers=auth).status_code == 409


def test_v21_validation_cli_fixture_and_replay(tmp_path):
    import json
    import subprocess
    import sys

    command = [
        sys.executable,
        "-m",
        "aura.validate",
        "--request",
        "examples/validation_fixture.json",
        "--data-dir",
        str(tmp_path),
    ]
    first = json.loads(subprocess.run(command, capture_output=True, text=True, check=True).stdout)
    second = json.loads(subprocess.run(command, capture_output=True, text=True, check=True).stdout)
    assert first["fold_count"] == 3
    assert first["replayed"] is False and second["replayed"] is True
    assert first["record_id"] == second["record_id"]
    assert first["execution_allowed"] is False and first["promotion_eligible"] is False


def test_v22_test_sample_count_is_not_permission_to_promote():
    req = changed(experiment(), min_test_trades=10)
    result = _run_validation(req)
    assert result["development_test_summary"]["trade_count"] >= 10
    assert result["evidence_status"] == "research_only_unvalidated"
    assert result["promotion_eligible"] is False and result["execution_allowed"] is False


def test_v23_source_or_interval_relabel_cannot_bypass_holdout(tmp_path):
    req = experiment()
    store = Store(tmp_path)
    persist_validation(store, req)
    for change in ({"source": "user_supplied"}, {"interval_seconds": 30}):
        with pytest.raises(HoldoutConflict):
            persist_validation(store, changed(req, dataset=req.dataset.model_dump() | change))
