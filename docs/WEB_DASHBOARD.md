# Local operations dashboard — 0.6.0

OMNEX AURA now has a browser dashboard served by the existing FastAPI backend, with packaged
HTML/CSS/JavaScript and no Node.js installation/build required on the Windows VPS. It uses
saved backend evidence: no fake prices, balances, signals, provider integrations or process
heartbeats are substituted when data is absent. The dark interface is responsive, but it
is not an Android APK.

## Open the app after reviewing/merging the PR

In PowerShell ON THE VPS:

```powershell
cd C:\OMNEX-AURA
git switch main
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m aura.dashboard --open-browser
```

The console shows this URL:

http://127.0.0.1:8000/dashboard

If no AURA_ADMIN_TOKEN is configured, the launcher generates a random temporary local
access token and displays it once in that console. Copy it into the dashboard's Access
token field and choose Connect. Keep it local: do NOT send a screenshot containing that
token to chat, GitHub or another person. It is neither an OpenAI key nor a broker password.
No external AI credential is required to view the dashboard. If existing admin/viewer tokens
are configured, use them; the launcher does not print configured tokens.

If the browser does not open automatically, paste the URL into Chrome/Edge INSIDE THE VPS.
A loopback URL opened on your phone/home PC points to that different device, not this VPS.
Do not expose this bootstrap bearer-token service to the public internet. Remote HTTPS,
production login sessions and Android distribution remain later deployment gates.

Leave the PowerShell process running. Ctrl+C stops the dashboard. This command does not
start the collector, evaluator, strategy engine or a Windows service. Those processes are
independent and their supervision is not configured by opening the dashboard. ChatGPT does
not need to stay open for an already running VPS process, but closing its terminal can stop
that process. Use --port 8001 if another backend already occupies port 8000; the printed URL
will use that port. The launcher always binds to 127.0.0.1, never all network interfaces.

`scripts\start-dashboard.ps1` is an optional wrapper for the same command. No execution-policy
bypass is required or provided; the Python command above works without that wrapper.

## Available views

- Command center: virtual equity/session counts, positions, implemented agent functions,
  recent diagnostic reports, collector heartbeat evidence and last local research records.
- Market evidence: saved bid quote samples or closed M1 candles, feed/symbol selection,
  UTC timestamps and explicit timestamp-interpretation labels. Charts are observations,
  not current trading signals. Fixture/stale/saved data is labelled. No data means an
  empty state, never an illustrative market price.
- AI agents: all 15 roles, distinguishing three implemented deterministic local tasks from
  planned functions, with saved last-run results where available. This is not liveness.
- Virtual sessions: separate source labels, simulated cash/equity, halted/open states,
  position SL/TP/strategy evidence. Summed session equity is not one deployable portfolio.
- Evaluations: recent saved rolling reports, quality flags, costs/expectancy/profit factor
  and due endpoints. Reports are diagnostic and overlapping. No promotion is permitted.
- System/audit: declared provider implementation status, stored job states, runtime limits
  and recent audit actions. Stored running jobs/plans are not proof of live background workers.

The authenticated summary API returns bounded projections (20 sessions/reports/feeds,
five research records, ten audit actions). It reads existing optional virtual schemas
without constructing ledgers, creating evaluation plans or altering account/source bindings.
Missing/corrupt safety/evidence returns unavailable instead of a green operational status.
Source-account fingerprints, broker login IDs and authentication tokens are excluded.

All views require the existing administrator or viewer bearer token. The shell and its
static assets are public locally but contain no saved operational evidence or tokens. The
browser retains its token only in tab memory; it uses no browser storage, cookies or URL
credential. Disconnect clears the token and data projections; refresh/restart needs login
again. Backend replies have no-store, nosniff, frame denial, referrer and restrictive CSP
headers. Dynamic evidence is rendered with textContent, not untrusted HTML. No external
fonts, CDNs, analytics or third-party chart scripts are loaded.

Viewer access is read-only. The new dashboard action only turns the persisted emergency
stop ON, requires administrator access and rejects enabled=false. There is no UI to clear
the stop, open/close positions, activate entries, change risk, promote a model or submit
broker orders. The older separately authenticated research APIs remain unchanged. The
stop does not retroactively cancel in-flight virtual operations; existing cross-database
fencing limits still apply. Broker and live-money execution remain unavailable.

## Validation and current limits

HTTP/auth/projection/safety tests cover an empty database and a synthetic populated one.
JavaScript syntax and Python lint/tests/builds are checked, including that dashboard assets
are inside the wheel. The managed browser-preview runner cannot use this checkout's Python
virtual environment, so visual browser QA is UNVERIFIED in this environment. No alternative
browser-control path or public deployment was improvised. Actual Windows browser rendering,
login, navigation, chart interaction and the stop control remain owner acceptance checks.
Send a browser screenshot of the dashboard AFTER connecting; exclude the token console.

For local development only, `scripts/preview-dashboard.py` seeds a NEW temporary directory
and serves explicitly labelled synthetic evidence. Its fixed synthetic test tokens are not
operational credentials and must never be used with real data. Normal launch never seeds
fixtures. The fixture helper refuses any nonempty directory. Runtime/API version reporting
now matches package version 0.6.0 (earlier package increments left the API version stale).

Fresh market observation, production authentication/TLS, supervised services, external AI
adapters, full strategy lifecycle, automatic virtual entries, Android APK and approved
challenger validation are still pending. This UI is operational visibility, not completion
of the full master specification. No live-money trading is enabled.
