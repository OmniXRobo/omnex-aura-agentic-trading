# Virtual market ledger foundation — 0.5.0

This is the first M5 component, not an autonomous trading release. `aura.virtual.VirtualLedger`
accepts explicit validated intents and quotes, simulates market fills and stores its state,
receipts, consumed intents and append-only events only in `virtual.db`. It has no MT5,
provider, network or order submission interface. Historical/demo records are not used as
virtual performance. The Store foundation still creates its standard three empty DBs.

A session fixes one instrument contract, declared evidence source, initial USD cash and
all cost/risk assumptions. Changing any configuration requires a separate labelled session;
existing evidence remains. The evidence source is caller-declared, not a verified provenance
chain. `demo_observation` is a label, not proof of broker-connected forward testing. The
caller must supply quotes from the independently accepted read-only collector. No HTTP API,
worker, strategy generator or continuously running quote consumer is wired to this engine.

## Implemented behavior

- Market entry at ask plus explicit adverse slippage for buys; bid minus slippage for sells.
- Exit uses bid minus slippage for buys and ask plus slippage for sells. SL/TP checks use
  the relevant bid/ask closing side. Gaps fill at the available quote, never an assumed
  protective level. Sampled quotes may miss intratick stop crossings.
- USD P/L uses XAU/USD contract size and volume. Decimal arithmetic tracks cash, liquidation
  equity, commission on each side and a declared nonnegative swap debit per lot per UTC
  midnight crossed. This swap approximation is not the broker's rollover calendar and
  does not support credits/triple-swap holidays. Costs must be provided explicitly.
- One position per session/instrument, with no same-quote exit-and-reentry. Different
  sessions are isolated experiments, not a consolidated portfolio/exposure guarantee.
- Entry requires the persisted global emergency stop to be OFF, with unavailable safety
  state failing closed. Creating a ledger never arms that stop. Active virtual SL/TP and
  cost marking continue when stopped; stop activation does not fabricate a liquidation.
- Fresh quotes must be no more than five seconds old, never future or out of order.
  Same-millisecond changed quotes are allowed. Exact input retries return the saved
  receipt even when old because no transition is repeated.
- Intents carry strategy version, reason, timestamps, SL/TP, volume and news-blackout state.
  They expire within 60 seconds. News blackout defaults ON. There is no news provider;
  clearing that flag is caller responsibility. Stop geometry/minimum distances, broker
  volume constraints, maximum spread and planned loss at the stop are checked.
- Planned loss includes both commissions and adverse exit slippage, capped at 0.25% of
  available cash by default (configuration may lower it). Actual gaps/overnight costs may
  exceed planned risk. Liquidation-equity drawdown produces a durable halt (5% default,
  at most 10%). A halt never clears automatically. There is no martingale or recovery
  sizing algorithm; volume is explicit and bounded by the same risk calculation.
- SQLite immediate transactions serialize position transitions. One transaction persists
  updated state, consumed intent, immutable receipt and audit event. Storage failure rolls
  them all back. Exact key/input replay is idempotent; key reuse with different input is
  rejected. An intent ID is consumed even if rejected, so a retry cannot later become a
  new position under another transport key. Changing an intent requires a new explicit ID.

The emergency stop is currently read from the historical control DB, whereas transitions
commit in the virtual DB. This is not an atomic multi-database kill-switch protocol: a
stop racing an in-flight transition may only affect the next transition. No broker orders
exist, and independent process fencing is a future integration gate. This component is
for serialized virtual research, not production broker execution.

Schema marker 7 is added only in virtual storage. Session state is the mutable projection;
audit events, receipts and consumed intents have update/delete protection. Backups must
capture the entire virtual DB and its WAL consistently; copying just a session row loses
idempotency evidence. No pruning or automatic expiry of learning records is implemented.

## Isolated Windows fixture check

After reviewing/merging the PR and updating to 0.5.0:

```powershell
cd C:\OMNEX-AURA
git switch main
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m aura.virtual_fixture
```

This CLI creates a NEW temporary fixture store, enables virtual entries only in that new
store, runs the synthetic exercise and removes the temporary store on completion. It does
not read/modify `C:\OMNEX-AURA\data`, broker terminals or existing emergency-stop controls.
Persistent deployments use VirtualLedger with a normal Store; the disposable CLI verifies
behavior without changing an operational configuration.

Expected synthetic result: entry opened, restart replay identical, exit take_profit, two
ledger events, final cash 10009.4600 and net P/L 9.4600, execution_allowed false. The numbers
come from deliberately chosen prices (3000/3000.2 entry quote, 3010/3010.2 exit quote), 0.01
lots, contract size 100, 0.1 adverse slippage and 7 USD commission/lot/side. They demonstrate
accounting, not profitability. No current market prices or strategy forecasts are involved.

## Remaining M5 gates

Fresh VPS quote collection, provenance/contract binding into a durable consumer, automated
strategy decisions, supervisor restart recovery, pending limit/stop orders, queue latency,
partial exits, trailing/break-even stops, margin/rejections, session/news policy providers,
daily/weekly exposure limits, calibrated broker costs, authenticated read APIs/dashboard,
and the durable two-/three-day evaluation schedule remain unimplemented. This checkpoint
must not be reported as completed virtual autopilot or a forward performance trial. Live
trading remains inaccessible, and demo broker execution is not introduced.
