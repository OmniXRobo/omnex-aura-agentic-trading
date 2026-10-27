"""Independent research perspectives through the gateway, always NO TRADE."""

import asyncio
import uuid

from .gateway import Gateway
from .gateway_store import GatewayStore
from .review_types import REVIEW_ROLES, Binding, ReviewContext, ReviewTask
from .store import Store


class LocalReviewAdapter:
    """Explicit deterministic fallback; this is not a language model."""

    async def review(self, task, binding):
        if binding.provider != "local" or binding.model != "local-deterministic-v1":
            raise ValueError("The local adapter cannot impersonate an external provider/model")
        snapshot = task.context.snapshot
        count = len(snapshot.prices)
        if task.role == "technical_interpreter":
            summary = "Descriptive sample change; no validated predictive model"
            evidence = [
                f"Sample count: {count}",
                f"First-to-last change: {snapshot.prices[-1] - snapshot.prices[0]:.6f}",
            ]
        elif task.role == "strategy_critic":
            summary = "Hypothesis requires independent strategy and out-of-sample evidence"
            evidence = [
                "No strategy validation artifact is supplied to this review",
                "Language-model agreement cannot establish a trading edge",
            ]
        else:
            summary = "Source and freshness claims are not independently broker-verified"
            evidence = [
                f"Supplied source label: {snapshot.source}",
                f"Supplied tick age seconds: {snapshot.tick_age_seconds}",
            ]
        return {
            "provider": binding.provider,
            "model": binding.model,
            "model_version": "local-review-v1",
            "usage": {"input_tokens": 0, "output_tokens": 0, "cost_microusd": 0},
            "review": {
                "verdict": "INSUFFICIENT_EVIDENCE",
                "summary": summary,
                "evidence": evidence,
                "limitations": [
                    "Deterministic local adapter, not AI inference",
                    "No broker, research promotion or execution authority",
                ],
            },
        }


def default_gateway(store):
    return Gateway(GatewayStore(store), {"local": LocalReviewAdapter()})


def default_routes():
    return {
        role: [Binding(provider="local", model="local-deterministic-v1")] for role in REVIEW_ROLES
    }


class ReviewCoordinator:
    def __init__(self, store: Store, gateway: Gateway, routes=None):
        self.store, self.gateway = store, gateway
        self.routes = default_routes() if routes is None else routes

    async def run(self, context: ReviewContext):
        run_id = str(uuid.uuid4())

        async def run_role(role):
            task = ReviewTask(
                task_id=run_id + ":" + str(REVIEW_ROLES.index(role)),
                role=role,
                context=context.model_copy(deep=True),
            )
            try:
                return await self.gateway.review(task, self.routes.get(role, []))
            except Exception:
                return {"status": "unavailable", "attempts": [{"code": "review_failed"}]}

        outcomes = await asyncio.gather(*(run_role(role) for role in REVIEW_ROLES))
        results = [{"role": role, **result} for role, result in zip(REVIEW_ROLES, outcomes)]
        providers = {r["provider"] for r in results if r["status"] == "completed"}
        report = {
            "run_id": run_id,
            "mode": "research_review_only",
            "signal": "NO TRADE",
            "execution_allowed": False,
            "promotion_eligible": False,
            "source": context.snapshot.source,
            "reviews": results,
            "provider_count": len(providers),
            "provider_independence_verified": False,
            "reason": "Review opinions do not replace validated strategies or deterministic risk gates",
        }
        record_id = self.store.record(
            "historical",
            "research_review",
            {"context": context.model_dump(mode="json"), "result": report},
        )
        self.store.audit(
            "review_coordinator", "review.completed", {"record_id": record_id, "run_id": run_id}
        )
        return {"record_id": record_id, **report}

    def statuses(self):
        health = {row["provider"]: row for row in self.gateway.state.health()}
        return {
            "external_calls_enabled": False,
            "providers": [
                {
                    "provider": "local",
                    "implementation": "deterministic_local",
                    "health": health.get("local"),
                },
                *[
                    {"provider": name, "implementation": "not_implemented", "enabled": False}
                    for name in ("openai", "anthropic", "xai")
                ],
            ],
            "role_routes": {
                role: [binding.model_dump() for binding in route]
                for role, route in self.routes.items()
            },
        }
