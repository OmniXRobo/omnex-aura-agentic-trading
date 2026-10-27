# OMNEX AURA 0.1.0 — foundation checkpoint

Demo-only research platform in development. Live execution is prohibited in V1.
This checkpoint is runnable locally; it is not an autonomous trading release.

## Run locally

Python 3.11 or 3.12:

```bash
python -m venv .venv
# Activate the virtual environment using your operating system's normal command.
python -m pip install -r requirements.lock
python -m pip install -e . --no-deps
# Configure AURA_ADMIN_TOKEN (32+ random characters) in the process environment.
python -m uvicorn aura.api:create_app --factory --host 127.0.0.1 --port 8080
```

On Windows use `scripts/start-backend.ps1` after configuring the service environment.
Environment files are ignored by Git but are not automatically loaded by this application.
Use a secret manager or process environment. Never paste keys into issues or commit them.
No AI or broker credentials are required for this local deterministic checkpoint.

`GET /health` is public. Other endpoints require `Authorization: Bearer <token>`.
Use distinct `AURA_ADMIN_TOKEN` and optional `AURA_VIEWER_TOKEN`. These are local
bootstrap service tokens, not a complete end-user login system.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | /v1/status | Mode, safety state, unavailable provider status |
| GET | /v1/agents | All 15 roles with honest implementation status |
| POST | /v1/research/run | Execute 3 independent local tasks, save evidence |
| POST | /v1/risk/preview | Validate a caller-supplied hypothetical proposal |
| PUT | /v1/safety/kill-switch | Persist emergency-stop state (admin only) |
| GET | /v1/memory/{historical,virtual,demo} | Read separated local records |

Example research body:

```json
{"symbol":"XAUUSD","prices":[3000,3001,3002],"tick_age_seconds":1,"source":"fixture"}
```

This returns NO TRADE with evidence from simple sample statistics, a descriptive
sample label, and data-quality checks. These are not an ML model, validated market
classifier, live broker feed, or provider-backed AI predictions.

## Verify

```bash
python -m pytest -q --junitxml=reports/junit.xml
python -m ruff check aura tests
python -m build
```

Independent stop, even with the API closed:

```bash
python -m aura.safety --data-dir ./data
```

All paths must use the same absolute data directory on deployment. The kill switch
starts ON. Turning it off does not enable order execution: no order-send implementation
exists. Risk previews consume caller-supplied facts and cannot authorize a broker order.

See ARCHITECTURE.md, ROADMAP.md, ACCEPTANCE_CRITERIA.md, docs/MT5_DEMO_PLAN.md,
docs/OPERATIONS.md and reports/MILESTONE_1.md. The full input specification is preserved
in docs/MASTER_SPECIFICATION.md.
