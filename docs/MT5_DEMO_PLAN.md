# MT5 demo integration plan

## Current implementation

`aura/mt5.py` supplies a read-only injectable port and demo diagnostics. Fake-port tests
reject real and contest accounts, missing account metadata and disconnected terminals.
They do not establish a connection with Exness, Equiti or MultiBank.

`scripts/mt5-diagnostics.py` runs only on Windows, requires an explicit terminal path,
and uses the official MetaTrader5 package. It reads the currently selected account;
it does not log in, change credentials or send orders. All diagnostic results state
execution_allowed=false. The MetaTrader5 package is intentionally not a Linux runtime dependency.

## Connection procedure (M2)

1. Install the broker's official MT5 terminal on the Windows VPS. Record terminal build,
   Python/package versions and terminal path per broker. Do not assume symbol equivalence.
2. User selects a demo account inside the terminal; keep credentials in a Windows secret
   store. Record an allowlist of demo login ID and exact broker server privately.
3. Install the official MetaTrader5 Python package in the VPS virtual environment;
   set AURA_MT5_TERMINAL_PATH to that installation's terminal64.exe.
4. Run `python scripts/mt5-diagnostics.py` from the installed source checkout. Require
   `account_info().trade_mode == ACCOUNT_TRADE_MODE_DEMO`; account name/server text alone
   is never proof of a demo account. Real, contest, unknown, missing metadata: reject.
5. Discover candidates such as XAUUSDm, XAUUSD., GOLD. Manually verify base/profit currencies,
   contract size, digits, point/tick value, volume min/max/step, stop/freeze levels,
   allowed filling modes and sessions before mapping a canonical instrument.
6. Ingest UTC-stamped bid/ask ticks, candle close times, commission/swap assumptions,
   missing intervals and connection state. Reject future/stale/crossed/invalid ticks.
7. Import paginated history, preserve source and broker identity, deduplicate by event
   identity, and test gaps/restarts/DST separately. Never use an open candle as closed data.
8. Verify disconnection and restart behavior with read-only ingestion before M7.

## Demo execution procedure (M7, not implemented)

Require explicit demo activation with an audited login/server allowlist. Before EVERY
broker operation re-read terminal connection, account type/ID/server, fresh tick and
contract metadata, safety state and strategy eligibility. Reject any mismatch.
Use broker-calculated potential stop loss in account currency to size volume, round
down to the allowed step and ensure conservative exposure. Validate daily/weekly loss,
drawdown, equity, spread, slippage, session, news blackout and margin. Missing data blocks.

Reserve the instrument atomically across workers; record an immutable intent before
send. Use broker-compatible filling mode and broker-side SL/TP. Verify broker acceptance
and actual protective stops. A timeout/ambiguous send becomes UNKNOWN, never an automatic
blind retry. Reconcile active orders, positions and history using intent correlation,
magic/comment and broker tickets; comments alone cannot guarantee deduplication.
Block the instrument until reconciliation resolves ambiguity. Revalidate account and
risk for stop amendments, partial closes and trailing stops. Never widen SL to recover.

An independent safety process inhibits new entries even if the AI crashes. It does not
silently close positions; define and test protective position-management policy before
activation. Test account switching immediately before send, disconnection after send,
rejected SL, partial fills, concurrent requests, broker restart and VPS reboot. Activation
is prohibited until these gates pass for each broker.

## Official references

- https://www.mql5.com/en/docs/python_metatrader5
- https://www.mql5.com/en/docs/python_metatrader5/mt5accountinfo_py
- https://www.mql5.com/en/book/automation/account/account_real_demo_contest

The official integration supplies account_info, symbol metadata, ticks, history and order
APIs. Only its read-only diagnostics boundary is implemented in this checkpoint.
