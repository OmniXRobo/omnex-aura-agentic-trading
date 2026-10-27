"""Independent local analysis tasks; no LLM inference or trade capability."""

import asyncio
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .risk import Proposal, RiskController
from .store import Store

AGENT_ROLES = (
    "chief_autopilot",
    "technical_analysis",
    "market_structure",
    "machine_learning",
    "fundamental_macro",
    "news_social",
    "order_flow",
    "market_regime",
    "strategy_selection",
    "risk_controller",
    "virtual_trader",
    "performance_auditor",
    "self_healing",
    "technology_research",
    "security_reliability",
)


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    symbol: str = "XAUUSD"
    prices: list[float] = Field(min_length=3, max_length=5000)
    tick_age_seconds: float = Field(ge=0)
    source: Literal["fixture", "manual"] = "manual"


@dataclass(frozen=True)
class AgentResult:
    agent: str
    status: str
    evidence: dict


async def technical(snapshot):
    first, last = snapshot.prices[0], snapshot.prices[-1]
    return AgentResult(
        "technical_analysis",
        "completed",
        {"price_change": last - first, "sample_count": len(snapshot.prices)},
    )


async def regime(snapshot):
    changes = [b - a for a, b in zip(snapshot.prices, snapshot.prices[1:])]
    label = (
        "directional_sample"
        if all(x > 0 for x in changes) or all(x < 0 for x in changes)
        else "mixed_sample"
    )
    return AgentResult(
        "market_regime", "completed", {"sample_label": label, "validated_classifier": False}
    )


async def data_quality(snapshot):
    valid = all(p > 0 for p in snapshot.prices) and snapshot.tick_age_seconds <= 5
    return AgentResult(
        "security_reliability",
        "completed",
        {"data_usable": valid, "source": snapshot.source, "broker_verified": False},
    )


class Orchestrator:
    def __init__(self, store: Store):
        self.store = store

    async def run(self, snapshot: Snapshot):
        results = await asyncio.gather(
            technical(snapshot), regime(snapshot), data_quality(snapshot), return_exceptions=True
        )
        evidence = []
        for role, result in zip(
            ("technical_analysis", "market_regime", "security_reliability"), results
        ):
            if isinstance(result, Exception):
                evidence.append({"agent": role, "status": "failed", "evidence": {}})
            else:
                evidence.append(vars(result))
        report = {
            "signal": "NO TRADE",
            "reason": "Research foundation; no validated strategy",
            "execution_allowed": False,
            "provider": "local_deterministic",
            "agents": evidence,
            "source": snapshot.source,
        }
        identifier = self.store.record("historical", "agent_run", report)
        self.store.audit("orchestrator", "research.completed", {"record_id": identifier})
        return {"id": identifier, **report}

    def preview(self, proposal: Proposal):
        return RiskController(self.store).evaluate(proposal)
