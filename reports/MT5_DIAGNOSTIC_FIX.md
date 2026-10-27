# MT5 diagnostics and account-binding repair (0.4.1)

Observed: the VPS installed OMNEX AURA and both terminal diagnostics reported demo
accounts. Metadata identified a MetaQuotes demo terminal and an Equiti demo terminal.
A first collection attempt returned a generic error. A second attempt used the other
terminal's login and hit the stream-binding guard. No successful quote persistence was
shown. No account numbers or personal data from those screenshots are committed here.

Root causes addressed: constructor binding happened before account verification, and
polling collapsed actionable identity/metadata/freshness errors into one generic message.
The patch verifies actual demo identity before new binding persistence, preserves existing
bindings, emits sanitized categories and removes raw tracebacks from expected CLI failures.
It adds a standalone read-only diagnostic with match booleans, contract fields and tick
freshness. Diagnosis does not access a database or change account/symbol/stream state.

Tests: 178 local tests passed (163 existing + 15 diagnostic regressions), zero failures;
one existing TestClient deprecation warning. Ruff, HTTP/restart/independent-stop smoke
and source/wheel builds are checked before publishing. New PR remote CI is separate.
This is a fixture-tested repair, not proof that the first VPS error was a particular
contract/freshness problem. Actual successful collection is still pending.

No stored fingerprint is overwritten, no data is deleted, no freshness/account gate is
relaxed, and no order/login/amend/close operation is introduced. Broker execution and
promotion remain disabled. Next: run docs/MT5_TROUBLESHOOTING.md on the Equiti demo
terminal using its own login, then inspect the resulting safe diagnostics before retrying.
