"""Explicit short-lived quote correction; never infer an offset from tick age."""

from pydantic import Field, model_validator

from .market import MarketModel


class QuoteTimePolicy(MarketModel):
    server: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=64)
    offset_seconds: int = Field(strict=True, ge=-50400, le=50400)
    verified_at_msc: int = Field(strict=True, gt=0)
    expires_at_msc: int = Field(strict=True, gt=0)
    evidence: str = Field(min_length=8, max_length=256)

    @model_validator(mode="after")
    def window(self):
        if not 0 < self.expires_at_msc - self.verified_at_msc <= 86400000:
            raise ValueError("Quote correction must expire within 24 hours")
        if self.offset_seconds % 900:
            raise ValueError("Offset must be a whole quarter-hour")
        return self

    def normalize(self, raw_msc, now_msc, server, symbol):
        if server != self.server or symbol != self.symbol:
            raise ValueError("Quote time policy does not match server/symbol")
        if not self.verified_at_msc <= now_msc < self.expires_at_msc:
            raise ValueError("Quote time policy is not currently valid")
        return raw_msc - self.offset_seconds * 1000


def load_policy(path):
    from pathlib import Path

    return QuoteTimePolicy.model_validate_json(Path(path).read_text()) if path else None


class HistoryTimePolicy(MarketModel):
    """Operator-attested constant offset for one closed, dated intraday interval."""

    server: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=64)
    timeframe: str
    offset_seconds: int = Field(strict=True, ge=-50400, le=50400)
    valid_from_utc: int = Field(strict=True, gt=0)
    valid_to_utc: int = Field(strict=True, gt=0)
    reviewed_at_msc: int = Field(strict=True, gt=0)
    evidence: str = Field(min_length=8, max_length=256)

    @model_validator(mode="after")
    def bounded_interval(self):
        from .market import TIMEFRAMES

        if self.timeframe not in TIMEFRAMES or self.timeframe == "D1":
            raise ValueError("Only intraday timeframes have a history correction policy")
        if self.offset_seconds % 900:
            raise ValueError("Offset must be a whole quarter-hour")
        if not 0 < self.valid_to_utc - self.valid_from_utc <= 31 * 86400:
            raise ValueError("History evidence must cover at most 31 days")
        if self.valid_to_utc * 1000 > self.reviewed_at_msc:
            raise ValueError("History policy must describe an already observed interval")
        if self.valid_from_utc + self.offset_seconds <= 0:
            raise ValueError("Shifted request must remain positive")
        return self

    def require_scope(self, server, symbol, timeframe, start, end, now_msc):
        if (server, symbol, timeframe) != (self.server, self.symbol, self.timeframe):
            raise ValueError("History policy scope mismatch")
        if not self.valid_from_utc <= start < end <= self.valid_to_utc:
            raise ValueError("History request is outside the reviewed interval")
        if self.reviewed_at_msc > now_msc:
            raise ValueError("History review is ahead of the VPS clock")


def load_history_policy(path):
    from pathlib import Path

    return HistoryTimePolicy.model_validate_json(Path(path).read_text()) if path else None
