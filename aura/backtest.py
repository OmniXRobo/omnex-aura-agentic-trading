"""Offline single-instrument research simulation. No broker or AI provider access."""

import hashlib
import json
from decimal import ROUND_FLOOR, Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .features import features
from .store import Store


class ResearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)


class ResearchBar(ResearchModel):
    # Bid OHLC; ask is modelled with an explicit constant spread for the whole bar.
    open_time: int = Field(gt=0, le=4102444800, strict=True)
    open: float = Field(ge=1e-6, le=1e7)
    high: float = Field(ge=1e-6, le=1e7)
    low: float = Field(ge=1e-6, le=1e7)
    close: float = Field(ge=1e-6, le=1e7)
    spread: float = Field(ge=0, le=1e5)

    @model_validator(mode="after")
    def geometry(self):
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("Invalid bid OHLC range")
        return self


class Dataset(ResearchModel):
    label: str = Field(min_length=1, max_length=80)
    source: Literal["fixture", "user_supplied"]
    symbol: Literal["XAUUSD"] = "XAUUSD"
    interval_seconds: int = Field(gt=0, le=86400, strict=True)
    as_of: int = Field(gt=0, le=4102444800, strict=True)
    bars: list[ResearchBar] = Field(min_length=3, max_length=5000)

    @model_validator(mode="after")
    def closed_and_ordered(self):
        for index, bar in enumerate(self.bars):
            if bar.open_time + self.interval_seconds > self.as_of:
                raise ValueError("Dataset contains an unfinished candle")
            if index and bar.open_time < self.bars[index - 1].open_time + self.interval_seconds:
                raise ValueError("Overlapping, duplicated or unordered candles")
        return self


class ResearchConfig(ResearchModel):
    strategy: Literal["ema_cross_v1", "channel_breakout_v1"]
    fast_period: int = Field(default=5, ge=2, le=100)
    slow_period: int = Field(default=20, ge=3, le=200)
    volatility_period: int = Field(default=14, ge=2, le=100)
    stop_atr: float = Field(default=2, ge=0.1, le=10)
    reward_risk: float = Field(default=2, ge=1, le=4)
    risk_percent: float = Field(default=0.25, gt=0, le=0.25)
    initial_equity: float = Field(default=10000, ge=100, le=1e8)
    # Explicit USD costs/contract assumptions, never guessed from a broker name.
    contract_size: float = Field(ge=1e-6, le=1e5)
    volume_min: float = Field(ge=1e-8, le=1000)
    volume_max: float = Field(gt=0, le=1000)
    volume_step: float = Field(ge=1e-8, le=1000)
    commission_roundtrip_per_lot: float = Field(ge=0, le=1e5)
    slippage: float = Field(ge=0, le=1e5)
    swap_cost_per_lot_day: float = Field(ge=-1e5, le=1e5)
    max_drawdown_percent: float = Field(default=5, gt=0, le=10)
    max_spread: float = Field(gt=0)

    @model_validator(mode="after")
    def consistency(self):
        if self.fast_period >= self.slow_period:
            raise ValueError("Fast period must be below slow period")
        if self.volume_min > self.volume_max or self.volume_step > self.volume_max:
            raise ValueError("Invalid volume constraints")
        return self


class BacktestRequest(ResearchModel):
    dataset: Dataset
    config: ResearchConfig

    @model_validator(mode="after")
    def positive_executable_prices(self):
        if any(bar.low <= self.config.slippage for bar in self.dataset.bars):
            raise ValueError("Slippage would produce a non-positive executable quote")
        return self


def signals(dataset: Dataset, config: ResearchConfig, computed):
    output = [None] * len(dataset.bars)
    for i in range(1, len(dataset.bars)):
        current, previous = computed[i], computed[i - 1]
        if current["atr_sma"] is None or current["atr_sma"] <= 0:
            continue
        if config.strategy == "ema_cross_v1":
            if previous["slow_ema"] is None or current["slow_ema"] is None:
                continue
            if (
                previous["fast_ema"] <= previous["slow_ema"]
                and current["fast_ema"] > current["slow_ema"]
            ):
                output[i] = "buy"
            elif (
                previous["fast_ema"] >= previous["slow_ema"]
                and current["fast_ema"] < current["slow_ema"]
            ):
                output[i] = "sell"
        elif i >= config.slow_period:
            window = dataset.bars[i - config.slow_period : i]
            if dataset.bars[i].close > max(bar.high for bar in window):
                output[i] = "buy"
            elif dataset.bars[i].close < min(bar.low for bar in window):
                output[i] = "sell"
    return output


def volume_for_risk(equity, distance, config):
    # Reserve adverse exit slippage and commission in the modeled SL-loss budget.
    loss_per_lot = (
        distance + config.slippage
    ) * config.contract_size + config.commission_roundtrip_per_lot
    available = min(config.volume_max, equity * config.risk_percent / 100 / loss_per_lot)
    step = Decimal(str(config.volume_step))
    volume = float(
        (Decimal(str(max(available, 0))) / step).to_integral_value(rounding=ROUND_FLOOR) * step
    )
    return volume if volume >= config.volume_min else 0.0


