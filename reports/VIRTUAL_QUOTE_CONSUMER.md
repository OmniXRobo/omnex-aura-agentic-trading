# M5 persisted quote consumer — 0.5.1

Implemented a source-bound observation-only bridge from historical market events into the
virtual ledger. It pins source database identity, collector account fingerprint, feed,
symbol and immutable contract; checks event hashes, checkpoint continuity, reception and
heartbeat ages, normalized quote age, time-offset binding and stored correction policy.
Consumer schema marker 8 adds virtual bindings, cursors and append-only dispositions.
Source UUID/index initialization is additive. Operational account IDs are not emitted.

Stale/out-of-order backlog is recorded as gaps, never retrospectively simulated. Invalid
fresh evidence blocks without acknowledging it. A ledger receipt committed before a crash
allows cursor recovery without another transition. Same-ms changes and concurrent delivery
retain stable event receipt keys. No entry-intent path or automatic stop activation exists;
existing virtual positions may mark/exit. This is not a full autonomous virtual release.

Validation: 289 tests passed, zero failed; Ruff passed; real HTTP/restart/independent safety
CLI smoke passed; v0.5.1 source/wheel built. One preexisting Starlette/httpx deprecation
warning remains. CQ01–CQ19 fixture tests cover policy expiry/missing evidence, contract/
account/source mismatch, stale/future/reception/heartbeat gates, checkpoint rollback,
concurrent replay, crash-after-ledger/before-ack, same-ms quotes, existing-position exit,
isolated CLI and persisted-data observer CLI restart. Demo source in tests is emulated;
no actual MT5 connection or broker order was used.

The isolated `python -m aura.virtual_consumer_fixture` returned three applied events,
restart idle, no position, unchanged active stop, entries disabled and execution disabled.
It uses/removes a new temporary store and does not touch the operational data directory.
Owner VPS observation acceptance remains pending. Existing owner v0.5.0 fixture success
is recorded as synthetic behavior, not strategy profitability or real forward performance.

Remaining gates: accepted advancing VPS quotes with reviewed current timestamp evidence,
process supervision, complete source/stop fencing, strategy-intent automation, full order
lifecycle, calibrated costs, daily/weekly controls, durable 2/3-day evaluations and UI.
Feed/safety state and virtual commit are not one cross-database transaction. Data gaps can
hide missed stops and invalidate performance evidence. Do not claim lossless tick replay,
healthy live data from an idle response, or production deployment. See
 docs/VIRTUAL_QUOTE_CONSUMER.md for the exact limits and two-window VPS workflow.
Live-money trading stays inaccessible; no demo execution interface was introduced.
