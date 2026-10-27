"""Provider-neutral research data contracts; no executable tools or broker actions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .agents import Snapshot

REVIEW_ROLES = ("technical_interpreter", "strategy_critic", "evidence_auditor")
ReviewRole = Literal["technical_interpreter", "strategy_critic", "evidence_auditor"]


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)


class ReviewContext(ReviewModel):
    snapshot: Snapshot
    hypothesis: str = Field(
        default="Review the supplied sample; evidence is unverified", max_length=2000
    )

    @model_validator(mode="after")
    def bounded_sample(self):
        if self.snapshot.symbol != "XAUUSD" or any(not 0 < p <= 1e7 for p in self.snapshot.prices):
            raise ValueError("Reviews require a positive finite XAUUSD sample")
        return self


class ReviewTask(ReviewModel):
    task_id: str = Field(min_length=1, max_length=64)
    role: ReviewRole
    context: ReviewContext


class ReviewEvidence(ReviewModel):
    verdict: Literal["REVIEW_ONLY", "INSUFFICIENT_EVIDENCE", "REJECT_HYPOTHESIS"]
    summary: str = Field(min_length=1, max_length=2000)
    evidence: list[str] = Field(min_length=1, max_length=8)
    limitations: list[str] = Field(min_length=1, max_length=8)
    execution_allowed: Literal[False] = False
    promotion_eligible: Literal[False] = False

    @model_validator(mode="after")
    def bounded_text(self):
        if any(not text or len(text) > 500 for text in self.evidence + self.limitations):
            raise ValueError("Evidence/limitations text exceeds schema limits")
        return self


class Usage(ReviewModel):
    input_tokens: int = Field(ge=0, le=100000, strict=True)
    output_tokens: int = Field(ge=0, le=20000, strict=True)
    cost_microusd: int = Field(ge=0, le=10**9, strict=True)


class ProviderReply(ReviewModel):
    provider: str = Field(min_length=1, max_length=48)
    model: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=128)
    review: ReviewEvidence
    usage: Usage


class Binding(ReviewModel):
    provider: str = Field(min_length=1, max_length=48, pattern=r"^[a-zA-Z0-9_.-]+$")
    model: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    timeout_seconds: float = Field(default=1, ge=0.005, le=10)
    max_attempts: int = Field(default=2, ge=1, le=3)
    max_input_tokens: int = Field(default=16000, ge=1, le=100000)
    max_output_tokens: int = Field(default=512, ge=1, le=20000)
    max_cost_microusd: int = Field(default=0, ge=0, le=10**8)
    cache_seconds: float = Field(default=5, ge=0, le=60)


class QuotaPolicy(ReviewModel):
    calls_per_minute: int = Field(default=30, ge=1, le=1000)
    token_reservations_per_minute: int = Field(default=100000, ge=1, le=10**7)
    cost_reservations_microusd_per_minute: int = Field(default=100000, ge=0, le=10**9)
    circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    circuit_cooldown_seconds: float = Field(default=30, ge=0.01, le=300)
