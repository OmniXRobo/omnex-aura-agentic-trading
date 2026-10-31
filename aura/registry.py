"""Immutable research lineage and review requests; no deployment or trading authority."""

import hashlib
import json
import time
from typing import Literal

from pydantic import Field

from .market import MarketModel


class StrategyVersion(MarketModel):
    version_id: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_.-]+$')
    strategy_id: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_.-]+$')
    parent_version: str | None = Field(default=None, min_length=1, max_length=64)
    symbol: Literal['XAUUSD'] = 'XAUUSD'
    family: Literal['trend', 'momentum', 'breakout', 'mean_reversion', 'volatility', 'market_structure', 'ml', 'macro', 'hybrid']
    hypothesis: str = Field(min_length=10, max_length=2000)
    entry_method: str = Field(min_length=10, max_length=2000)
    exit_method: str = Field(min_length=10, max_length=2000)
    cost_assumptions: str = Field(min_length=10, max_length=2000)
    risk_percent: float = Field(gt=0, le=.25)
    sizing: Literal['fixed_risk_no_loss_recovery'] = 'fixed_risk_no_loss_recovery'


class RegistryAction(MarketModel):
    operation_id: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_.-]+$')
    expected_revision: int = Field(strict=True, ge=1)
    action: Literal['attach_evidence', 'request_review', 'suspend', 'archive', 'annotate']
    reason: str = Field(min_length=10, max_length=2000)
    record_id: str | None = Field(default=None, min_length=1, max_length=64)


class RegistryConflict(ValueError):
    pass


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


SCHEMA = '''
CREATE TABLE IF NOT EXISTS strategy_versions (
 id TEXT PRIMARY KEY, strategy TEXT NOT NULL, parent TEXT,
 spec TEXT NOT NULL, digest TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS strategy_events (
 version TEXT NOT NULL REFERENCES strategy_versions(id), revision INTEGER NOT NULL,
 operation TEXT UNIQUE NOT NULL, request TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(version,revision));
'''


class StrategyRegistry:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.executescript(SCHEMA)
            for table in ('strategy_versions', 'strategy_events'):
                for action in ('UPDATE', 'DELETE'):
                    db.execute(f'CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} '
                               f"BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'append only'); END")

    @staticmethod
    def _read(db, identifier):
        row = db.execute('SELECT * FROM strategy_versions WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise RegistryConflict('Unknown strategy version')
        if digest(row['spec']) != row['digest']:
            raise RegistryConflict('Strategy specification integrity failure')
        events = [json.loads(r[0]) for r in db.execute(
            'SELECT payload FROM strategy_events WHERE version=? ORDER BY revision', (identifier,))]
        if not events or [e['revision'] for e in events] != list(range(1, len(events)+1)):
            raise RegistryConflict('Strategy history integrity failure')
        for event in events:
            if event.get('record_id'):
                record = db.execute('SELECT kind,payload FROM records WHERE id=?', (event['record_id'],)).fetchone()
                if record is None or record['kind'] != event['record_kind'] or digest(record['payload']) != event['record_digest']:
                    raise RegistryConflict('Referenced research evidence changed or disappeared')
        return dict(spec=json.loads(row['spec']), spec_digest=row['digest'], revision=len(events),
                    state=events[-1]['state'], events=events, execution_allowed=False,
                    promotion_allowed=False, evidence_interpretation='references_only_not_strategy_validation')

    def create(self, spec, actor='local-operator'):
        payload = encoded(spec.model_dump(mode='json'))
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT spec FROM strategy_versions WHERE id=?', (spec.version_id,)).fetchone()
            if row:
                if row[0] != payload:
                    raise RegistryConflict('Version ID already has a different immutable specification')
                return self._read(db, spec.version_id)
            if spec.parent_version:
                parent = self._read(db, spec.parent_version)
                if parent['spec']['strategy_id'] != spec.strategy_id:
                    raise RegistryConflict('Parent must belong to the same strategy')
            db.execute('INSERT INTO strategy_versions VALUES (?,?,?,?,?,?)',
                       (spec.version_id, spec.strategy_id, spec.parent_version, payload, digest(payload), time.time()))
            event = dict(revision=1, action='created', state='draft', reason='Research candidate registered',
                         created_msc=int(time.time()*1000), actor=actor)
            db.execute('INSERT INTO strategy_events VALUES (?,1,?,?,?)',
                       (spec.version_id, 'created:'+spec.version_id, payload, encoded(event)))
            self._audit(db, actor, 'strategy.created', spec.version_id)
            return self._read(db, spec.version_id)

    @staticmethod
    def _audit(db, actor, action, identifier):
        db.execute('INSERT INTO audit(actor,action,payload,created) VALUES (?,?,?,?)',
                   (actor, action, encoded(dict(version_id=identifier)), time.time()))

    def apply(self, identifier, request, actor='local-operator'):
        serialized = encoded(dict(version=identifier, request=request.model_dump(mode='json')))
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT request FROM strategy_events WHERE operation=?',
                                  (request.operation_id,)).fetchone()
            if previous:
                if previous[0] != serialized:
                    raise RegistryConflict('Operation ID reused with different input')
                return self._read(db, identifier)
            current = self._read(db, identifier)
            if current['revision'] != request.expected_revision:
                raise RegistryConflict('Stale strategy revision')
            if current['revision'] >= 100:
                raise RegistryConflict('History limit reached; register a child version')
            state = current['state']
            if state == 'archived':
                raise RegistryConflict('Archived versions are immutable; register a child version')
            event = dict(revision=current['revision']+1, action=request.action, state=state,
                         reason=request.reason, actor=actor, created_msc=int(time.time()*1000))
            if request.action == 'attach_evidence':
                if state != 'draft' or not request.record_id:
                    raise RegistryConflict('Evidence attachment requires a draft and saved research record')
                record = db.execute('SELECT kind,payload FROM records WHERE id=?', (request.record_id,)).fetchone()
                if record is None or record['kind'] not in ('backtest', 'validation'):
                    raise RegistryConflict('Only saved historical backtest/validation references are supported')
                if any(e.get('record_id') == request.record_id for e in current['events']):
                    raise RegistryConflict('Evidence reference already attached')
                event.update(record_id=request.record_id, record_kind=record['kind'],
                             record_digest=digest(record['payload']))
            elif request.record_id is not None:
                raise RegistryConflict('Record ID is only accepted for evidence attachment')
            if request.action == 'request_review':
                kinds = {e.get('record_kind') for e in current['events']}
                if state != 'draft' or not {'backtest', 'validation'} <= kinds:
                    raise RegistryConflict('Review requires draft with backtest and validation references')
                event['state'] = 'review_requested'
            elif request.action == 'suspend':
                event['state'] = 'suspended'
            elif request.action == 'archive':
                event['state'] = 'archived'
            db.execute('INSERT INTO strategy_events VALUES (?,?,?,?,?)',
                       (identifier, event['revision'], request.operation_id, serialized, encoded(event)))
            self._audit(db, actor, 'strategy.'+request.action, identifier)
            return self._read(db, identifier)

    def get(self, identifier):
        with self.store.connect() as db:
            return self._read(db, identifier)

    def list(self, limit=20):
        if not 1 <= limit <= 100:
            raise ValueError('Limit must be 1–100')
        with self.store.connect() as db:
            ids = [r[0] for r in db.execute('SELECT id FROM strategy_versions ORDER BY created DESC,id LIMIT ?', (limit,))]
            return [{key: value for key, value in self._read(db, identifier).items() if key != "events"}
                    for identifier in ids]
