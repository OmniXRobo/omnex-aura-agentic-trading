"""Durable rolling virtual diagnostics. Reports never promote, arm or mutate trading."""

import hashlib
import json
import time
from decimal import Decimal as D

from pydantic import Field, model_validator

from .market import MarketModel, Quote
from .store import Store
from .virtual import encode

DAY = 86400000


class EvaluationPlan(MarketModel):
    session: str = Field(min_length=1, max_length=64)
    anchor_msc: int = Field(strict=True, gt=0)
    windows_days: tuple[int, ...] = (2, 3)
    stride_days: int = Field(default=1, strict=True, ge=1, le=3)
    grace_seconds: int = Field(default=60, strict=True, ge=5, le=3600)
    min_closed_trades: int = Field(default=20, strict=True, ge=1, le=10000)

    @model_validator(mode="after")
    def periods(self):
        if not self.windows_days or tuple(sorted(set(self.windows_days))) != self.windows_days:
            raise ValueError("Window lengths must be unique and increasing")
        if any(type(day) is not int or day not in (2, 3) for day in self.windows_days):
            raise ValueError("Only two/three-day diagnostic windows are supported")
        return self


SCHEMA = """
CREATE TABLE IF NOT EXISTS virtual_eval_plans (
 session TEXT PRIMARY KEY, config TEXT NOT NULL, source_config TEXT NOT NULL,
 last_checked_msc INTEGER NOT NULL, indexed_id INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS virtual_eval_due (
 session TEXT NOT NULL, days INTEGER NOT NULL, end_msc INTEGER NOT NULL,
 PRIMARY KEY(session,days));
CREATE TABLE IF NOT EXISTS virtual_eval_index (
 event_id INTEGER PRIMARY KEY, session TEXT NOT NULL, time_msc INTEGER NOT NULL,
 digest TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS virtual_eval_time ON virtual_eval_index(session,time_msc,event_id);
CREATE TABLE IF NOT EXISTS virtual_eval_reports (
 session TEXT NOT NULL, days INTEGER NOT NULL, end_msc INTEGER NOT NULL,
 payload TEXT NOT NULL, PRIMARY KEY(session,days,end_msc));
CREATE TABLE IF NOT EXISTS virtual_eval_late_events (
 session TEXT NOT NULL, event_id INTEGER NOT NULL, time_msc INTEGER NOT NULL,
 reported_end_msc INTEGER NOT NULL, PRIMARY KEY(session,event_id));
INSERT OR IGNORE INTO schema_version VALUES (9);
"""


