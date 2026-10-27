# M2 — read-only market data checkpoint (0.2.0)

PR #1 is confirmed merged. Its Linux/Windows Python 3.11/3.12 tests/build jobs and
dependency-audit jobs all passed on GitHub. Repository visibility is public as explicitly
requested by the owner. Production database/auth and actual VPS recovery are still pending.

## Implemented

- `aura/market.py`: typed feed identity, gold contract, bid/ask quote and closed-candle models.
- `aura/market_store.py`: additive historical schema v2, feed/account fingerprint binding,
  append-only event triggers, exact deduplication, immutable candle corrections, heartbeat.
- `aura/collector.py`: verified demo account/server checks around reads; currency-based
  gold discovery, contract validation, fresh snapshot polling, UTC paginated candle history.
- `aura/collect.py`: Windows read-only CLI for discovery, one-shot/watch collection and
  history imports using an already signed-in account. No passwords/login/order API calls.
- `aura/api.py`: authenticated feed-status and market-event read endpoints.
- `tests/test_market_data.py`: 21 named test cases, parameterized to 36 M2 scenarios.
- Updated README, roadmap, acceptance mapping and env template. Added the Windows setup guide.

## Validation

Local suite: 76 passed, 0 failed (40 foundation + 36 market data), one existing TestClient
deprecation warning. Ruff passed for backend/tests/scripts. The real backend HTTP/restart
smoke and package build are checked before publishing this branch. Machine-readable
results are in reports/junit.xml and reports/smoke.json. The earlier syntax/formatting
errors during implementation were corrected before this final suite passed.

M2 remote CI status must be read from its PR; only PR #1 CI is confirmed passed at the
time this report was prepared. No actual Windows MT5/broker connection is claimed.

## Limitations and safety

Quotes are sampled snapshots, not a lossless tick archive. History completeness stays
unverified; potential gaps are not session-aware. D1 boundaries need broker/session
validation. Commission, currency conversion and trading sessions are not yet supplied.
Quote records can become stale after storage; the API provides event timestamps and feed
heartbeat freshness, not an execution authorization. Feed names are operator labels;
account/server binding is independently checked. Fingerprints/DBs stay local and out of Git.

Collection retries guarded reads in watch mode; native terminal reinitialization and
Windows supervised restart remain pending. These fixtures are not Exness/Equiti/MultiBank
runtime certification. The CLI fails on non-Windows for real terminal access.

No broker order submission, stop amendment, position close or live-money execution is
implemented. Clearing the kill switch cannot enable them. Market collection is allowed
while stopped because it is read-only. No real credentials are needed for local fixtures.

## Next step

Run docs/MT5_READ_ONLY_SETUP.md on the Windows VPS with a chosen demo account and exact
terminal path. Verify symbols/metadata/timestamps against the terminal and test loss of
connection before claiming M2 broker acceptance. Keep demo order submission disabled.
Continue M3 research using explicitly labelled fixture data until broker data quality and
cost assumptions are independently validated.
