# Persisted quote-to-virtual consumer — 0.5.1

The consumer bridges the read-only collector's historical market events to the separate
virtual ledger. This release OBSERVES quotes and can mark/close an existing virtual position.
It has no entry-intent input, MT5 import, provider call or broker execution interface.
The CLI never changes the global stop. It is not an autonomous virtual strategy release.

A virtual session is pinned to the source database's generated UUID, feed key, account
fingerprint, exact symbol and immutable ledger contract. The expected login/server must
match the collector's saved account binding. Login numbers are never emitted or copied
into the virtual binding (only a fingerprint is retained). A different source/contract or
preexisting unbound ledger history requires investigation; it cannot silently rebind.
These are local integrity controls, not cryptographic proof of account type. The trusted
collector must still perform its demo-account checks before every terminal read/write.

Quotes are read in insertion order with a durable cursor, preserving different quotes at
the same millisecond. Source event hashes and checkpoint identity are checked. A missing
or changed checkpoint (for example after restoring an older source DB) blocks progress.
Fresh unapplied quotes require a healthy feed heartbeat within 15 seconds, receipt age
within five seconds, a matching preceding/current contract and a bound time interpretation.
Corrected quotes require saved policy hash/content, scope and validity at both receipt and
processing time. Quote freshness remains five seconds. Contract changes block, rather than
changing the position's USD sizing assumptions underneath it.

Old backlog is recorded as skipped_stale_gap, never retroactively filled. Fresh out-of-order
quotes are recorded as skipped_out_of_order_gap. Neither advances the ledger's price history;
audit dispositions persist in virtual_source_events. Such gaps may hide missed virtual
stops, so the resulting trial is incomplete and cannot support promotion. Future/malformed
quotes, invalid reception time, bad source health/provenance and contract changes block
without acknowledging that event. No skip/delete override is implemented.

Ledger receipt and cursor acknowledgement use separate virtual DB transactions. Delivery
is at least once: if the ledger commits and the process crashes before cursor acknowledgement,
restart checks its stable market-event receipt and acknowledges the already committed
transition, even if it is now old. This never relaxes freshness for a NEW transition.
Concurrent consumers use the same receipt and compare-and-set cursor; cursor_race_retry
means retry from the stored checkpoint. Audit dispositions/bindings are immutable.

The collector, global stop, source read and virtual transition do not share one distributed
transaction. A feed/stop can change after validation of an in-flight observation. No entry
is possible through this consumer; production broker fencing is still unimplemented. SQLite
source index/UUID initialization is additive; schema marker 8 is in virtual storage. Keep
source and virtual DB/WAL backups consistent. No new Windows service/supervisor is installed.

## First run: isolated fixture

After reviewing/merging and updating to 0.5.1:

```powershell
cd C:\OMNEX-AURA
git switch main
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m aura.virtual_consumer_fixture
```

Expected: three applied states, restart_state idle, ledger_events 3, position_open false,
emergency_stop_unchanged true, entries_enabled false and execution_allowed false. This
uses a NEW temporary fixture store, leaves the stop ON and touches no operational data.

## Actual VPS observation gate

First verify the intended Equiti terminal is receiving advancing quotes, not just old chart
candles. Retain/set the explicit terminal path and expected demo account/server environment.
Run `python -m aura.diagnose --symbol XAUUSD`. If timestamps still show the previously
observed +3-hour discrepancy, review a fresh quote policy following MT5_TIME_POLICY.md.
Do not reuse an expired policy or assume the same offset after a session/DST change.
Do not alter the Windows clock or enlarge freshness limits. Send diagnostic output if it
fails. All actual current-quote acceptance remains pending until tested on the VPS.

With a currently valid reviewed quote policy, keep the read-only collector running in
PowerShell window A (omit the policy flag only if verified native UTC quotes need no correction):

```powershell
.\.venv\Scripts\python.exe -m aura.collect --broker Equiti --stream equiti-demo-1 --symbol XAUUSD --quote-time-policy data\equiti-quote-time.json --watch
```

Only after fresh quotes are being persisted, create the observer configuration in window B.
The example costs below are research ASSUMPTIONS, not verified Equiti fees, and must be
reviewed before any future virtual-entry strategy. No positions can be opened here:

```powershell
@{
  session = 'equiti-observer-1'
  feed = @{broker='Equiti'; source='mt5_demo'; stream='equiti-demo-1'}
  symbol = 'XAUUSD'
  costs = @{
    evidence_source='demo_observation'
    commission_per_lot_side='7'
    slippage_price='0.1'
    swap_debit_per_lot_utc_day='1'
  }
} | ConvertTo-Json -Depth 4 | Set-Content -Encoding ASCII data\equiti-observer.json
```

Set AURA_MT5_EXPECTED_LOGIN and AURA_MT5_EXPECTED_SERVER locally in window B too (PowerShell
process environments are separate). This consumer needs no terminal path or credentials:

```powershell
$env:AURA_MT5_EXPECTED_SERVER = 'EquitiSecurities-Demo'
$env:AURA_MT5_EXPECTED_LOGIN = Read-Host 'Enter the same Equiti DEMO login locally'
.\.venv\Scripts\python.exe -m aura.consume_virtual --config data\equiti-observer.json --data-dir data --watch
```

Each loop processes at most 100 events. Output reports applied/idle/skipped dispositions;
errors use fixed codes without account IDs or native exception strings. Press Ctrl+C to
stop; restarting uses the same source binding/cursor/ledger receipts. A one-shot run without
--watch is useful for acceptance. If no contract is saved, collect_fresh_contract_and_quote_first
requires a successful collector poll; importing four historical candles alone is insufficient.
A blocked feed/session must be investigated without deleting DBs or changing bindings.

Send the summary JSON, not account prompts or raw DB files. Repeated idle may mean either
caught-up processing or a stopped collector; inspect collector freshness/health separately.
Idle is not a healthy-live-feed assertion. No notifications or monitoring service is enabled.

Automated strategies, durable 2/3-day evaluation, full order lifecycle, authenticated UI,
licensed news, calibrated costs and real VPS observation/restart acceptance remain pending.
