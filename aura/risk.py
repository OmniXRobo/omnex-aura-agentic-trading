from dataclasses import dataclass
from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .store import Store


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    symbol: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    side: Literal["buy", "sell"]
    entry: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    risk_percent: float = Field(gt=0)
    spread: float = Field(ge=0)
    tick_age_seconds: float = Field(ge=0)
    active_positions: int = Field(ge=0)
    news_blackout: bool


@dataclass(frozen=True)
class RiskLimits:
    max_risk_percent: float = 0.25
    max_spread: float = 0.5  # XAUUSD quote-price units; broker-specific policy later
    max_tick_age_seconds: float = 5

    def __post_init__(self):
        if any(not isfinite(v) or v <= 0 for v in vars(self).values()):
            raise ValueError("Risk limits must be positive and finite")


class RiskController:
    def __init__(self, store: Store, limits=RiskLimits()):
        self.store, self.limits = store, limits

    def evaluate(self, p: Proposal):
        reasons = []
        try:
            if self.store.killed():
                reasons.append("Emergency stop is active")
        except Exception:
            reasons.append("Safety state unavailable: fail closed")
        if p.symbol.upper() != "XAUUSD":
            reasons.append("Broker symbol mapping and instrument policy not yet verified")
        valid_stops = (
            p.stop_loss < p.entry < p.take_profit
            if p.side == "buy"
            else p.take_profit < p.entry < p.stop_loss
        )
        if not valid_stops:
            reasons.append("Invalid protective stop or target geometry")
        if p.risk_percent > self.limits.max_risk_percent:
            reasons.append("Risk per trade exceeds limit")
        if p.spread > self.limits.max_spread:
            reasons.append("Spread exceeds limit")
        if p.tick_age_seconds > self.limits.max_tick_age_seconds:
            reasons.append("Market data is stale")
        if p.active_positions:
            reasons.append("One position per instrument limit")
        if p.news_blackout:
            reasons.append("News blackout")
        return {
            "eligible_for_research": not reasons,
            "reasons": reasons,
            "execution_allowed": False,
            "live_enabled": False,
        }
