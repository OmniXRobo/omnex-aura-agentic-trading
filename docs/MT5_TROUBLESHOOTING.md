# MT5 read-only collector troubleshooting (0.4.1)

The first deployed collector could record an entered login/server binding before it
verified that the running terminal matched it. A later attempt with another login then
correctly refused to reuse the stream, but its earlier generic collection message did
not distinguish identity, metadata and tick-freshness failures. This patch fixes the
premature binding and improves diagnostics. It does NOT bypass existing bindings.

## Diagnose before retrying collection

From C:\OMNEX-AURA on the Windows VPS, use the intended terminal and its actual DEMO
account. Read the login locally from THAT terminal, not another terminal's title bar.
Do not share passwords or put account IDs in GitHub issues. The diagnostic prints
login/server MATCH booleans, not the login number.

```powershell
$env:AURA_MT5_TERMINAL_PATH = 'C:\Program Files\MT5_2\terminal64.exe'
$env:AURA_MT5_EXPECTED_SERVER = 'EquitiSecurities-Demo'
$env:AURA_MT5_EXPECTED_LOGIN = Read-Host 'Enter the DEMO login from the Equiti MT5_2 terminal'
.\.venv\Scripts\python.exe -m aura.diagnose --symbol XAUUSD
```

Use these paths/server only if they match your installed Equiti terminal. The command
reads account type/company/server, connection state, expected-identity match booleans,
contract fields, Market Watch visibility when available, quote validity/spread/age and
whether identity remained stable during the reads. It does not create a Store, database,
feed, binding, order, account login or symbol selection. It has no broker order methods.

terminal_checks_passed means only that the current terminal identity, contract and quote
checks passed. It does NOT inspect existing stream bindings or prove collection success.
The existing stream is validated separately by the collector. No stale-data threshold
or demo/account safety gate is relaxed.

## Interpret safely

| Result/error | Meaning | Next step |
| --- | --- | --- |
| login_matches=false / login_mismatch | Entered login belongs to a different account | Check the intended Equiti terminal's DEMO login locally |
| server_matches=false / server_mismatch | Expected server differs from actual server | Confirm terminal/server; do not relabel a different broker as Equiti |
| not_demo | The account is real, contest or otherwise not a verified demo | Stop collection on that account; use the intended demo terminal |
| disconnected | Terminal/account connection is unavailable | Restore the terminal's connection and diagnose again |
| stream_binding_conflict | That stream already belongs to another saved account fingerprint | Keep existing data/binding intact; identify the correct original account before recovery |
| contract_invalid / contract_invalid_fields | Broker gold metadata is missing or invalid | Inspect the named fields; do not guess contract sizes/tick values |
| quote_invalid / quote_valid=false | Missing/nonpositive/nonfinite/crossed quote or invalid timestamp | Check the exact symbol and its available quote data |
| stale_tick / quote_fresh=false | Last quote is older than 5 seconds | Check Market Watch, feed and trading session; do not disable freshness validation |
| future_tick | Quote is ahead of VPS clock | Compare the Windows system clock and broker timestamps; do not fake tick times |
| native_read_failed / terminal_read_failed | Native read failed | Check the intended terminal/session; raw native errors are intentionally not echoed |

The screenshot that prompted this patch established a stream conflict after a second,
different login was entered. It did not establish the reason for the first generic
failure. It also did not prove that either gold symbol had a fresh valid quote. The
new report supplies that missing evidence without collecting under a new identity.

Do not delete the databases, overwrite a stored fingerprint, or choose random new stream
names merely to silence a mismatch. Existing pre-patch incorrect empty bindings are
not automatically rewritten. A genuinely different account must have an explicitly
identified separate stream after its identity is verified. Repair of an old incorrect
binding needs a separate reviewed recovery procedure with evidence preservation.

Collector construction now verifies live terminal account type/login/server BEFORE
persisting any new stream binding. A verified different account still cannot reuse an
existing bound stream. Constructor failures use sanitized structured errors without a
raw traceback; poll errors distinguish safe failure categories. Native exception payloads
are never copied into messages. No trading behavior, account switching, automatic login
or order operation is introduced.
