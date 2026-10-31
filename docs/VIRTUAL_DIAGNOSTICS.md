# Virtual learning review — 0.8.0

This milestone adds deterministic triage of existing immutable two-/three-day virtual
evaluation reports. It is the evidence-review part of self-healing, not automatic
strategy improvement, causal diagnosis, statistical drift testing or promotion.
No strategy specifications, positions, risk settings, source reports or approval states
are changed. No broker/AI provider calls occur.

## Windows update and acceptance

Stop the dashboard and operations runner in their own PowerShell windows with Ctrl+C.
After reviewing and merging the PR:

```powershell
cd C:\OMNEX-AURA
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m aura.diagnostic_fixture
```

Expected fixture output: diagnostics_created 3, replay_new_diagnostics 0, all_synthetic
true, all_review_only true, emergency_stop_active true and execution_allowed false.
It creates temporary synthetic quotes and real evaluator reports, then triages them.
The temporary data is deleted; operational data is neither populated nor modified.

Restart the dashboard and the separate operations runner using the same data directory:

```powershell
.\.venv\Scripts\python.exe -m aura.dashboard --data-dir C:\OMNEX-AURA\data --open-browser
```

In another PowerShell window:

```powershell
cd C:\OMNEX-AURA
.\.venv\Scripts\python.exe -m aura.operations --data-dir C:\OMNEX-AURA\data
```

Connect with the locally printed dashboard token and open **Learning review**. The
operations runner now processes up to ten newly saved evaluations per cycle, after its
configured evaluators run. If no virtual evaluation reports exist, the page stays empty.
It does not create trades, sessions or evaluation plans. Configuring the actual collector,
consumer and evaluator remains a separate requirement; weekend stale quotes are not new
evidence. Earlier fixture outputs are not operational forward-performance results.

For a single bounded manual batch, use `python -m aura.diagnose_virtual --data-dir ...`.
Add `--list` to read latest saved diagnostics instead. Repeat batches for larger backlogs.
Authenticated viewers may GET `/v1/virtual/diagnostics?limit=20` (1–100). Administrators
may POST `/v1/virtual/diagnostics/run` for one bounded ten-report batch. The dashboard is
read-only for diagnostics. All paths refer to the installed project's local CLI.

## Findings and limitations

Supported findings include synthetic evidence, nonpositive opening equity, no observations,
insufficient closed trades, source gaps, late evidence, mixed strategy versions, sparse
or closed-market observations, positions crossing window boundaries, negative net closed
P/L and recorded commission/swap costs. Unknown source quality flags produce a compatibility
review finding. Financial/count/window inconsistencies reject the batch instead of being
interpreted as strategy evidence.

Findings describe observable evidence and propose research checks. A loss does not prove
bad timing, news effects, overfitting or a regime change. Commission/swap debits do not
by themselves establish why a strategy lost. Spread/slippage are not decomposed by these
summary reports. Market session calendars, regime attribution and semantic strategy-to-
evidence matching remain unverified. No validated profitability or confidence score is
reported, and positive P/L does not authorize promotion.

Two-/three-day windows overlap: do not sum results, treat them as independent samples,
or infer drift by comparing them naively. Diagnostic policy is pinned to
`virtual-triage-v1`. Future interpretation changes require an explicit migration/version
review; existing records are not silently rewritten.

## Persistence and failure handling

Reports and their source cursor are stored together in virtual.db (schema 10). Per-batch
transactions bind diagnostic rows to exact source payload SHA-256 and their SQL identity,
advance the cursor, and append virtual audit events atomically. Batches are bounded,
concurrent runs serialize through SQLite, and restarts do not duplicate reports. The
cursor is an insertion-order high-water mark, not an evaluation time or performance rank.
Reads verify the original hash and deterministic interpretation. These checks do not
authenticate evidence against a local administrator who can replace databases/triggers.

A malformed report rolls the whole batch back. The runner retries at most three consecutive
diagnostic failures, then marks that task blocked until operator review/restart while
other research/evaluation tasks can continue. Failure messages contain no raw private
exception text. Missing safety state blocks processing. The diagnostic task runs while
the emergency stop is ON and never clears it. A manual run may retry a blocked source;
it cannot override validation or skip the offending evidence. No repair/deletion bypass
is provided. The updated backup module supports schema 10 and preserves diagnostic state
on an isolated emergency-stopped restore.

Windows fixture acceptance, Learning Review browser interactions and actual forward-market
evidence remain pending. Full self-healing still needs causally justified hypotheses,
reproducible isolated challengers, fresh OOS validation, shadow trials and reviewed
promotion/rollback. External AI, automatic virtual entries, demo orders and Android are
not completed here. Live-money trading remains disabled.
