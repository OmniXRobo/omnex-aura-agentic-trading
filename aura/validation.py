"""Chronological research evaluation, never trading permission or strategy promotion."""

import hashlib
import json
import math
import random
import time
import uuid

from pydantic import Field, model_validator

from .backtest import (
    EXPOSURE_SCHEMA,
    BacktestRequest,
    Dataset,
    ResearchConfig,
    ResearchModel,
    _index_exposures,
    run_backtest,
)
from .store import Store

SEARCH_FIELDS = {
    "strategy",
    "fast_period",
    "slow_period",
    "volatility_period",
    "stop_atr",
    "reward_risk",
}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


class ValidationRequest(ResearchModel):
    dataset: Dataset
    candidates: list[ResearchConfig] = Field(min_length=1, max_length=6)
    train_bars: int = Field(default=80, ge=10, le=3000)
    test_bars: int = Field(default=20, ge=5, le=1000)
    gap_bars: int = Field(default=2, ge=1, le=200)
    holdout_bars: int = Field(default=30, ge=5, le=1000)
    max_folds: int = Field(default=10, ge=1, le=20)
    min_train_trades: int = Field(default=3, ge=1, le=200)
    min_test_trades: int = Field(default=30, ge=10, le=1000)
    bootstrap_paths: int = Field(default=200, ge=50, le=1000)
    seed: int = Field(default=7, ge=0, le=2**32 - 1)

    @model_validator(mode="after")
    def validate_experiment(self):
        development_end = len(self.dataset.bars) - self.holdout_bars
        if self.train_bars + self.gap_bars + self.test_bars > development_end:
            raise ValueError("Insufficient data for disjoint train/gap/test/final-holdout windows")
        identities = [fingerprint(c.model_dump(mode="json")) for c in self.candidates]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate candidates are not independent alternatives")
        reference = self.candidates[0].model_dump(exclude=SEARCH_FIELDS)
        for candidate in self.candidates:
            if candidate.model_dump(exclude=SEARCH_FIELDS) != reference:
                raise ValueError("Candidate costs, sizing and risk policy must be identical")
            if self.train_bars <= max(candidate.slow_period, candidate.volatility_period):
                raise ValueError("Training window must exceed every candidate warmup")
        return self


def folds(request):
    boundary = len(request.dataset.bars) - request.holdout_bars
    training_end = request.train_bars
    result = []
    while (
        training_end + request.gap_bars + request.test_bars <= boundary
        and len(result) < request.max_folds
    ):
        testing_start = training_end + request.gap_bars
        result.append((training_end, testing_start, testing_start + request.test_bars))
        training_end += request.test_bars
    return result


def _prefix(dataset, end):
    bars = dataset.bars[:end]
    return Dataset.model_validate(
        dataset.model_dump(exclude={"bars", "as_of"})
        | {
            "bars": [bar.model_dump() for bar in bars],
            "as_of": bars[-1].open_time + dataset.interval_seconds,
        }
    )


def _select(request, training_end):
    """No future test/holdout bars are supplied to the candidate evaluator."""
    scores = []
    for candidate in request.candidates:
        result = run_backtest(
            BacktestRequest(dataset=_prefix(request.dataset, training_end), config=candidate)
        )
        candidate_id = fingerprint(candidate.model_dump(mode="json"))
        metrics = result["metrics"]
        eligible = (
            metrics["trade_count"] >= request.min_train_trades
            and metrics["net_profit"] > 0
            and not result["drawdown_entry_halt"]
        )
        scores.append(
            {
                "candidate_id": candidate_id,
                "eligible": eligible,
                "training_metrics": metrics,
                "config": candidate,
            }
        )
    eligible = sorted(
        (s for s in scores if s["eligible"]),
        key=lambda s: (-s["training_metrics"]["net_profit"], s["candidate_id"]),
    )
    selected = eligible[0] if eligible else None
    return selected, [{k: v for k, v in score.items() if k != "config"} for score in scores]


def _test(request, selected, start, end):
    if selected is None:
        return {
            "decision": "NO TRADE",
            "reason": "No training-eligible candidate",
            "trades": [],
            "candidate_id": None,
        }
    result = run_backtest(
        BacktestRequest(
            dataset=_prefix(request.dataset, end),
            config=selected["config"],
            evaluation_start=request.dataset.bars[start].open_time,
        )
    )
    return {
        "decision": "RESEARCH EVALUATION",
        "candidate_id": selected["candidate_id"],
        "metrics": result["metrics"],
        "trades": result["trades"],
        "engine_version": result["engine_version"],
    }


def bootstrap(profits, initial_equity, paths=200, seed=7):
    """IID resampling diagnostics, NOT a calibrated future-return confidence interval."""
    if not 1 <= paths <= 1000 or not math.isfinite(initial_equity) or initial_equity <= 0:
        raise ValueError("Invalid resampling limits")
    if any(not math.isfinite(profit) for profit in profits):
        raise ValueError("Non-finite trade result")
    if not profits:
        return {
            "status": "no_test_trades",
            "method": "iid_closed_trade_bootstrap",
            "paths": 0,
            "mean_trade_percentile_interval": None,
        }
    generator = random.Random(seed)
    means, drawdowns = [], []
    for _ in range(paths):
        equity = peak = initial_equity
        drawdown = total = 0.0
        for _ in profits:
            profit = generator.choice(profits)
            total += profit
            equity += profit
            peak = max(peak, equity)
            drawdown = max(drawdown, 100 * (peak - equity) / peak)
        means.append(total / len(profits))
        drawdowns.append(drawdown)
    means.sort()
    drawdowns.sort()
    return {
        "status": "research_diagnostic",
        "method": "iid_closed_trade_bootstrap",
        "seed": seed,
        "paths": paths,
        "trade_count": len(profits),
        "mean_trade_percentile_interval": [
            means[int((paths - 1) * 0.025)],
            means[int((paths - 1) * 0.975)],
        ],
        "closed_trade_drawdown_p95": drawdowns[int((paths - 1) * 0.95)],
        "limitations": "IID resampling ignores serial dependence, regimes and selection bias",
    }


