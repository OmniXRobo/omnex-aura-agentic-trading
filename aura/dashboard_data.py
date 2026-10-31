"""Bounded dashboard projections. Read existing data without creating trading schemas."""

import json
import time

from .agents import AGENT_ROLES
from .operations import runtime_status


def table_exists(db, name):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def dashboard_overview(store, market, role, version, mode):
    now = int(time.time() * 1000)
    # Missing safety state must never become a green dashboard indicator.
    killed = store.killed()
    with store.connect("historical") as db:
        fixture = db.execute("SELECT 1 FROM records WHERE kind='dashboard_fixture' LIMIT 1").fetchone() is not None
        runs = []
        latest_agents = {}
        for row in db.execute("SELECT payload,created FROM records WHERE kind='agent_run' ORDER BY created DESC LIMIT 5"):
            report = json.loads(row[0])
            runs.append(dict(created_msc=int(row[1] * 1000), signal=report.get("signal", "NO TRADE"),
                             reason=report.get("reason", ""), provider=report.get("provider", "unknown"),
                             source=report.get("source", "unknown")))
            for result in report.get("agents", []):
                latest_agents.setdefault(result.get("agent"), dict(status=result.get("status"),
                                                                  last_run_msc=int(row[1] * 1000)))
        jobs = {row[0]: row[1] for row in db.execute("SELECT state,count(*) FROM jobs GROUP BY state")}
        audit = [dict(actor=row[0], action=row[1], created_msc=int(row[2] * 1000)) for row in db.execute(
            "SELECT actor,action,created FROM audit ORDER BY id DESC LIMIT 10")]
    sessions, evaluations, plans = [], [], []
    with store.connect("virtual") as db:
        if table_exists(db, "virtual_sessions"):
            for row in db.execute("SELECT id,config,state FROM virtual_sessions ORDER BY id LIMIT 20"):
                config, state = json.loads(row[1]), json.loads(row[2])
                position = state.get("position")
                sessions.append(dict(session=row[0], source=config["config"]["evidence_source"],
                                     symbol=config["contract"]["symbol"], cash=state["cash"],
                                     equity=state["equity"], closed_trades=state["closed_trades"],
                                     halted=state["halted"], last_quote_msc=state["last_time_msc"],
                                     position=None if position is None else {
                                         k: position.get(k) for k in ("side", "volume", "entry", "stop_loss", "take_profit", "strategy_version")
                                     }))
        if table_exists(db, "virtual_eval_reports"):
            for row in db.execute("SELECT payload FROM virtual_eval_reports ORDER BY end_msc DESC,days LIMIT 20"):
                data = json.loads(row[0])
                evaluations.append({key: data.get(key) for key in (
                    "session", "days", "start_msc", "end_msc", "evaluated_at_msc", "source",
                    "closed_trades", "wins", "losses", "net_closed_pnl", "expectancy", "profit_factor",
                    "observed_max_drawdown", "quote_events", "max_observation_gap_msc", "quality_flags", "conclusion",
                )} | dict(promotion_allowed=False))
        if table_exists(db, "virtual_eval_due"):
            plans = [dict(session=r[0], days=r[1], next_window_end_msc=r[2]) for r in db.execute(
                "SELECT session,days,end_msc FROM virtual_eval_due ORDER BY end_msc LIMIT 20")]
    implemented = {"technical_analysis", "market_regime", "security_reliability"}
    agents = [dict(role=name, implementation="local_task" if name in implemented else "planned",
                   last_run=latest_agents.get(name)) for name in AGENT_ROLES]
    return dict(version=version, generated_msc=now, role=role, mode=mode,
                fixture_preview=fixture, kill_switch=killed, live_enabled=False,
                broker_execution_enabled=False, dashboard_entries_enabled=False,
                feeds=market.statuses(now)[:20], sessions=sessions, evaluations=evaluations,
                evaluation_plans=plans, agents=agents, recent_research=runs, jobs=jobs, audit=audit,
                limits=dict(sessions=20, evaluations=20, feeds=20),
                storage=dict(directory=str(store.directory.resolve()) if role == "admin" else "configured local directory",
                             market_observations="saved_records_only"),
                operations=runtime_status(store),
                runtime=dict(supervisor="local_polling_runner_available", android="not_built",
                             external_ai="not_integrated", strategy_entries="not_implemented"))
