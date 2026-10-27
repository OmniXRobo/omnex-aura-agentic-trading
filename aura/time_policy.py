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