def exit_for_bar(position, bar, slippage):
    """Adverse gaps fill at opening executable quote. If both levels hit, SL wins."""
    buy = position["side"] == "buy"
    offset = 0 if buy else bar.spread
    opening, high, low = bar.open + offset, bar.high + offset, bar.low + offset
    stop, target = position["stop_loss"], position["take_profit"]
    if (buy and opening <= stop) or (not buy and opening >= stop):
        return opening - slippage if buy else opening + slippage, "stop_gap"
    if (buy and opening >= target) or (not buy and opening <= target):
        # Conservative target fill: never assume favorable gap improvement.
        return target - slippage if buy else target + slippage, "target"
    if low <= stop if buy else high >= stop:
        return stop - slippage if buy else stop + slippage, "stop"
    if high >= target if buy else low <= target:
        return target - slippage if buy else target + slippage, "target"
    return None


def metrics(trades, initial_equity):
    equity, peak, drawdown = initial_equity, initial_equity, 0.0
    profits = [trade["net_profit"] for trade in trades]
    for profit in profits:
        equity += profit
        peak = max(peak, equity)
        drawdown = max(drawdown, 100 * (peak - equity) / peak)
    gross_win = sum(max(p, 0) for p in profits)
    gross_loss = -sum(min(p, 0) for p in profits)
    return {
        "trade_count": len(trades),
        "ending_equity": equity,
        "net_profit": sum(profits),
        "win_rate": sum(p > 0 for p in profits) / len(profits) if profits else None,
        "expectancy": sum(profits) / len(profits) if profits else None,
        "profit_factor": gross_win / gross_loss if gross_loss else None,
        "profit_factor_unbounded": bool(gross_win and not gross_loss),
        "max_closed_trade_drawdown_percent": drawdown,
    }


def run_backtest(request: BacktestRequest):
    dataset, config = request.dataset, request.config
    computed = features(
        dataset.bars, config.fast_period, config.slow_period, config.volatility_period
    )
    proposals = signals(dataset, config, computed)
    position, trades, equity, peak = None, [], config.initial_equity, config.initial_equity
    halted, skipped = False, 0
    for index, bar in enumerate(dataset.bars):
        # Only the previous CLOSED candle may trigger entry at this bar's open.
        if position is None and index and not halted and proposals[index - 1]:
            previous = dataset.bars[index - 1]
            if (
                bar.open_time != previous.open_time + dataset.interval_seconds
                or bar.spread > config.max_spread
            ):
                skipped += 1
            else:
                side = proposals[index - 1]
                entry = (
                    bar.open + bar.spread + config.slippage
                    if side == "buy"
                    else bar.open - config.slippage
                )
                distance = computed[index - 1]["atr_sma"] * config.stop_atr
                volume = volume_for_risk(equity, distance, config)
                stop = entry - distance if side == "buy" else entry + distance
                target = (
                    entry + distance * config.reward_risk
                    if side == "buy"
                    else entry - distance * config.reward_risk
                )
                if volume and min(entry, stop, target) > 0:
                    position = {
                        "side": side,
                        "entry_time": bar.open_time,
                        "signal_close_time": previous.open_time + dataset.interval_seconds,
                        "entry": entry,
                        "stop_loss": stop,
                        "take_profit": target,
                        "volume": volume,
                        "strategy": config.strategy,
                    }
                else:
                    skipped += 1
        if position is None:
            continue
        exit_value = exit_for_bar(position, bar, config.slippage)
        if exit_value is None and index == len(dataset.bars) - 1:
            price = (
                bar.close - config.slippage
                if position["side"] == "buy"
                else bar.close + bar.spread + config.slippage
            )
            exit_value = price, "end_of_sample"
        if exit_value is None:
            continue
        price, reason = exit_value
        # Intrabar exits have no known tick time: use the bar close as a conservative bound.
        exit_time = bar.open_time + dataset.interval_seconds
        direction = 1 if position["side"] == "buy" else -1
        gross = (price - position["entry"]) * direction * config.contract_size * position["volume"]
        commission = config.commission_roundtrip_per_lot * position["volume"]
        nights = max(0, exit_time // 86400 - position["entry_time"] // 86400)
        swap = nights * config.swap_cost_per_lot_day * position["volume"]
        net = gross - commission - swap
        trades.append(
            {
                **position,
                "exit_time_upper_bound": exit_time,
                "exit": price,
                "exit_reason": reason,
                "gross_profit": gross,
                "commission": commission,
                "swap_cost": swap,
                "net_profit": net,
            }
        )
        equity += net
        peak = max(peak, equity)
        halted = (
            halted or equity <= 0 or 100 * (peak - equity) / peak >= config.max_drawdown_percent
        )
        position = None
    canonical = json.dumps(request.model_dump(mode="json"), sort_keys=True, allow_nan=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return {
        "request_hash": digest,
        "engine_version": "bar-research-v1",
        "dataset_label": dataset.label,
        "data_source": dataset.source,
        "strategy": config.strategy,
        "metrics": metrics(trades, config.initial_equity),
        "trades": trades,
        "drawdown_entry_halt": halted,
        "skipped_entries": skipped,
        "promotion_eligible": False,
        "execution_allowed": False,
        "assumptions": {
            "quote_model": "bid_ohlc_constant_bar_spread",
            "account_currency": "USD",
            "both_hit_policy": "stop_first",
            "sample_type": "in_sample_research",
            "fill_times": "bar_open_entries_and_bounded_intrabar_exits",
        },
    }


def persist_backtest(store: Store, request: BacktestRequest):
    result = run_backtest(request)
    identifier = store.record(
        "historical", "backtest", {"request": request.model_dump(mode="json"), "result": result}
    )
    store.audit(
        "research",
        "backtest.completed",
        {"record_id": identifier, "request_hash": result["request_hash"]},
    )
    return {"record_id": identifier, **result}
