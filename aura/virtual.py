"""Persistent single-instrument virtual market ledger. No broker/provider interface."""

import hashlib
import json
import time
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from .market import GoldContract, MarketModel, Quote
from .store import Store

D = Decimal


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)


class VirtualConfig(MarketModel):
    evidence_source: Literal["fixture", "demo_observation"]
    initial_cash: D = Field(default=D("10000"), ge=100, le=100000000)
    max_risk_fraction: D = Field(default=D("0.0025"), gt=0, le=D("0.0025"))
    max_drawdown_fraction: D = Field(default=D("0.05"), gt=0, le=D("0.10"))
    max_spread: D = Field(default=D("0.5"), gt=0, le=100)
    commission_per_lot_side: D = Field(ge=0, le=1000)
    slippage_price: D = Field(ge=0, le=100)
    swap_debit_per_lot_utc_day: D = Field(ge=0, le=10000)


class VirtualIntent(MarketModel):
    intent_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    strategy_version: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=500)
    side: Literal["buy", "sell"]
    volume: D = Field(gt=0, le=1000)
    stop_loss: D = Field(gt=0, le=10000000)
    take_profit: D = Field(gt=0, le=10000000)
    created_msc: int = Field(strict=True, gt=0)
    expires_msc: int = Field(strict=True, gt=0)
    news_blackout: bool = True

    @model_validator(mode="after")
    def lifetime(self):
        if not 0 < self.expires_msc - self.created_msc <= 60000:
            raise ValueError("Virtual intent must expire within 60 seconds")
        return self


SCHEMA = """
CREATE TABLE IF NOT EXISTS virtual_sessions (
 id TEXT PRIMARY KEY, config TEXT NOT NULL, state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS virtual_receipts (
 session TEXT NOT NULL, key TEXT NOT NULL, digest TEXT NOT NULL, result TEXT NOT NULL,
 PRIMARY KEY(session,key));
CREATE TABLE IF NOT EXISTS virtual_intents (
 session TEXT NOT NULL, intent_id TEXT NOT NULL, PRIMARY KEY(session,intent_id));
CREATE TRIGGER IF NOT EXISTS virtual_intents_no_delete BEFORE DELETE ON virtual_intents
 BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TRIGGER IF NOT EXISTS virtual_intents_no_update BEFORE UPDATE ON virtual_intents
 BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TABLE IF NOT EXISTS virtual_events (
 id INTEGER PRIMARY KEY, session TEXT NOT NULL, key TEXT NOT NULL,
 payload TEXT NOT NULL, UNIQUE(session,key));
CREATE TRIGGER IF NOT EXISTS virtual_events_no_update BEFORE UPDATE ON virtual_events
 BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TRIGGER IF NOT EXISTS virtual_events_no_delete BEFORE DELETE ON virtual_events
 BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TRIGGER IF NOT EXISTS virtual_receipts_no_update BEFORE UPDATE ON virtual_receipts
 BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TRIGGER IF NOT EXISTS virtual_receipts_no_delete BEFORE DELETE ON virtual_receipts
 BEGIN SELECT RAISE(ABORT,'append only'); END;
INSERT OR IGNORE INTO schema_version VALUES (7);
"""


