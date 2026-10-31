# Durable rolling virtual evaluation — 0.5.2

This local evaluator reads the virtual ledger and produces immutable diagnostic reports.
It never changes a position, global stop, strategy, risk limit, provider route or entry
setting. Report `promotion_allowed`, `entries_enabled` and `execution_allowed` are always
false. A profitable checkpoint cannot activate trading. This is not a self-healing or
strategy-promotion release.

## Time semantics and restart

One immutable plan belongs to one existing virtual session. The default plan creates two
lookback lengths, 2 and 3 days, advancing each endpoint by 1 day. The first two-day report
is due after 48 hours plus grace; at 72 hours plus grace the next two-day report and first
three-day report are due. Windows are [start,end), so an event exactly at end belongs to
a later window. These OVERLAPPING reports are not independent experiments and must not be
added as portfolio returns. The daily stride is configurable from 1 to 3 days.

A day is exactly 86,400,000 UTC milliseconds, not a trading day, broker session, Dubai day
or guarantee of 24 hours of usable prices. Weekend/session closure remains visible as
missing/sparse observation; it never generates synthetic trades. No broker calendar is
integrated. The local Windows system epoch clock controls due times. Moving it backwards
blocks evaluation until the persisted watermark is reached again; no timezone service is
added. Grace is 60 seconds by default (5–3600 configurable) to allow normal input latency.

SQLite immediate transactions serialize competing evaluators. Each successful batch commits
reports, due-endpoint advancement, evidence indexing and clock watermark together. A failed
batch rolls back. Restart at the same checkpoint does not duplicate reports. Catch-up is
bounded to 10 reports per poll by default. A first/backlog index processes up to 1000 input
events per call; while still indexing no reports are published. Next calls continue without
restarting the scan. Missing/changed index checkpoints block, rather than hiding lost evidence.

The index records immutable ledger event IDs, quote times and payload hashes; reading a
report verifies the stored input-evidence digest and indexed payload hashes. Each report
freezes the high-water event ID, evaluation time and window evidence digest. A late ledger
event in an already reported interval is separately recorded. Old reports are NEVER rewritten;
new reports and run summaries flag late evidence. Source gap dispositions currently lack
window timestamps, so skipped source events are counted conservatively as cumulative session
gaps, not misrepresented as precisely dated coverage. Source and evaluator are local trusted
components; these checks are not tamper-proof cryptographic attestation of broker prices.

## Report interpretation

Reports include closed trade count, wins/losses/flat trades, net P/L, expectancy and profit
factor, plus closed-trade commission and approximate swap debit totals. Trades belong to
the window in which they CLOSED: net P/L/costs include their entire lifetime even if entry
preceded the window. Each strategy version also has a separate trade count/net subtotal;
mixed-version aggregate reports are flagged and are not a clean strategy comparison.

Opening equity is the latest ledger mark strictly before window start, or initial cash if
none exists. Ending equity carries the last available mark. Equity change and marked-equity
drawdown are separate from closed-trade P/L: unrealized positions and entry costs can make
them differ. Missing prices can hide worse drawdowns; no continuous price-path inference
is made. Position boundary crossings and nonpositive opening equity are flagged. Profit
factor is null/undefined when there are no losses, never an invented infinity; empty sample
win rate/expectancy are null. Decimal accounting values are emitted as strings.

Minimum closed trades defaults to 20, configurable. This is a DIAGNOSTIC sample flag, not a
statistically justified proof threshold. Reports flag no observations, insufficient sample,
sparse/closed-market observation (gaps over one minute), cumulative source gaps, late evidence
and mixed versions. Market-session coverage remains explicitly unverified in every report.
Negative net trade outcomes request review only; they do not modify or suspend a strategy.
No confidence calibration, independence test, promotion eligibility, daily/weekly risk update
or automated improvement/backtest loop is implemented.

## Isolated Windows check after review/merge

```powershell
cd C:\OMNEX-AURA
git switch main
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m aura.virtual_evaluation_fixture
```

Expected: reports_before_due 0, reports_created 3, window_lengths [2,3], restart_new_reports 0,
all_reports_diagnostic true, emergency_stop_active true, existing_data_modified false,
promotion_allowed false, entries_enabled false and execution_allowed false. The fixture
advances a LOGICAL clock; it is not a real three-day trial. Its one synthetic trade happens
only in a NEW temporary store which is removed afterwards; operational VPS data/controls
are untouched. No MT5 or API keys are required and no multi-day wait occurs.

## Actual persisted session (later acceptance gate)

Do this only after the actual observation session has been created through the validated
quote consumer described in VIRTUAL_QUOTE_CONSUMER.md. Temporary fixture sessions do not
exist in the operational DB. The evaluator intentionally refuses an unknown session.

Choose the actual observation trial start; do not backdate it to imply elapsed market
coverage. For a new trial starting now, create a local plan:

```powershell
@{
  session = 'equiti-observer-1'
  anchor_msc = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
  windows_days = @(2,3)
  stride_days = 1
  grace_seconds = 60
  min_closed_trades = 20
} | ConvertTo-Json | Set-Content -Encoding ASCII data\equiti-evaluation.json

.\.venv\Scripts\python.exe -m aura.evaluate_virtual --data-dir data --plan data\equiti-evaluation.json --watch
```

Keep that SAME plan file after restart. Regenerating its anchor or changing thresholds is
rejected for the session; review a separate experimental session instead of overwriting
learning evidence. Default --watch polling is every 30 seconds and checks only while this
process runs. Ctrl+C stops it; rerun the identical command to catch up. No Windows service,
Task Scheduler entry or reboot auto-start is installed. Do not claim background operation
when the command is closed. Source consumption and strategy entry are separate processes;
the evaluator does not run either of them. Observation-only sessions normally have no trades.

Run once without --watch to check due work. Saved reports can be listed with:

```powershell
.\.venv\Scripts\python.exe -m aura.evaluate_virtual --data-dir data --plan data\equiti-evaluation.json --list
```

This returns the most recent 20 saved reports in chronological order. The engine retains
all reports; the API limit is not a retention policy. Back up the entire virtual DB/WAL
consistently, including plan/cursor/index tables. Schema marker 9 is virtual-only. Existing
historical/demo memories and virtual ledger accounting are preserved.

Actual source observation, a real 48/72-hour supervised run, production recovery/monitoring,
strategy automation, session calendars and approved challenger validation remain pending.
Live-money trading remains disabled and no demo order interface is introduced.