class VirtualEvaluator:
    def __init__(self, store: Store, plan: EvaluationPlan):
        self.store, self.plan = store, plan
        with store.connect("virtual") as db:
            # Do not initialize or arm a ledger when the session is absent.
            if not db.execute("SELECT name FROM sqlite_master WHERE name='virtual_sessions'").fetchone():
                raise ValueError("Create a virtual session before its evaluation plan")
            source = db.execute("SELECT config FROM virtual_sessions WHERE id=?", (plan.session,)).fetchone()
            if source is None:
                raise ValueError("Unknown virtual session")
            db.executescript(SCHEMA)
            for table in ("virtual_eval_reports", "virtual_eval_index", "virtual_eval_late_events"):
                for operation in ("UPDATE", "DELETE"):
                    db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} "
                               f"BEFORE {operation} ON {table} "
                               "BEGIN SELECT RAISE(ABORT,'append only'); END")
            db.execute("BEGIN IMMEDIATE")
            saved = db.execute("SELECT config,source_config FROM virtual_eval_plans WHERE session=?",
                               (plan.session,)).fetchone()
            encoded = plan.model_dump_json()
            if saved and (saved[0] != encoded or saved[1] != source[0]):
                raise ValueError("Evaluation plan and session configuration are immutable")
            if not saved:
                db.execute("INSERT INTO virtual_eval_plans VALUES (?,?,?,0,0)",
                           (plan.session, encoded, source[0]))
                for days in plan.windows_days:
                    db.execute("INSERT INTO virtual_eval_due VALUES (?,?,?)",
                               (plan.session, days, plan.anchor_msc + days * DAY))

    @staticmethod
    def _number(value):
        result = D(str(value))
        if not result.is_finite():
            raise ValueError("Nonfinite virtual accounting evidence")
        return result

    def _event(self, raw):
        event = json.loads(raw)
        quote = Quote.model_validate(event["market_quote"])
        request = encode(dict(quote=json.loads(quote.model_dump_json()), intent=event["intent"]))
        if hashlib.sha256(request.encode()).hexdigest() != event["input_digest"]:
            raise ValueError("Virtual input evidence digest mismatch")
        for field in ("equity", "cash"):
            self._number(event["state"][field])
        if event["environment"] != "virtual" or event["execution_allowed"] is not False:
            raise ValueError("Wrong evidence environment")
        return quote.time_msc, event

    def _index(self, db, saved, limit):
        if saved["indexed_id"]:
            checkpoint = db.execute(
                "SELECT e.payload,i.digest FROM virtual_events e JOIN virtual_eval_index i "
                "ON e.id=i.event_id WHERE e.id=? AND e.session=? AND i.session=?",
                (saved["indexed_id"], self.plan.session, self.plan.session),
            ).fetchone()
            if checkpoint is None or hashlib.sha256(checkpoint[0].encode()).hexdigest() != checkpoint[1]:
                raise ValueError("Evaluation evidence checkpoint missing or changed")
        rows = db.execute("SELECT id,payload FROM virtual_events WHERE session=? AND id>? "
                          "ORDER BY id LIMIT ?", (self.plan.session, saved["indexed_id"], limit + 1)).fetchall()
        end = db.execute("SELECT max(end_msc) FROM virtual_eval_reports WHERE session=?",
                         (self.plan.session,)).fetchone()[0]
        last_id = saved["indexed_id"]
        for row in rows[:limit]:
            stamp, _ = self._event(row["payload"])
            db.execute("INSERT INTO virtual_eval_index VALUES (?,?,?,?)",
                       (row["id"], self.plan.session, stamp, hashlib.sha256(row["payload"].encode()).hexdigest()))
            if end and self.plan.anchor_msc <= stamp < end:
                db.execute("INSERT INTO virtual_eval_late_events VALUES (?,?,?,?)",
                           (self.plan.session, row["id"], stamp, end))
            last_id = row["id"]
        db.execute("UPDATE virtual_eval_plans SET indexed_id=? WHERE session=?", (last_id, self.plan.session))
        return len(rows) > limit, last_id

    def _report(self, db, days, end, now, highwater, source_config):
        start = end - days * DAY
        config = json.loads(source_config)
        initial = self._number(config["config"]["initial_cash"])
        baseline = db.execute("SELECT e.payload,i.digest FROM virtual_eval_index i JOIN virtual_events e "
                              "ON e.id=i.event_id WHERE i.session=? AND i.time_msc<? "
                              "ORDER BY i.time_msc DESC,i.event_id DESC LIMIT 1",
                              (self.plan.session, start)).fetchone()
        opening, position_at_start = initial, False
        if baseline:
            if hashlib.sha256(baseline[0].encode()).hexdigest() != baseline[1]:
                raise ValueError("Indexed baseline evidence changed")
            _, previous = self._event(baseline[0])
            opening = self._number(previous["state"]["equity"])
            position_at_start = previous["state"]["position"] is not None
        equity, peak, drawdown, drawdown_fraction = opening, opening, D(0), D(0)
        trades, wins, losses, events, entry_rejections = 0, 0, 0, 0, 0
        net, gains, loss_total = D(0), D(0), D(0)
        commission, swap = D(0), D(0)
        previous_time, max_gap, first_time, last_time = start, 0, None, None
        position_at_end = position_at_start
        evidence = hashlib.sha256()
        versions = {}
        rows = db.execute("SELECT i.event_id,i.time_msc,i.digest,e.payload FROM virtual_eval_index i "
                          "JOIN virtual_events e ON e.id=i.event_id WHERE i.session=? "
                          "AND i.time_msc>=? AND i.time_msc<? ORDER BY i.time_msc,i.event_id",
                          (self.plan.session, start, end))
        for row in rows:
            if hashlib.sha256(row["payload"].encode()).hexdigest() != row["digest"]:
                raise ValueError("Indexed virtual evidence changed")
            stamp, event = self._event(row["payload"])
            if stamp != row["time_msc"]:
                raise ValueError("Indexed timestamp changed")
            evidence.update(encode([row["event_id"], row["digest"]]).encode())
            events += 1
            first_time = stamp if first_time is None else first_time
            last_time = stamp
            max_gap = max(max_gap, stamp - previous_time)
            previous_time = stamp
            equity = self._number(event["state"]["equity"])
            position_at_end = event["state"]["position"] is not None
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
            if peak > 0:
                drawdown_fraction = max(drawdown_fraction, (peak - equity) / peak)
            if "entry_rejected" in event["details"]:
                entry_rejections += 1
            if event["action"] in ("stop_loss", "take_profit"):
                trade = event["details"]
                pnl = self._number(trade["net_pnl"])
                fee = self._number(trade["exit_commission"]) + self._number(trade["position"]["entry_commission"])
                debit = self._number(trade["position"]["swap_paid"])
                commission += fee
                swap += debit
                trades += 1
                wins += pnl > 0
                losses += pnl < 0
                net += pnl
                gains += max(D(0), pnl)
                loss_total += max(D(0), -pnl)
                version = trade["position"]["strategy_version"]
                group = versions.setdefault(version, dict(closed_trades=0, net_pnl=D(0)))
                group["closed_trades"] += 1
                group["net_pnl"] += pnl
        max_gap = max(max_gap, end - previous_time)
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        gaps = 0
        if "virtual_source_events" in tables:
            gaps = db.execute("SELECT count(*) FROM virtual_source_events WHERE session=? "
                              "AND disposition LIKE 'skipped_%'", (self.plan.session,)).fetchone()[0]
        late = db.execute("SELECT count(*) FROM virtual_eval_late_events WHERE session=?",
                          (self.plan.session,)).fetchone()[0]
        flags = ["diagnostic_only", "market_session_coverage_unverified"]
        if opening <= 0:
            flags.append("nonpositive_opening_equity")
        if not events:
            flags.append("no_observations")
        if trades < self.plan.min_closed_trades:
            flags.append("insufficient_closed_trades")
        if gaps:
            flags.append("source_data_gaps_cumulative")
        if late:
            flags.append("late_evidence_after_prior_report")
        if len(versions) > 1:
            flags.append("mixed_strategy_versions")
        if max_gap > 60000:
            flags.append("sparse_or_closed_market_observation")
        if position_at_start or position_at_end:
            flags.append("position_crosses_window_boundary")
        return json.loads(encode(dict(
            session=self.plan.session, days=days, start_msc=start, end_msc=end,
            evaluated_at_msc=now, event_highwater_id=highwater, evidence_digest=evidence.hexdigest(),
            source=config["config"]["evidence_source"], quote_events=events,
            first_quote_msc=first_time, last_quote_msc=last_time, max_observation_gap_msc=max_gap,
            closed_trades=trades, wins=wins, losses=losses, flat_trades=trades - wins - losses,
            win_rate=None if not trades else D(wins) / trades, net_closed_pnl=net,
            expectancy=None if not trades else net / trades,
            profit_factor=None if not loss_total else gains / loss_total,
            profit_factor_undefined=not bool(loss_total), closed_trade_commission=commission,
            closed_trade_swap_debits=swap, opening_equity=opening, ending_equity=equity,
            equity_change=equity - opening, observed_max_drawdown=drawdown,
            observed_max_drawdown_fraction=drawdown_fraction if peak > 0 else None, entry_rejections=entry_rejections,
            strategy_versions=versions, source_gap_count_cumulative=gaps,
            late_evidence_count_cumulative=late, quality_flags=flags,
            conclusion="review_losses" if trades and net < 0 else "insufficient_or_diagnostic_evidence",
            promotion_allowed=False, entries_enabled=False, execution_allowed=False,
        )))

    def run_due(self, now_msc=None, max_reports=10, index_batch=1000):
        now = int(time.time() * 1000) if now_msc is None else now_msc
        if type(now) is not int or now < self.plan.anchor_msc:
            raise ValueError("Evaluation clock precedes plan anchor")
        if type(max_reports) is not int or not 1 <= max_reports <= 100:
            raise ValueError("Report batch must be one to 100")
        if type(index_batch) is not int or not 1 <= index_batch <= 10000:
            raise ValueError("Index batch must be one to 10000")
        with self.store.connect("virtual") as db:
            db.execute("BEGIN IMMEDIATE")
            saved = db.execute("SELECT * FROM virtual_eval_plans WHERE session=?", (self.plan.session,)).fetchone()
            source = db.execute("SELECT config FROM virtual_sessions WHERE id=?", (self.plan.session,)).fetchone()
            if source is None or saved["source_config"] != source[0]:
                raise ValueError("Session configuration changed")
            if now < saved["last_checked_msc"]:
                raise ValueError("Evaluation clock moved backwards")
            indexing, highwater = self._index(db, saved, index_batch)
            reports = []
            if not indexing:
                for _ in range(max_reports):
                    due = db.execute("SELECT days,end_msc FROM virtual_eval_due WHERE session=? "
                                     "AND end_msc<=? ORDER BY end_msc,days LIMIT 1",
                                     (self.plan.session, now - self.plan.grace_seconds * 1000)).fetchone()
                    if due is None:
                        break
                    report = self._report(db, due[0], due[1], now, highwater, source[0])
                    db.execute("INSERT INTO virtual_eval_reports VALUES (?,?,?,?)",
                               (self.plan.session, due[0], due[1], encode(report)))
                    db.execute("UPDATE virtual_eval_due SET end_msc=? WHERE session=? AND days=?",
                               (due[1] + self.plan.stride_days * DAY, self.plan.session, due[0]))
                    reports.append(report)
            db.execute("UPDATE virtual_eval_plans SET last_checked_msc=? WHERE session=?", (now, self.plan.session))
            late = db.execute("SELECT count(*) FROM virtual_eval_late_events WHERE session=?",
                              (self.plan.session,)).fetchone()[0]
            remaining = db.execute("SELECT min(end_msc) FROM virtual_eval_due WHERE session=?",
                                   (self.plan.session,)).fetchone()[0]
            return dict(state="indexing" if indexing else "checked", reports=reports,
                        next_due_msc=remaining + self.plan.grace_seconds * 1000,
                        late_evidence_count_cumulative=late,
                        execution_allowed=False, promotion_allowed=False)

    def reports(self, limit=20):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Report limit must be one to 100")
        with self.store.connect("virtual") as db:
            rows = db.execute(
                "SELECT payload FROM virtual_eval_reports WHERE session=? ORDER BY end_msc DESC,days DESC LIMIT ?",
                (self.plan.session, limit)).fetchall()
            return [json.loads(row[0]) for row in reversed(rows)]
