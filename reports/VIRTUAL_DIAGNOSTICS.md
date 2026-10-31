# Virtual learning review continuation — 0.8.0

Adds deterministic saved-evaluation triage with immutable virtual reports, pinned policy,
source-payload digests, transactional bounded cursor/audit, restart-safe/concurrent batches,
runner polling with three-failure blocking, local/API entry points and read-only Learning
Review page. Backup compatibility now accepts and preserves schema 10 diagnostics.

Validation: 379 tests passed, zero failed/skipped (17 new diagnostic cases). Ruff,
JavaScript syntax and whitespace checks passed; source/wheel builds passed. Tests exercise
real evaluator fixtures, restart/idempotency, bounded concurrent batches, negative P/L
review without causal claims, malformed/prohibited input, append-only storage, digest
checks, batch rollback, runner failure redaction/blocking, authorization/dashboard data,
CLI subprocess startup and backup/restore persistence. Isolated fixture created three
synthetic diagnostics, replay created zero, and emergency stop remained active. One
existing Starlette/httpx TestClient deprecation warning remains.

Diagnostics do not modify strategies, risk, source evidence, approvals or positions.
They do not establish causal loss explanations, statistical drift, regime attribution,
validated profitability or semantic strategy/evidence agreement. Overlapping windows are
not independent samples. No provider/broker calls or VPS changes were made. Browser and
actual Windows diagnostic acceptance remain pending. Full self-healing, challenger
experiments, fresh OOS/shadow validation, external AI, automatic virtual entries, demo
orders, Android and production acceptance remain incomplete. Live-money trading is disabled.