class VirtualLedger:
    def __init__(self, store: Store, session: str, config: VirtualConfig,
                 contract: GoldContract, clock=None):
        if not session or len(session) > 64:
            raise ValueError("A bounded virtual session ID is required")
        self.store, self.session, self.config, self.contract = store, session, config, contract
        self.clock = clock or (lambda: int(time.time() * 1000))
        configuration = encode(dict(config=json.loads(config.model_dump_json()),
                                    contract=json.loads(contract.model_dump_json())))
        state = dict(cash=str(config.initial_cash), equity=str(config.initial_cash),
                     peak_equity=str(config.initial_cash), halted=False, position=None,
                     last_time_msc=0, closed_trades=0)
        with store.connect("virtual") as db:
            db.executescript(SCHEMA)
            db.execute("INSERT OR IGNORE INTO virtual_sessions VALUES (?,?,?)",
                       (session, configuration, encode(state)))
            saved = db.execute("SELECT config FROM virtual_sessions WHERE id=?", (session,)).fetchone()
            if saved[0] != configuration:
                raise ValueError("Session contract/cost/risk/source configuration is immutable")

    def snapshot(self):
        with self.store.connect("virtual") as db:
            state = json.loads(db.execute("SELECT state FROM virtual_sessions WHERE id=?",
                                          (self.session,)).fetchone()[0])
        return state | {"environment": "virtual", "execution_allowed": False,
                        "evidence_source": self.config.evidence_source}

    def events(self):
        with self.store.connect("virtual") as db:
            return [json.loads(row[0]) for row in db.execute(
                "SELECT payload FROM virtual_events WHERE session=? ORDER BY id", (self.session,))]

    def apply(self, key: str, quote: Quote, intent: VirtualIntent | None = None):
        """One atomic quote step; exact retry returns its original receipt even after restart."""
        if not key or len(key) > 128:
            raise ValueError("A bounded idempotency key is required")
        request = encode(dict(quote=json.loads(quote.model_dump_json()),
                              intent=None if intent is None else json.loads(intent.model_dump_json())))
        digest = hashlib.sha256(request.encode()).hexdigest()
        with self.store.connect("virtual") as db:
            db.execute("BEGIN IMMEDIATE")
            saved = db.execute("SELECT digest,result FROM virtual_receipts WHERE session=? AND key=?",
                               (self.session, key)).fetchone()
            if saved:
                if saved[0] != digest:
                    raise ValueError("Idempotency key reused with different input")
                return json.loads(saved[1])
            quote.require_fresh(self.clock())
            if quote.symbol != self.contract.symbol:
                raise ValueError("Quote does not match the immutable instrument contract")
            state = json.loads(db.execute("SELECT state FROM virtual_sessions WHERE id=?",
                                          (self.session,)).fetchone()[0])
            if quote.time_msc < state["last_time_msc"]:
                raise ValueError("Out-of-order quote")
            state["last_time_msc"] = quote.time_msc
            bid, ask = D(str(quote.bid)), D(str(quote.ask))
            cash = D(state["cash"])
            position, action, details = state["position"], "observed", {}
            cfg = self.config
            if position is not None:
                volume, entry = D(position["volume"]), D(position["entry"])
                rollover = max(0, quote.time_msc // 86400000 - position["entry_utc_day"])
                total_swap = volume * cfg.swap_debit_per_lot_utc_day * rollover
                cash -= total_swap - D(position["swap_paid"])
                position["swap_paid"] = str(total_swap)
                buy = position["side"] == "buy"
                exit_price = bid - cfg.slippage_price if buy else ask + cfg.slippage_price
                if exit_price <= 0:
                    raise ValueError("Nonpositive simulated exit price")
                pnl = (exit_price - entry) * volume * D(str(self.contract.trade_contract_size))
                if not buy:
                    pnl = -pnl
                stop = bid <= D(position["stop_loss"]) if buy else ask >= D(position["stop_loss"])
                target = bid >= D(position["take_profit"]) if buy else ask <= D(position["take_profit"])
                exit_fee = volume * cfg.commission_per_lot_side
                state["equity"] = str(cash + pnl - exit_fee)
                if stop or target:
                    cash += pnl - exit_fee
                    state["equity"] = str(cash)
                    action = "stop_loss" if stop else "take_profit"
                    details = dict(position=position, exit_price=str(exit_price), gross_pnl=str(pnl),
                                   net_pnl=str(pnl - exit_fee - D(position["entry_commission"])
                                               - total_swap), exit_commission=str(exit_fee))
                    state["position"] = None
                    state["closed_trades"] += 1
            else:
                state["equity"] = str(cash)
            peak = max(D(state["peak_equity"]), D(state["equity"]))
            state["peak_equity"] = str(peak)
            if D(state["equity"]) <= peak * (1 - cfg.max_drawdown_fraction):
                state["halted"] = True
            if intent is not None:
                # Never open another position on a quote which already managed a position.
                reasons = []
                if position is not None:
                    reasons.append("position_was_active")
                if not intent.created_msc <= quote.time_msc <= intent.expires_msc:
                    reasons.append("intent_time_invalid")
                if intent.news_blackout:
                    reasons.append("news_blackout")
                if state["halted"]:
                    reasons.append("drawdown_halt")
                try:
                    if self.store.killed():
                        reasons.append("emergency_stop")
                except Exception:
                    reasons.append("safety_state_unavailable")
                if ask - bid > cfg.max_spread:
                    reasons.append("spread_limit")
                volume = intent.volume
                minimum, maximum, step = (D(str(getattr(self.contract, field))) for field in
                                         ("volume_min", "volume_max", "volume_step"))
                if not minimum <= volume <= maximum or volume % step:
                    reasons.append("volume_constraints")
                buy = intent.side == "buy"
                entry = ask + cfg.slippage_price if buy else bid - cfg.slippage_price
                valid = (intent.stop_loss < entry < intent.take_profit if buy
                         else intent.take_profit < entry < intent.stop_loss)
                # Stops must also lie beyond the current closing side of the quote.
                if not valid or (intent.stop_loss >= bid if buy else intent.stop_loss <= ask):
                    reasons.append("stop_geometry")
                stop_distance = D(str(self.contract.trade_stops_level)) * D(str(self.contract.point))
                if (abs((bid if buy else ask) - intent.stop_loss) < stop_distance
                        or abs(intent.take_profit - (bid if buy else ask)) < stop_distance):
                    reasons.append("minimum_stop_distance")
                cost = volume * cfg.commission_per_lot_side
                planned_loss = (abs(entry - intent.stop_loss) + cfg.slippage_price) * volume * D(
                    str(self.contract.trade_contract_size)) + 2 * cost
                if cash <= 0 or planned_loss > cash * cfg.max_risk_fraction:
                    reasons.append("risk_limit")
                # Intent ID is durable independently of the transport idempotency key.
                consumed = db.execute(
                    "SELECT 1 FROM virtual_intents WHERE session=? AND intent_id=?",
                    (self.session, intent.intent_id)).fetchone()
                if consumed:
                    reasons.append("intent_already_consumed")
                db.execute("INSERT OR IGNORE INTO virtual_intents VALUES (?,?)",
                           (self.session, intent.intent_id))
                if reasons:
                    details["entry_rejected"] = reasons
                    if action == "observed":
                        action = "entry_rejected"
                else:
                    cash -= cost
                    state["position"] = json.loads(intent.model_dump_json()) | dict(
                        entry=str(entry), entry_commission=str(cost), swap_paid="0",
                        entry_utc_day=quote.time_msc // 86400000, entry_time_msc=quote.time_msc)
                    liquidation = bid - cfg.slippage_price if buy else ask + cfg.slippage_price
                    initial_pnl = (liquidation - entry) * volume * D(str(self.contract.trade_contract_size))
                    if not buy:
                        initial_pnl = -initial_pnl
                    state["equity"] = str(cash + initial_pnl - cost)
                    action, details = "opened", dict(position=state["position"], planned_loss=str(planned_loss))
            if D(state["equity"]) <= D(state["peak_equity"]) * (1 - cfg.max_drawdown_fraction):
                state["halted"] = True
            state["cash"] = str(cash)
            result = dict(action=action, details=details, state=state, environment="virtual",
                          execution_allowed=False, evidence_source=cfg.evidence_source,
                          market_quote=json.loads(quote.model_dump_json()),
                          intent=None if intent is None else json.loads(intent.model_dump_json()),
                          input_digest=digest)
            encoded = encode(result)
            db.execute("UPDATE virtual_sessions SET state=? WHERE id=?", (encode(state), self.session))
            db.execute("INSERT INTO virtual_receipts VALUES (?,?,?,?)",
                       (self.session, key, digest, encoded))
            db.execute("INSERT INTO virtual_events(session,key,payload) VALUES (?,?,?)",
                       (self.session, key, encoded))
            return json.loads(encoded)
