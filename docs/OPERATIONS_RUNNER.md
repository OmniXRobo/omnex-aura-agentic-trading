# Local research and diagnostic runner (0.6.1)

The runner is an independent Python process. It polls the durable research queue and,
when explicitly supplied existing evaluation plans, runs virtual diagnostics. It does
not create market signals, fetch new snapshots, run external AI, launch MT5, collect
quotes, consume virtual quotes, open positions or submit orders. It never clears the
emergency stop. An empty queue remains empty.

## Use the same persistent data directory

On the Windows VPS, after reviewing/merging this PR and updating the checkout:

```powershell
cd C:\OMNEX-AURA
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
```

Stop the old dashboard with Ctrl+C in its own PowerShell window, then restart with:

```powershell
.\.venv\Scripts\python.exe -m aura.dashboard --data-dir C:\OMNEX-AURA\data --open-browser
```

The console now prints its absolute data directory. Connect using the locally printed
token. System & audit shows that directory to administrators, plus the runner's latest
poll heartbeat. Viewer access does not reveal the directory. Existing market data must
be in this directory; nothing is copied, synthesized or imported automatically.
The chart initially selects quote observations. Select closed M1 candles to inspect
previous historical imports; four imported candles do not imply saved live ticks.

In a second PowerShell window:

```powershell
cd C:\OMNEX-AURA
.\.venv\Scripts\python.exe -m aura.operations --data-dir C:\OMNEX-AURA\data
```

Keep that process running independently of ChatGPT. Ctrl+C stops it. A second runner
using the same directory is rejected by an OS-held lock. A crash releases the lock;
the dashboard marks the last running heartbeat stale after 20 seconds (or on future
clock skew). A recent poll is process evidence, not broker/data/strategy health.
A long job can delay the heartbeat and appear stale; no competing runner is started.

To include evaluations, append `--evaluation-plan C:\path\to\reviewed-plan.json`.
Repeat for at most ten distinct existing virtual sessions. Plans must use the existing
EvaluationPlan schema documented in VIRTUAL_EVALUATION.md. No sample operational plan
is invented. Reports and durable due cursors retain the evaluator's existing idempotency
and diagnostic limits. After three consecutive evaluator errors that task is blocked
until operator review and process restart. Research queue polling continues; generic
failure states exclude private exception details. If safety/storage reads fail, the
runner exits instead of changing safety controls.

Do not run the old evaluator watch process for a plan while this runner handles it.
The operations lock excludes other operations runners only, not every legacy CLI.
The collector and virtual quote consumer still require their separately reviewed
configuration and separate processes. Do not renew timestamp policies based on weekend
stale quotes. Actual fresh-feed acceptance remains pending market reopening.

## Optional Windows user-logon recovery

Review `scripts/register-operations-task.ps1`, then run it locally from PowerShell:

```powershell
.\scripts\register-operations-task.ps1
Start-ScheduledTask -TaskName OMNEX-AURA-Research-Operations
```

This opt-in task polls research jobs only, using the repository's `data` folder. It
starts under the current interactive user at logon with limited privileges, ignores
duplicate task starts, and requests up to three one-minute failure restarts. It does
not persist passwords, tokens or account IDs. Registration does not immediately run it.
If your script policy blocks it, use the Python command above; no policy bypass is
required. A custom data folder or unattended sign-out/service setup needs separate
review. It is not a Windows service and does not guarantee execution before user logon.
No Windows task was registered or reboot-tested from the Linux development environment.

Removal:

```powershell
Stop-ScheduledTask -TaskName OMNEX-AURA-Research-Operations
.\scripts\register-operations-task.ps1 -Remove
```

## Acceptance still required on the VPS

Confirm the absolute data directory, existing candle view, runner heartbeat, clean
stop, second-instance rejection, logon task startup and crash recovery. Browser user
screenshots establish that the 0.6.0 shell/login/empty command center render, not all
page interactions or fresh market data acceptance. Live-money execution remains disabled.
