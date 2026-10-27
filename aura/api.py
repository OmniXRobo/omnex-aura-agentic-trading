import hmac
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from . import __version__
from .agents import AGENT_ROLES, Orchestrator, Snapshot
from .backtest import BacktestRequest, ResearchConflict, persist_backtest
from .config import Settings
from .market_store import MarketStore
from .risk import Proposal
from .store import Store
from .validation import HoldoutConflict, ValidationRequest, persist_validation


class KillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool


def create_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        app.state.store = Store(settings.data_dir)
        app.state.market = MarketStore(app.state.store)
        yield

    app = FastAPI(
        title="OMNEX AURA",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    bearer = HTTPBearer(auto_error=False)

    def identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(401, "Authentication required")
        token = credentials.credentials
        if hmac.compare_digest(token.encode(), settings.admin_token.encode()):
            return "admin"
        if settings.viewer_token and hmac.compare_digest(
            token.encode(), settings.viewer_token.encode()
        ):
            return "viewer"
        raise HTTPException(401, "Invalid credentials")

    def admin(role=Depends(identity)):
        if role != "admin":
            raise HTTPException(403, "Administrator required")
        return role

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/v1/status", dependencies=[Depends(identity)])
    def status():
        try:
            killed = app.state.store.killed()
        except Exception:
            raise HTTPException(503, "Safety state unavailable") from None
        return {
            "mode": settings.mode,
            "kill_switch": killed,
            "live_enabled": False,
            "broker_execution_enabled": False,
            "ai_provider_status": "not_configured",
        }

    @app.get("/v1/agents", dependencies=[Depends(identity)])
    def agents():
        active = {"technical_analysis", "market_regime", "security_reliability"}
        return [
            {"role": role, "implementation": "local_task" if role in active else "planned"}
            for role in AGENT_ROLES
        ]

    @app.post("/v1/research/run", dependencies=[Depends(admin)])
    async def research(snapshot: Snapshot):
        return await Orchestrator(app.state.store).run(snapshot)

    @app.post("/v1/research/backtest", dependencies=[Depends(admin)])
    def backtest(request: BacktestRequest):
        try:
            return persist_backtest(app.state.store, request)
        except ResearchConflict as error:
            raise HTTPException(409, str(error)) from None

    @app.post("/v1/research/validate", dependencies=[Depends(admin)])
    def validate(request: ValidationRequest):
        try:
            return persist_validation(app.state.store, request)
        except (HoldoutConflict, ResearchConflict) as error:
            raise HTTPException(409, str(error)) from None

    @app.post("/v1/risk/preview", dependencies=[Depends(admin)])
    def risk(proposal: Proposal):
        result = Orchestrator(app.state.store).preview(proposal)
        app.state.store.audit("admin", "risk.preview", result)
        return result

    @app.put("/v1/safety/kill-switch")
    def kill(request: KillRequest, actor=Depends(admin)):
        app.state.store.set_kill(request.enabled, actor)
        return {"enabled": request.enabled, "execution_allowed": False}

    @app.get("/v1/memory/{environment}", dependencies=[Depends(identity)])
    def memory(environment: Literal["historical", "virtual", "demo"]):
        return app.state.store.records(environment)

    @app.get("/v1/market/feeds", dependencies=[Depends(identity)])
    def feeds():
        return app.state.market.statuses()

    @app.get("/v1/market/events", dependencies=[Depends(identity)])
    def events(
        feed: str = Query(min_length=1, max_length=160),
        symbol: str = Query(min_length=1, max_length=64),
        kind: Literal["quote", "candle", "contract"] = "quote",
        limit: int = Query(default=100, ge=1, le=500),
        timeframe: Literal["M1", "M5", "M10", "M15", "M30", "H1", "H4", "D1"] | None = None,
    ):
        return app.state.market.events(feed, symbol, kind, limit, timeframe)

    return app
