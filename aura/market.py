"""Validated gold data contracts. These models cannot authorize any execution."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TIMEFRAMES = {
    "M1": 60,
    "M5": 300,
    "M10": 600,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
}


class MarketModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)


class Feed(MarketModel):
    broker: str = Field(min_length=1, max_length=48, pattern=r"^[A-Za-z0-9_.-]+$")
    source: Literal["fixture", "mt5_demo"]
    # Local non-secret identifier; never a password or broker login.
    stream: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")

    @property
    def key(self):
        return f"{self.source}:{self.broker}:{self.stream}"


class GoldContract(MarketModel):
    symbol: str = Field(min_length=1, max_length=64)
    currency_base: Literal["XAU"]
    currency_profit: Literal["USD"]
    digits: int = Field(ge=0, le=10)
    point: float = Field(gt=0)
    trade_tick_size: float = Field(gt=0)
    trade_tick_value: float = Field(gt=0)
    trade_contract_size: float = Field(gt=0)
    volume_min: float = Field(gt=0)
    volume_max: float = Field(gt=0)
    volume_step: float = Field(gt=0)
    trade_stops_level: int = Field(ge=0)
    trade_freeze_level: int = Field(ge=0)
    trade_mode: int = Field(ge=0)
    filling_mode: int = Field(ge=0)
    swap_mode: int = Field(ge=0)
    swap_long: float
    swap_short: float

    @model_validator(mode="after")
    def validate_sizes(self):
        if self.volume_min > self.volume_max or self.volume_step > self.volume_max:
            raise ValueError("Inconsistent broker volume constraints")
        if abs(self.point - 10**-self.digits) > self.point * 1e-6:
            raise ValueError("Point and precision disagree")
        return self


class Quote(MarketModel):
    symbol: str = Field(min_length=1, max_length=64)
    time_msc: int = Field(gt=0)
    bid: float = Field(gt=0)
    ask: float = Field(gt=0)
    flags: int = Field(ge=0)

    @model_validator(mode="after")
    def uncrossed(self):
        if self.ask < self.bid:
            raise ValueError("Crossed quote")
        return self

    def require_fresh(self, now_msc: int, max_age_msc=5000):
        age = now_msc - self.time_msc
        if age < 0 or age > max_age_msc:
            raise ValueError("Future or stale quote")


class Candle(MarketModel):
    symbol: str = Field(min_length=1, max_length=64)
    timeframe: Literal["M1", "M5", "M10", "M15", "M30", "H1", "H4", "D1"]
    open_time: int = Field(gt=0)
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    tick_volume: int = Field(ge=0)
    spread_points: int = Field(ge=0)
    real_volume: int = Field(ge=0)

    @model_validator(mode="after")
    def valid_range(self):
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("OHLC range is inconsistent")
        if self.low > self.high:
            raise ValueError("Low exceeds high")
        return self

    @property
    def close_time(self):
        return self.open_time + TIMEFRAMES[self.timeframe]
