# M4 checkpoint — provider-neutral gateway and local review (0.4.0)

PR #4 is confirmed merged and all its Linux/Windows Python 3.11/3.12 checks/builds and
dependency audits passed. Actual Windows VPS/MT5 and external AI connections are unverified.

## Implemented

- `review_types.py`: bounded task, response, model binding, usage and quota contracts.
- `gateway_store.py`: durable minute quota reservations, circuit health, attempt records/cache.
- `gateway.py`: injectable async port, timeouts, transient retries, configured fallback,
  schema/provenance/usage validation, cancellation handling and in-process concurrency cap.
- `reviews.py`: 3 local deterministic perspectives; source/model honesty and fixed NO TRADE.
- `review.py` CLI, review fixture and authenticated API review/provider-status routes.
- Safe historical-only research records; no provider keys, network call or broker capability.
- Gateway guide, current roadmap, acceptance mapping and versioned source/wheel package.

## Verification

Local suite: 163 passed, 0 failed (132 existing + 31 gateway scenarios). One existing
Starlette TestClient deprecation warning. Ruff and real HTTP/restart/independent-stop smoke
passed. Source/wheel builds are checked before publishing. reports/junit.xml and
reports/smoke.json retain local evidence. This PR's remote CI must be checked separately.

## Limits and remaining gates

This is not completion of M4. OpenAI/Claude/Grok adapters and verified current model IDs
are not implemented; secure credential setup and real provider tests remain pending.
Only the local deterministic adapter runs by default; fake adapters test the port's
reliability. Three perspectives do not imply independent AI models. Billing is unverified;
minute quota reservations and adapter-reported successful cost are not actual invoice
reconciliation. Timeouts are cooperative; no hard process isolation/distributed single-
flight/concurrency or daily/monthly provider budget is provided. Historical tables remain
local SQLite, not the final production PostgreSQL/identity/deployment stack.

All 15 specialist roles, licensed macro/news sources, adaptive learning, continuous virtual
trading, model promotion, demo execution, dashboard, APK and production VPS recovery remain
unfinished. Current gateway cannot authorize execution, even if all reviews agree. No
broker order API exists. Promotion and live-money execution always remain disabled.

## Next

Review this gateway checkpoint, then complete official provider adapters and secure key/
model-access setup with bounded real API tests. Continue read-only MT5 acceptance on the
Windows VPS separately. Do not enable any broker order or strategy-promotion operation.
