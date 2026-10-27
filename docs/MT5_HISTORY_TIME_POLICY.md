# Dated intraday candle timestamp policy — 0.4.4

The sampled VPS candle/tick comparison supports a recent local discrepancy, not a universal
broker timezone or historical DST schedule. A separate, operator-reviewed history policy
now permits a specific interval only. It never inherits a quote correction. This policy is
an attestation recorded for audit, not independent verification by the software.

Scope is exact server, symbol and intraday timeframe. `valid_from_utc` is inclusive and
`valid_to_utc` exclusive, expressed as Unix seconds. The interval must already have ended
when reviewed and span no more than 31 days. A request must fit completely inside one
reviewed interval. No extrapolation across dates, sessions or DST is implemented. Offset
is raw broker time minus UTC; raw query boundaries add that offset, returned openings
subtract it. All passed datetime objects remain UTC-aware numerical transport values.
Corrected D1 imports are deliberately unsupported because daily-session conventions have
not been established. Do not infer them from M1 evidence.

All MT5 demo history imports now require `--history-time-policy`, including offset zero.
This intentional change prevents omitting the quote policy flag from restoring an
unreviewed UTC interpretation. Labelled fixture history retains its default UTC behavior.
Quote policy expiry/freshness is independent of historical review. History imports need
no current quote and cannot place orders.

Each imported policy-backed candle retains raw opening time, normalized UTC opening time,
offset and policy digest. Full policy JSON is saved in append-only historical storage.
Existing events and account bindings are not rewritten. Schema marker 6 adds policy and
interpretation tables. Before fetching, imports reserve their UTC/raw interpretation under
an immediate SQLite transaction. A different offset cannot overlap either a previous UTC
interval or its raw transport interval for the same feed/symbol/timeframe, including across
restart and concurrent attempts. Interrupted/empty imports retain reservations. Legacy
candles lacking provenance prevent nonzero reinterpretation of that stream/timeframe.
On conflict, preserve the data and investigate; do not delete the DB or reset bindings.
This protects ingestion paths, not arbitrary manual database modification.

Pages validate before any candle of that page is appended. Earlier pages may remain if a
later page fails. Replay with the same policy deduplicates exact observations; changed
candles remain immutable revisions. Changing policy evidence changes its digest and can
produce additional audit versions, never an overwrite. Complete bars only are imported;
bar close must be within the requested UTC end. Gaps/completeness remain unverified.
Policy validation is done before native historical reads or interpretation reservation.

## Windows validation after review/merge

Update to 0.4.4 and retain the explicit Equiti demo terminal/account environment settings:

```powershell
cd C:\OMNEX-AURA
git switch main
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
New-Item -ItemType Directory -Force data | Out-Null
.\.venv\Scripts\python.exe -m aura.diagnose --symbol XAUUSD --candle-time-probe | Set-Content -Encoding ASCII data\equiti-candle-time-probe.json
```

Review that fresh raw ticks advance, the recent M1 candle offset is consistently +10800,
and range replays match. Compare against synchronized UTC. Use only the CLOSED bars covered
by that observation. The most recent raw bar is current and must be excluded: an example
interval starts at the earliest sampled raw opening minus 10800 and ends at the current
raw opening minus 10800, provided the samples agree. Do not extend that evidence to a full
day or month. If there is disagreement, stop and inspect it instead of creating a policy.

Enter those reviewed UTC boundaries explicitly (ISO format with +00:00). These commands
create a local policy only; do not include a login number or password in its evidence:

```powershell
$from = [DateTimeOffset]::Parse((Read-Host 'Reviewed CLOSED interval start UTC, with +00:00'))
$to = [DateTimeOffset]::Parse((Read-Host 'Reviewed CLOSED interval end UTC, with +00:00'))
@{
  server = 'EquitiSecurities-Demo'
  symbol = 'XAUUSD'
  timeframe = 'M1'
  offset_seconds = 10800
  valid_from_utc = $from.ToUnixTimeSeconds()
  valid_to_utc = $to.ToUnixTimeSeconds()
  reviewed_at_msc = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
  evidence = 'Operator reviewed the saved recent M1 position/range probe against synchronized UTC; closed interval only'
} | ConvertTo-Json | Set-Content -Encoding ASCII data\equiti-history-time.json

.\.venv\Scripts\python.exe -m aura.collect --broker Equiti --stream equiti-demo-1 --symbol XAUUSD --timeframe M1 --history-from $from.ToUniversalTime().ToString('o') --history-to $to.ToUniversalTime().ToString('o') --history-time-policy data\equiti-history-time.json
```

Keep the same existing account-bound stream. A first successful import should report a
positive `inserted` count and `time_verification: operator_attested`; repeating with the
same policy should report duplicates. Neither proves strategy quality or complete broker
history. Send only the summary JSON, not your login prompt, local policy or raw database.
If there is a binding conflict or zero candles, preserve it and send the fixed error/summary.

Actual VPS import/replay remains an acceptance gate. Historical broker commission/session
validation, long-range dated evidence, lossless ticks, external AI providers, virtual/demo
execution and production operations remain pending. Live-money trading is disabled.
