# Research registry continuation — 0.7.0

Adds immutable XAUUSD strategy descriptions/versions and parent lineage in historical
memory, digest-pinned historical backtest/validation references, append-only review
requests/suspensions/archive, optimistic revisions, idempotent operation IDs and atomic
audit writes. Includes administrator write/viewer read API, local CLI, isolated fixture
and read-only Strategy laboratory dashboard projection.

Validation: 348 tests passed, zero failed/skipped (17 new registry cases). Ruff,
JavaScript syntax and whitespace checks passed. Wheel/source distribution builds passed.
The isolated CLI fixture reported two versions, identical creation replay, suspended
parent/draft child, active emergency stop and no existing-data modification. Tests cover
actual subprocess CLI startup, concurrent revision races, SQLite append-only protection,
audit rollback, evidence mutation, role authorization and bounded history. One existing
Starlette/httpx TestClient deprecation warning remains.

No dependency changes, external API requests, actual VPS process changes or broker calls.
No automatic strategy creation or deployment is enabled. Historical evidence references
verify exact record integrity only, not semantic strategy agreement, profitability or
OOS validity; review_requested never means approved. No champion selection, virtual
shadow execution, automatic self-healing, promotion or live authority exists here.

Windows fixture/browser acceptance and actual market/source acceptance remain pending.
External AI, collector supervision, backups, complete virtual lifecycle, demo execution,
Android and production release gates remain on the roadmap. Live-money trading is disabled.
