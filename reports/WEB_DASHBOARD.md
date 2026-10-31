# Operations dashboard milestone — 0.6.0

Adds an authenticated local web dashboard for saved market observations, 15 agent roles (three implemented local tasks), virtual sessions, immutable evaluation reports, job counts, and audit summaries. The loopback launcher supplies an ephemeral console token when no admin token is configured. Tokens stay in browser memory; viewer access is read-only. The dashboard emergency stop can only activate the stop.

Normal launch does not seed fixtures, start collectors or evaluation workers, contact external AI providers, or submit broker orders. Existing API authorization remains in place. Overview projections exclude account identifiers and binding fingerprints. Runtime and package versions now agree.

Validation: 321 tests passed, zero failures/errors/skips; Ruff passed; JavaScript syntax passed; git whitespace checks passed; wheel and source distribution built successfully with HTML/CSS/JS assets included. Backend HTTP smoke checks passed. Synthetic fixture tests cover populated and empty views, authorization, stop-only behavior, missing safety controls, and projection privacy.

Browser rendering could not be verified because the managed preview runner could not access the Python virtual environment. Windows browser acceptance remains pending. This is a local web app, not an Android APK or public hosted deployment. External AI integration, automatic virtual entries, continuous forward trials, and Windows service supervision remain pending. Live-money trading remains disabled.

See docs/WEB_DASHBOARD.md for VPS update and launch instructions.
