# Read-only candle timestamp evidence — 0.4.3

Purpose: establish what the connected demo terminal actually returns before designing a
historical conversion policy. Quote corrections do not prove candle time encoding.
The probe never creates a database/stream/policy, changes a symbol selection, logs in,
places orders, or authorizes historical ingestion. No broker login number is emitted.

Official API reference:
https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrompos_py
Position zero is the current bar. The diagnostic reads at most five recent bars by
position, then requests the inclusive numerical range from the first to last opening
using timezone-aware UTC datetime objects. It compares opening timestamps only, not OHLC
values: the current bar may change while it is read. A matching round trip establishes
numerical query consistency, not UTC correctness or historical daylight-saving behavior.

Each of three samples includes raw quote time, Windows UTC observation/completion times,
raw candle openings, the latest opening's difference from the UTC timeframe bucket and
from the raw tick timeframe bucket, and range-replay opening timestamps. No offset is
automatically inferred or applied. No timezone is declared verified. The current bar is
included deliberately for diagnosis; this output is not a closed-candle research dataset.
M1 is the default. M5/M15/H1/D1 are optional; D1 session alignment is not assumed to be UTC
midnight. Sparse sessions, weekends, delayed updates and a candle rollover between native
calls can affect these relationships or cause a replay mismatch. Review the evidence.

The three default samples have two one-second pauses. Native MT5 reads themselves can
block; this command provides no native-call hard timeout. A failed read emits a fixed
error code, retaining only previously completed samples. It never echoes native exceptions.
The explicit expected account/server must match a connected demo account before reads,
and identity is checked before/after each native quote/candle read. Contract and quote
shape validation is required; raw quote freshness is reported rather than required because
the purpose is diagnosing the timestamp discrepancy. Five-second collector protection is
unchanged. The report's `probe_completed` flag means collection of evidence finished, not
that the market data is accepted. `history_time_verified`, `history_import_authorized`,
`stream_modified` and `execution_allowed` remain false.

After reviewing/merging the PR:

```powershell
cd C:\OMNEX-AURA
git switch main
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
$env:AURA_MT5_TERMINAL_PATH = 'C:\Program Files\MT5_2\terminal64.exe'
$env:AURA_MT5_EXPECTED_SERVER = 'EquitiSecurities-Demo'
$env:AURA_MT5_EXPECTED_LOGIN = Read-Host 'Enter the Equiti MT5_2 DEMO login locally'
.\.venv\Scripts\python.exe -m aura.diagnose --symbol XAUUSD --candle-time-probe
```

Do not add `--quote-time-policy` to this command: it deliberately collects raw evidence.
Copy the JSON output, excluding the login prompt. To keep an optional private copy:

```powershell
New-Item -ItemType Directory -Force data | Out-Null
.\.venv\Scripts\python.exe -m aura.diagnose --symbol XAUUSD --candle-time-probe | Set-Content -Encoding ASCII data\equiti-candle-time-probe.json
```

Keep evidence in ignored local data storage, not the public repository. No screenshots,
account identifiers, native databases or user market observations are committed.

Next acceptance gate: inspect actual VPS output, compare candle chart labels and known UTC
observations across more than one session, then design a separately reviewed historical
policy with date ranges and raw-time provenance. Do not reuse a present quote offset for
old candles or remove the existing nonzero-offset history block. Until that gate passes,
research may continue with labelled fixtures and historical broker acceptance stays pending.

Update for 0.4.4: an independently reviewed, dated intraday history policy is now
implemented; see [history policy](MT5_HISTORY_TIME_POLICY.md). Quote policy alone still
does not authorize history conversion, and no UTC/DST rule is inferred by the probe.
