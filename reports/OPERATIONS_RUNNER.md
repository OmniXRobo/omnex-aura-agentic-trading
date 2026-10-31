# Operations runner continuation — 0.6.1

Implemented a local long-running research queue and optional virtual diagnostic poller,
a cross-process OS data-directory lock, durable redacted heartbeat/task status, bounded
three-failure evaluator blocking, dashboard status/path projection, explicit absolute
launcher paths, and optional current-user Windows logon task registration/removal scripts.
The runner never clears the kill switch, creates entries, invokes MT5 or calls external AI.

Validation: 331 tests passed, zero failed/skipped; Ruff and JavaScript syntax checks
passed; source distribution and wheel built successfully. Ten new acceptance tests
include actual subprocess CLI execution, concurrent lock rejection, abrupt process kill,
restart recovery, durable job/report idempotency, stale/future heartbeat classification,
redaction and authenticated directory projection. The only pytest warning is the existing
Starlette/httpx TestClient deprecation.

No dependency changes. No real credentials, databases or broker account data are committed.
Windows Task Scheduler script execution and actual logon/reboot acceptance remain pending;
Linux subprocess evidence does not establish Windows VPS operational acceptance. Owner
screenshots establish earlier login/empty dashboard rendering only. The new browser
status UI has syntax/API coverage; interactive browser acceptance remains pending.

This milestone does not supervise collectors or quote consumers, implement backups,
external AI adapters, automatic strategy entries, self-healing, demo orders or Android.
No task is installed and no process is started on the owner's VPS by this PR. Follow
`docs/OPERATIONS_RUNNER.md` after review and merge. Live-money trading remains disabled.