def _run_validation(request):
    walk_forward = []
    pooled_trades = []
    for training_end, test_start, test_end in folds(request):
        selected, scores = _select(request, training_end)
        tested = _test(request, selected, test_start, test_end)
        pooled_trades.extend(tested["trades"])
        walk_forward.append(
            {
                "train_index_range": [0, training_end],
                "gap_index_range": [training_end, test_start],
                "test_index_range": [test_start, test_end],
                "candidate_scores": scores,
                "evaluation": tested,
            }
        )
    holdout_start = len(request.dataset.bars) - request.holdout_bars
    selected, scores = _select(request, holdout_start - request.gap_bars)
    final = _test(request, selected, holdout_start, len(request.dataset.bars))
    # Keep final-holdout diagnostics separate from development/test-selection diagnostics.
    profits = [trade["net_profit"] for trade in pooled_trades]
    return {
        "validation_version": "chronological-v1",
        "request_hash": fingerprint(request.model_dump(mode="json")),
        "dataset_label": request.dataset.label,
        "data_source": request.dataset.source,
        "folds": walk_forward,
        "final_holdout": {
            "index_range": [holdout_start, len(request.dataset.bars)],
            "selection_train_end": holdout_start - request.gap_bars,
            "candidate_scores": scores,
            "evaluation": final,
        },
        "development_test_summary": {
            "trade_count": len(profits),
            "net_profit_sum": sum(profits),
            "accounting": "independent_windows_reset_equity",
        },
        "development_bootstrap": bootstrap(
            profits, request.candidates[0].initial_equity, request.bootstrap_paths, request.seed
        ),
        "evidence_status": (
            "insufficient_development_test_trades"
            if len(profits) < request.min_test_trades
            else "research_only_unvalidated"
        ),
        "promotion_eligible": False,
        "execution_allowed": False,
        "limitations": [
            "Synthetic/user-supplied provenance is not broker-certified",
            "Fixed candidate search; adaptive ML is not implemented",
            "Embargo is measured in supplied bars, not economic time",
            "Final holdout is excluded from bootstrap and fold summaries",
        ],
    }


class HoldoutConflict(ValueError):
    pass


LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS validation_ledger (
 id TEXT PRIMARY KEY, scope TEXT NOT NULL, holdout_start INTEGER NOT NULL,
 holdout_end INTEGER NOT NULL, request_hash TEXT NOT NULL UNIQUE,
 state TEXT NOT NULL, record_id TEXT, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS validation_scope ON validation_ledger(scope,holdout_start,holdout_end);
INSERT OR IGNORE INTO schema_version VALUES (3);
"""


def persist_validation(store: Store, request: ValidationRequest):
    request_hash = fingerprint(request.model_dump(mode="json"))
    start = request.dataset.bars[-request.holdout_bars].open_time
    end = request.dataset.bars[-1].open_time + request.dataset.interval_seconds
    scope = request.dataset.symbol
    with store.connect() as db:
        db.executescript(LEDGER_SCHEMA + EXPOSURE_SCHEMA)
        db.execute("BEGIN IMMEDIATE")
        _index_exposures(db)
        previous = db.execute(
            "SELECT * FROM validation_ledger WHERE request_hash=?", (request_hash,)
        ).fetchone()
        if previous is not None:
            if previous["state"] != "complete":
                raise HoldoutConflict(
                    "Validation already reserved or failed; no automatic holdout retry"
                )
            record = db.execute(
                "SELECT payload FROM records WHERE id=?", (previous["record_id"],)
            ).fetchone()
            if record is None:
                raise HoldoutConflict("Stored validation evidence unavailable")
            return {
                "record_id": previous["record_id"],
                "replayed": True,
                **json.loads(record[0])["result"],
            }
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='research_exposures'").fetchone():
            exposed = db.execute(
                "SELECT request_hash FROM research_exposures WHERE scope=? "
                "AND start_time<? AND end_time>? LIMIT 1",
                (scope, end, start),
            ).fetchone()
            if exposed:
                raise HoldoutConflict("Final holdout was already used by exploratory backtesting")
        overlap = db.execute(
            "SELECT id FROM validation_ledger WHERE scope=? AND holdout_start<? "
            "AND holdout_end>? LIMIT 1",
            (scope, end, start),
        ).fetchone()
        if overlap:
            raise HoldoutConflict(
                "Final holdout window already reserved; use a fresh holdout interval"
            )
        identifier = str(uuid.uuid4())
        db.execute(
            "INSERT INTO validation_ledger VALUES (?,?,?,?,?,?,NULL,?)",
            (identifier, scope, start, end, request_hash, "reserved", time.time()),
        )
    try:
        result = _run_validation(request)
        record_id = store.record(
            "historical",
            "validation",
            {"request": request.model_dump(mode="json"), "result": result},
        )
        store.audit(
            "research",
            "validation.completed",
            {"record_id": record_id, "request_hash": request_hash},
        )
        with store.connect() as db:
            db.execute(
                "UPDATE validation_ledger SET state='complete',record_id=? WHERE id=?",
                (record_id, identifier),
            )
        return {"record_id": record_id, "replayed": False, **result}
    except Exception:
        with store.connect() as db:
            db.execute("UPDATE validation_ledger SET state='failed' WHERE id=?", (identifier,))
        raise
