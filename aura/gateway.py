"""Injectable async provider gateway. This checkpoint has no external API adapter."""

import asyncio
import hashlib
import json
import time
from typing import Protocol

from pydantic import ValidationError

from .gateway_store import GatewayStore
from .review_types import Binding, ProviderReply, QuotaPolicy, ReviewTask


class TransientProviderError(RuntimeError):
    pass


class ProviderPort(Protocol):
    async def review(self, task: ReviewTask, binding: Binding) -> dict: ...


class Gateway:
    def __init__(
        self,
        state: GatewayStore,
        adapters: dict[str, ProviderPort],
        policy=None,
        clock=None,
        concurrency=3,
    ):
        if not 1 <= concurrency <= 10:
            raise ValueError("Invalid gateway concurrency")
        self.state, self.adapters = state, adapters
        self.policy = policy or QuotaPolicy()
        self.clock = clock or time.time
        self.semaphore = asyncio.Semaphore(concurrency)

    def check_reply(self, raw, binding):
        reply = ProviderReply.model_validate(raw)
        if reply.provider != binding.provider or reply.model != binding.model:
            raise ValueError("provenance")
        usage = reply.usage
        if (
            usage.input_tokens > binding.max_input_tokens
            or usage.output_tokens > binding.max_output_tokens
            or usage.cost_microusd > binding.max_cost_microusd
        ):
            raise ValueError("usage_policy")
        return reply

    async def review(self, task: ReviewTask, route: list[Binding]):
        attempts = []
        for binding in route:
            if not binding.enabled:
                attempts.append({"provider": binding.provider, "code": "disabled"})
                continue
            adapter = self.adapters.get(binding.provider)
            if adapter is None:
                attempts.append({"provider": binding.provider, "code": "adapter_unavailable"})
                continue
            content = {
                "role": task.role,
                "context": task.context.model_dump(mode="json"),
                "binding": binding.model_dump(mode="json"),
            }
            serialized = json.dumps(content, sort_keys=True, allow_nan=False)
            key = hashlib.sha256(serialized.encode()).hexdigest()
            # Conservative byte bound is an estimate; external provider tokenizer validation is pending.
            input_estimate = len(task.context.model_dump_json().encode()) + len(task.role) + 64
            if input_estimate > binding.max_input_tokens:
                attempts.append({"provider": binding.provider, "code": "input_limit"})
                continue
            try:
                cached = self.state.cached(key, self.clock())
                if cached is not None:
                    reply = self.check_reply(cached, binding)
                    return {
                        "status": "completed",
                        "cached": True,
                        "attempts": attempts,
                        "reported_success_cost_microusd": 0,
                        "provider_billing_verified": False,
                        **reply.model_dump(mode="json"),
                    }
            except (ValidationError, ValueError, TypeError):
                # Corrupt cache entries cannot bypass the response schema or gain authority.
                pass
            except Exception:
                attempts.append({"provider": binding.provider, "code": "state_unavailable"})
                continue
            for attempt in range(binding.max_attempts):
                async with self.semaphore:
                    try:
                        identifier, gate = self.state.reserve(
                            task.task_id, binding, self.policy, input_estimate, self.clock()
                        )
                    except Exception:
                        attempts.append({"provider": binding.provider, "code": "state_unavailable"})
                        break
                    if gate:
                        attempts.append({"provider": binding.provider, "code": gate})
                        break
                    reply = None
                    retry = False
                    try:
                        raw = await asyncio.wait_for(
                            adapter.review(task.model_copy(deep=True), binding),
                            timeout=binding.timeout_seconds,
                        )
                        reply = self.check_reply(raw, binding)
                        error = None
                    except asyncio.CancelledError:
                        try:
                            self.state.finish(
                                identifier, binding.provider, self.policy, self.clock(), "cancelled"
                            )
                        except Exception:
                            pass
                        raise
                    except asyncio.TimeoutError:
                        error, retry = "timeout", True
                    except TransientProviderError:
                        error, retry = "transient", True
                    except ValidationError:
                        error = "invalid_schema"
                    except (ValueError, TypeError):
                        error = "invalid_reply"
                    except Exception:
                        error = "provider_error"
                    try:
                        self.state.finish(
                            identifier,
                            binding.provider,
                            self.policy,
                            self.clock(),
                            error,
                            None if reply is None else reply.usage.model_dump(),
                        )
                    except Exception:
                        attempts.append({"provider": binding.provider, "code": "state_unavailable"})
                        break
                    if reply is not None:
                        # Cache failure must not turn a validated completed attempt into a retry.
                        if binding.cache_seconds:
                            try:
                                self.state.save_cache(
                                    key,
                                    reply.model_dump(mode="json"),
                                    self.clock() + binding.cache_seconds,
                                )
                            except Exception:
                                pass
                        return {
                            "status": "completed",
                            "cached": False,
                            "attempts": attempts,
                            "reported_success_cost_microusd": reply.usage.cost_microusd,
                            "provider_billing_verified": False,
                            **reply.model_dump(mode="json"),
                        }
                    attempts.append({"provider": binding.provider, "code": error})
                if not retry:
                    break
                if attempt + 1 < binding.max_attempts:
                    await asyncio.sleep(0.01 * (attempt + 1))
        return {
            "status": "unavailable",
            "cached": False,
            "attempts": attempts,
            "reported_success_cost_microusd": None,
            "provider_billing_verified": False,
        }
