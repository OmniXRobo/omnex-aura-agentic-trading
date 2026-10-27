# Explicit quote timestamp policy

MetaQuotes documents Python tick/bar times as UTC:
https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py
Keep UTC as the default. The observed VPS comparison showed +2 hours for one terminal
and +3 hours for another. This is evidence of a discrepancy, not proof of a universal
broker timezone rule or daylight-saving schedule. Do not change Windows time to match it.

An operator-reviewed local JSON file may specify a temporary quote-only correction.
There is no inferred offset, broker-wide default, automatic renewal or maturity bypass.
Subtract `offset_seconds` from raw milliseconds. Only the exact server and symbol match.
The policy is valid on [verified_at_msc, expires_at_msc), at most 24 hours. Five-second
quote freshness and rejection of future normalized ticks remain unchanged. A changed
server offset blocks collection; re-check evidence before issuing another policy.
A stale quote whose age happens to resemble an offset cannot be detected from that quote
alone: independently confirm advancing ticks, synchronized UTC and the correct symbol.
The policy is operator-attested evidence, not independently authenticated broker time.

After reviewing/merging the PR and confirming the discrepancy still exists, create a
ONE-HOUR local policy for the exact Equiti XAUUSD symbol (not XAUUSD.sd):

```powershell
cd C:\OMNEX-AURA
git switch main
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
New-Item -ItemType Directory -Force data | Out-Null
$verified = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
@{
  server = 'EquitiSecurities-Demo'
  symbol = 'XAUUSD'
  offset_seconds = 10800
  verified_at_msc = $verified
  expires_at_msc = $verified + 3600000
  evidence = 'Operator compared advancing Equiti ticks against synchronized VPS UTC; +3h observed'
} | ConvertTo-Json | Set-Content -Encoding ASCII data\equiti-quote-time.json

.\.venv\Scripts\python.exe -m aura.diagnose --symbol XAUUSD --quote-time-policy data\equiti-quote-time.json
```

Existing terminal path and expected demo login/server environment variables remain required.
Do not include account IDs/passwords in the policy evidence. Only proceed to collection if
all terminal checks pass, raw age is approximately -10800 seconds and corrected age is
between 0 and 5 seconds. Diagnostic mode never writes a stream or DB.

```powershell
.\.venv\Scripts\python.exe -m aura.collect --broker Equiti --stream equiti-demo-1 --symbol XAUUSD --quote-time-policy data\equiti-quote-time.json
```

A success inserts a quote only; no broker orders exist. Use `--watch` later for continuous
snapshot polling; expiry deliberately blocks the loop until a newly reviewed policy is
supplied on restart. This is not lossless tick collection.

Do not delete or rebind an existing stream on a conflict. The account fingerprint remains
immutable. A stream also locks its quote offset after the first successful poll, including
legacy streams containing quotes. Different policies with the same offset may renew within
new evidence windows. Raw time, normalized time, offset and policy digest are saved in each
corrected quote; the full policy is saved append-only in historical storage. Old events are
not rewritten. Schema marker 5 adds tables without altering existing data.

Nonzero quote corrections BLOCK historical imports, including D1. Quote observations do not
verify candle time encoding, request boundaries, historical DST or session alignment. A
separate dated history policy and broker comparison is still needed before enabling that
path. No automatic quote correction is reused for candles.
