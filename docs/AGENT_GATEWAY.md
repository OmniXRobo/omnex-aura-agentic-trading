# M4 gateway and review workflow checkpoint (0.4.0)

This is a provider-independent reliability foundation with an EXPLICIT deterministic
local adapter. It does not call OpenAI, Claude, Grok or any other external API. It is
not completion of the multi-LLM milestone and does not implement an adaptive trading
policy. The existing VPS backend architecture is preserved; no hosted session/sandbox
or provider SDK is provisioned. All prior broker and promotion restrictions remain.

## Run locally

```bash
python -m aura.review --request examples/review_fixture.json --data-dir ./data
```

On Windows use `.\.venv\Scripts\python.exe`. No provider or broker keys are required.
The fixture is a labelled synthetic three-price sample; it is not current market data.
The command runs three tasks and stores the context and research report in historical
memory. It does not create virtual/demo trades. Do not place credentials in request text.

API routes use the existing admin/viewer bootstrap authorization:

| Route | Authorization | Effect |
| --- | --- | --- |
| POST /v1/research/review | Admin | Run and store the review-only workflow |
| GET /v1/providers/status | Admin or viewer | Read local health and declared routes |

Clients cannot select adapters, configure models, enable remote providers or change
policy through these request bodies. Configuration fields beyond the review context
are rejected. The original /v1/status continues to report external AI as not_configured.
OpenAI/Anthropic/xAI explicitly show not_implemented/disabled in the provider status.

## What actually runs

- Technical interpreter: descriptive sample count and first-to-last change.
- Strategy critic: identifies the absence of independent strategy/validation evidence.
- Evidence auditor: labels source/freshness as supplied rather than broker-verified.

These are three async research tasks using ONE deterministic local provider, not three
LLMs or independent AI models. Every local response is INSUFFICIENT_EVIDENCE. The report
always says NO TRADE, promotion_eligible=false and execution_allowed=false. Provider
count is reported and provider_independence_verified remains false. The local adapter
refuses to impersonate any other provider or model identifier.

## Provider port and response schema

A reviewed server-side adapter may implement the async ProviderPort.review method.
It receives a typed role/context and binding; it returns a structured ProviderReply.
The gateway validates provider/model identity, version metadata, usage bounds and a
bounded ReviewEvidence object. Only REVIEW_ONLY, INSUFFICIENT_EVIDENCE and
REJECT_HYPOTHESIS verdicts are allowed. Execution/promotion flags must be false; unknown
fields (including tools/orders/commands) are rejected. Text is data, never executable
instructions. No tool registry, shell execution, module loading or broker client is
available through this port.

Bindings configure server-owned model identifiers, enable state, deadlines, bounded
attempts, output/input limits, declared cost caps and cache TTL. The actual local model
identifier is local-deterministic-v1; no speculative external model IDs are hardcoded.
Future real model IDs must be verified against official provider documentation/listing
APIs and project access before their adapters are activated. No real API key is read,
created, stored or transmitted by this checkpoint. Secure credentials remain pending.

## Reliability controls

- Retry only explicitly transient errors/timeouts, with at most 3 attempts and small
  bounded backoff. Invalid schema/provenance/usage and generic errors are not retried
  on the same provider; declared fallback routes may still be attempted.
- A shared in-process semaphore limits concurrent adapter calls. It is not a distributed
  concurrency limiter; provider quotas are the cross-worker durable constraint.
- SQLite write transactions reserve per-provider call, token and cost capacity in UTC
  wall-clock minute buckets BEFORE each attempt. Restarting does not reset the counters.
- Circuit failure counts/open-until state persist across restarts. Cache reads may serve
  a still-valid prior review during an open circuit; the circuit gates NEW calls only.
- Each attempt has a durable started/completed/failed record. Cancellation records a
  generic cancelled state and retains its quota reservation. A process crash can leave
  started records for future reconciliation; they are not claimed completed or billed.
- Errors use sanitized categorical codes. Raw provider exceptions/responses are not
  written to attempt logs. Source request/validated review content is kept only in the
  local historical research record with normal access controls.
- Short-lived cache keys include role, full context and binding/model configuration.
  Task IDs are excluded so identical evidence can reuse a review. Default TTL is five
  seconds. Corrupt cache data is schema-checked and cannot gain execution authority.
  A cache write failure never repeats a successfully completed call.
- Per-attempt deep copies keep one adapter from mutating another role/fallback context.
- Database/quota/health failures prevent starting a new provider call. Failure to record
  a completed attempt does not blindly retry that provider.

Deadlines depend on cooperative async cancellation. A hostile/native adapter can ignore
cancellation; hard process isolation and supervisor termination are not implemented.
Adapters must be trusted reviewed code, never dynamically downloaded research scripts.
There is no distributed single-flight request deduplication or exactly-once billing.
Model fallback agreement is never treated as validated market evidence.

## Usage and cost accounting limits

A token estimate based on context UTF-8 byte count plus a small envelope reserve bounds
this local fixture workflow. It is NOT a verified tokenizer or a complete external API
prompt accounting method. A real adapter must include system prompts/serialization and
provider-specific tokenization, authoritative pricing and project-access checks.

Calls reserve the declared worst-case input/output token capacity and maximum declared
cost per attempt. Reservations remain consumed until the minute ends, including failures;
they are deliberately not refunded using unverified or missing usage. These are quota
reservations, not accounting entries proving charges. Reply usage is adapter-reported.
A schema/usage violation after a hypothetical external call cannot undo a charge.

reported_success_cost_microusd describes only the validated successful response (zero
for a cache hit); it does not include unknown charges from prior failed/timed-out attempts.
A fully unsuccessful route reports this value as null. provider_billing_verified is always
false. No paid API is actually connected, and local adapter token usage/cost is zero.
Provider invoice reconciliation, cumulative daily/monthly budgets, distributed concurrency
and real rate-limit headers remain future work before actual provider activation.

## Persistence and tests

Historical component schema marker 4 adds provider_quota, provider_health,
provider_attempts and review_cache. Existing records/holdout protection are preserved.
No automatic deletion is added to permanent research memory; cache expiration only
prevents reuse of stale cache entries. SQLite is still a local prototype, not production
PostgreSQL or an immutable external audit service. Failed/cache records can accumulate;
add an explicit operational maintenance policy before long-running use.

Tests G01..G24 in tests/test_gateway.py cover 31 scenarios: valid schemas/provenance,
timeouts/retries/failover, authority injection, pre-call quotas, atomic reservation,
restart-persistent circuits/cache, usage limits, safe error logging, context isolation,
cancellation, no-trade coordinator behavior, route ownership/auth, database/cache failures,
local-model honesty, CLI execution, bounded concurrency and uncertain-cost reporting.
All provider reliability tests use local or fake ports; none verifies a real provider.

## Remaining M4 and deployment gates

Official OpenAI/Anthropic/xAI adapters, secure keys, verified current model discovery,
real token/cost reconciliation, API-access smoke tests and multi-provider independence
remain pending. All 15 specialist roles are not implemented; current local agents and
these review tasks are foundation components. There is no autonomous model learning,
continuous virtual scheduler, strategy promotion, Android app or production VPS service
in this checkpoint. Real Windows MT5 acceptance remains pending too. No brokerage order
placement/amendment/close function exists and live-money trading cannot be enabled.
