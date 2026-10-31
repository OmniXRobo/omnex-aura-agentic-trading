# M5 rolling diagnostic scheduler — 0.5.2

Added immutable evaluation plans for existing virtual sessions, overlapping two-/three-day
UTC lookbacks with daily stride by default, a settlement grace, foreground watch polling,
bounded evidence indexing and catch-up, and atomic report/due-cursor advancement. Immutable
reports freeze their input high-water mark and event digest. Late evidence is separately
audited rather than silently rewriting checkpoints. Clock regressions and missing/changed
evidence checkpoints block. Schema marker 9 is virtual-only.

Reports include closed-trade counts/wins/losses/net P/L/expectancy/profit factor, commissions,
approximate swap debits, strategy-version subtotals, marked equity/drawdown and evidence
quality flags. Empty/sparse/closed-market periods never create trades. Source gap counts
are conservatively cumulative because existing dispositions lack per-window timestamps.
Overlapping reports are not independent and must not be summed. Closed-trade accounting
and marked-equity change are distinct measures. All reports remain diagnostic; there is
no profitability pass, maturity activation, strategy promotion or automatic healing.

Validation: 311 tests passed, zero failed; Ruff passed; real HTTP/restart/independent safety
CLI smoke passed; v0.5.2 source distribution and wheel built. One preexisting Starlette/
httpx deprecation warning remains. EV01–EV16 cover due/grace/half-open boundaries, rolling
windows, costs, restart/concurrent dedupe, rollback, empty/sparse evidence, bounded work,
clock regression, immutable plans/reports, late evidence, source gaps, checkpoint integrity
and isolated fixture/CLI output. A formatting-only assertion was corrected to compare
commission Decimal values rather than require insignificant trailing zeroes.

The isolated logical-clock fixture created three reports for two window lengths, zero early
or duplicate restart reports, with all reports diagnostic, active stop and no operational
data modification. It is NOT a real three-day performance trial. No broker or external AI
API was called, and no Windows service/background task was installed. No runtime strategy,
entry, risk control or broker execution interface was modified. All promotion/entry/execution
flags remain false.

PR #11 was verified merged before this work. Its owner-reported VPS fixture success does not
complete actual source observation; the user reported market closure and ticks were not
advancing. Current time correction must be reviewed again once quoting resumes. Actual fresh
source observation, an uninterrupted supervised 48/72-hour run, process monitoring/recovery,
strategy decisions and approved challenger validation remain pending. See
 docs/VIRTUAL_EVALUATION.md for exact fixture and future operational commands.
