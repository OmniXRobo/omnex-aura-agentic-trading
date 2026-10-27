# Windows MT5 read-only setup (0.2.0)

This collector reads an already signed-in MT5 demo session. It cannot submit, amend or
close orders. It does not accept broker passwords or log into accounts. Keep all secrets
on the Windows VPS, never in GitHub or chat. Windows Server 2022/actual broker verification
has not been performed in the development container.

## Prepare the VPS

1. Install Python 3.12 and Git, and the desired broker's official Windows MT5 terminal.
2. Download/check out the reviewed `dev/m2-market-data` branch. Use an explicit terminal
   installation for each broker. Sign into a DEMO account in MT5 yourself.
3. Open PowerShell in the repository folder and create an isolated environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m pip install MetaTrader5
```

`MetaTrader5` is Windows-only and installed only on this VPS. Its installed version and
terminal build must be recorded privately during actual acceptance. This release does
not pin an untested broker package version. Current Linux pins still need Windows VPS
validation, despite the backend's successful GitHub Windows CI matrix.

## Set process-local configuration

Replace the following local values. The example terminal path may differ on your VPS.
LOGIN_NUMBER is the numeric demo login shown by your terminal; EXACT_DEMO_SERVER must
match account_info().server. The collector checks the actual demo trade_mode too, so
putting 'Demo' in a server name cannot enable a real account.

```powershell
$env:AURA_MT5_TERMINAL_PATH = 'C:\Program Files\YOUR BROKER MT5\terminal64.exe'
$env:AURA_MT5_EXPECTED_LOGIN = 'LOGIN_NUMBER'
$env:AURA_MT5_EXPECTED_SERVER = 'EXACT_DEMO_SERVER'
$env:AURA_DATA_DIR = 'C:\OMNEX-AURA\data'
```

Do not run this as written without replacing the placeholders. Use one unique stream
per account/terminal. Broker labels Exness/Equiti/MultiBank are operator labels; the
expected account and exact server are the verified binding. Reusing a stream for a
different account is blocked by a stored fingerprint. No passwords are written by this
collector and login/server values are not emitted in normal output.

## Discover gold and collect

```powershell
.\.venv\Scripts\python.exe -m aura.collect --broker Exness --stream exness-demo-1 --discover
```

Choose a returned symbol explicitly, e.g. XAUUSDm. Discovery requires broker metadata
currency_base=XAU and currency_profit=USD rather than relying on a GOLD name substring.
Contract checks also require positive tick value/size/contract size, consistent point
precision, and valid volume constraints. The symbol must be available in Market Watch;
select/show it manually in MT5 if needed. The collector never auto-selects an ambiguous
symbol or changes the account.

```powershell
.\.venv\Scripts\python.exe -m aura.collect --broker Exness --stream exness-demo-1 --symbol XAUUSDm
.\.venv\Scripts\python.exe -m aura.collect --broker Exness --stream exness-demo-1 --symbol XAUUSDm --watch --interval 1
```

Use the actual discovered symbol. Change --broker and --stream for Equiti or MultiBank.
Stop with Ctrl+C. Each poll verifies account/connection before and after reading, refuses
stale/future/crossed/invalid quotes, records metadata and a quote snapshot, and updates a
heartbeat. This is a sampled quote collector; rapid ticks between polls can be missed.
It is NOT a lossless tick archive, high-frequency feed or an executable trading signal.
An unchanged quote older than five seconds blocks even if the market is merely quiet.
The collector does not infer market-open/closed sessions.

## Import closed candles

Use timezone-aware ISO-8601 boundaries with explicit UTC offsets. Maximum 31 days per
request. Select a completed historical interval available in your broker terminal.

```powershell
.\.venv\Scripts\python.exe -m aura.collect --broker Exness --stream exness-demo-1 --symbol XAUUSDm --timeframe M1 --history-from '2026-10-20T00:00:00+00:00' --history-to '2026-10-21T00:00:00+00:00'
```

Supported periods: M1/M5/M10/M15/M30/H1/H4/D1. Requests page across UTC time ranges;
non-closed candles are skipped. Exact repeats are deduplicated, changed candles remain
as immutable revisions, and the read API selects the latest observed revision. An
interrupted request can be retried from the same boundaries: already stored events
are not duplicated. Commits occur per event after each page is validated, so the whole
import is not a single transaction. A DB failure can leave a partial page; retries dedupe.

Potential gaps are reported between returned bars; they may be session/weekend gaps.
Completeness always remains UNVERIFIED because broker chart history can be truncated
and edge gaps/session calendars are not yet verified. Do not backtest or train against
this data as a complete, leakage-safe dataset without the later quality gates.
D1 close boundaries currently use 86,400 seconds; verify broker/session conventions
before strategy use.

## Read the stored data from the backend

Start the authenticated backend with the SAME absolute AURA_DATA_DIR. Existing historical,
virtual and demo records remain intact. Startup adds historical market schema version 2.

- `GET /v1/market/feeds`: heartbeat/state with stale-heartbeat indicator after 15 seconds.
- `GET /v1/market/events?feed=mt5_demo:Exness:exness-demo-1&symbol=XAUUSDm&kind=quote`
- Change kind to candle/contract; candle queries support timeframe=M1 and limit up to 500.

Use the normal admin/viewer bearer token. These endpoints cannot connect to MT5 or write
market data. Returned quotes are historical observations; always inspect event timestamps.
All results say execution_allowed=false. Current prices do not automatically feed strategies.

## Failure behavior and remaining gates

Account switches, disconnection or invalid metadata block collection. Watch mode retries
reads without placing orders; if the native session needs initialization, a supervisor
must restart the collector after the terminal is restored. Full Windows service registration,
terminal reconnect and reboot recovery are still pending. A healthy feed heartbeat means
only that a recent snapshot was collected; it does not prove continuous market coverage.
An idle collector's heartbeat becomes stale. History-only imports do not mark a live feed
healthy.

Swap metadata retains the broker's mode and raw values. Commission, exchange rates,
trading sessions and realized execution costs are still unknown and must be configured
and validated before virtual sizing/backtests. Retail tick volume is a proxy, not complete
institutional order flow. No demo or live-money order operation exists in 0.2.0.

Official integration references:
- https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5symbolinfo_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5symbolinfotick_py

For login, stream-conflict or quote/contract errors, follow MT5_TROUBLESHOOTING.md before
retrying. In 0.4.1, `python -m aura.diagnose --symbol XAUUSD` can inspect the terminal
without binding any stream or writing market data. Do not replace an Equiti login with
a login from a separately running MetaQuotes terminal.
