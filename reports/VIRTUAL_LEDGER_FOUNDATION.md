# M5 virtual ledger foundation — 0.5.0

Implemented persistent single-instrument virtual sessions with immutable contract/cost/risk/
source configuration, decimal USD cash/equity accounting, bid/ask market fills, explicit
commission/slippage/approximate UTC rollover debits, sampled-quote SL/TP, one-position
protection, entry freshness/news/stop/spread/volume/planned-risk gates and a durable
liquidation-equity drawdown halt. Position state, intent consumption, receipts and audit
events commit atomically in virtual.db; concurrent/after-restart exact retries cannot refill.

Validation: 268 tests passed, zero failed; Ruff passed; HTTP/restart/independent safety CLI
smoke passed; v0.5.0 source and wheel built. One preexisting Starlette/httpx deprecation
warning remains. V01–V18 tests include long/short cost accounting, adverse gaps, duplicate
keys/signals, concurrent delivery, rolled-back writes, stop failures, expiry, append-only
evidence and isolated fixture CLI behavior. The fixture uses a new temporary store and
never arms/modifies the operational VPS stop. Its synthetic net P/L of 9.4600 is an
accounting assertion, not performance evidence.

No actual MT5 current-quote consumer is wired; no live provider calls, strategy automation,
HTTP exposure, continuous worker, two-/three-day scheduler, broker order interface or
production deployment is introduced. Costs/session/calendar/margin/partial/trailing orders
are incomplete. The global stop read and virtual DB commit are not a multi-database atomic
fencing protocol; see docs/VIRTUAL_LEDGER.md. Do not claim completed virtual autopilot.

The owner's VPS screenshots confirm four historical M1 candles and successful duplicate
replay in the reviewed interval. Broader history and current quote acceptance remain
pending. No screenshot/account data or operational databases are committed. Next owner
check after PR review/merge: update code and run `python -m aura.virtual_fixture`, then
continue the fresh-quote integration and durable consumer milestone. Live-money trading
remains disabled and inaccessible.
