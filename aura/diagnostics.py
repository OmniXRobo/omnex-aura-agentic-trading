"""Deterministic virtual evidence triage. No causal claims, mutation or promotion."""

import hashlib
import json
import time
from decimal import Decimal

POLICY = 'virtual-triage-v1'
SCHEMA = '''
CREATE TABLE IF NOT EXISTS virtual_diagnostics (
 source_row INTEGER PRIMARY KEY, session TEXT NOT NULL, days INTEGER NOT NULL,
 end_msc INTEGER NOT NULL, source_digest TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS virtual_diagnostic_cursor (
 id INTEGER PRIMARY KEY CHECK(id=1), source_row INTEGER NOT NULL);
INSERT OR IGNORE INTO virtual_diagnostic_cursor VALUES (1,0);
INSERT OR IGNORE INTO schema_version VALUES (10);
'''


class DiagnosticError(ValueError):
    pass


def hash_payload(payload):
    return hashlib.sha256(payload.encode()).hexdigest()


def exists(db, table):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def parse_payload(raw):
    try:
        result = json.loads(raw)
    except (ValueError, TypeError):
        raise DiagnosticError('Invalid diagnostic or evaluation JSON') from None
    if not isinstance(result, dict):
        raise DiagnosticError('Diagnostic or evaluation object required')
    return result


def triage(report):
    if (not isinstance(report, dict) or not isinstance(report.get('session'), str)
            or not 1 <= len(report['session']) <= 64):
        raise DiagnosticError('Invalid evaluation session')
    for flag in ('execution_allowed', 'entries_enabled', 'promotion_allowed'):
        if report.get(flag) is not False:
            raise DiagnosticError('Evaluation evidence has unsupported authority flags')
    for key in ('days', 'start_msc', 'end_msc', 'evaluated_at_msc', 'closed_trades',
                'wins', 'losses', 'flat_trades', 'quote_events'):
        if type(report.get(key)) is not int or report[key] < 0:
            raise DiagnosticError('Invalid evaluation counts or timestamps')
    if (report['days'] not in (2, 3) or report['end_msc']-report['start_msc'] != report['days']*86400000
            or report['evaluated_at_msc'] < report['end_msc']
            or report['wins']+report['losses']+report['flat_trades'] != report['closed_trades']
            or report['closed_trades'] > report['quote_events']):
        raise DiagnosticError('Inconsistent evaluation window or counts')
    if report.get('source') not in ('fixture', 'demo_observation'):
        raise DiagnosticError('Unsupported evaluation source')
    flags = report.get('quality_flags')
    if not isinstance(flags, list) or len(flags) > 30 or any(not isinstance(f, str) or len(f) > 100 for f in flags):
        raise DiagnosticError('Invalid evaluation quality flags')
    numbers = {}
    for key in ('net_closed_pnl', 'closed_trade_commission', 'closed_trade_swap_debits',
                'observed_max_drawdown', 'opening_equity', 'ending_equity'):
        value = report.get(key)
        if isinstance(value, bool) or not isinstance(value, (str, int, float)) or len(str(value)) > 100:
            raise DiagnosticError('Invalid evaluation financial evidence')
        try:
            number = Decimal(str(value))
        except Exception:
            raise DiagnosticError('Invalid evaluation financial evidence') from None
        if not number.is_finite():
            raise DiagnosticError('Nonfinite evaluation financial evidence')
        numbers[key] = number
    if any(numbers[k] < 0 for k in ('closed_trade_commission', 'closed_trade_swap_debits', 'observed_max_drawdown')):
        raise DiagnosticError('Negative costs or drawdown')
    if report['closed_trades'] == 0 and numbers['net_closed_pnl'] != 0:
        raise DiagnosticError('Closed P/L without closed trades')
    findings = []
    def add(code, explanation, follow_up):
        findings.append(dict(code=code, explanation=explanation, follow_up=follow_up))
    if report['source'] == 'fixture':
        add('synthetic_evidence', 'This report uses synthetic fixture evidence.', 'Collect separately labelled demo observations before forward-performance claims.')
    if 'nonpositive_opening_equity' in flags or numbers['opening_equity'] <= 0:
        add('accounting_review', 'Opening equity is nonpositive.', 'Review accounting inputs in isolation; do not increase risk.')
    if not report['quote_events'] or 'no_observations' in flags:
        add('no_observations', 'No quote observations support this window.', 'Check collector/consumer status and market session coverage.')
    if 'insufficient_closed_trades' in flags:
        add('insufficient_sample', 'The evaluator reports fewer closed trades than its configured minimum.', 'Continue observation; do not optimize after a few losses.')
    for flag in ('source_data_gaps_cumulative', 'late_evidence_after_prior_report',
                 'mixed_strategy_versions', 'sparse_or_closed_market_observation',
                 'position_crosses_window_boundary'):
        if flag in flags:
            add(flag, 'The source evaluator flagged '+flag.replace('_', ' ')+'.',
                'Review the original window and source evidence; do not infer a market cause or sum overlapping windows.')
    if report['closed_trades'] and numbers['net_closed_pnl'] < 0:
        add('negative_net_pnl', 'Net closed P/L is negative after the evaluator cost accounting.',
            'Review fills, costs and strategy hypotheses; test candidates on fresh disjoint OOS evidence before shadow trials.')
    if numbers['closed_trade_commission'] > 0 or numbers['closed_trade_swap_debits'] > 0:
        add('costs_present', 'Closed trades include commission or swap debits.',
            'Check broker-specific assumptions; these debits alone do not establish the cause of losses.')
    known = {'diagnostic_only', 'market_session_coverage_unverified', 'nonpositive_opening_equity',
             'no_observations', 'insufficient_closed_trades', 'source_data_gaps_cumulative',
             'late_evidence_after_prior_report', 'mixed_strategy_versions',
             'sparse_or_closed_market_observation', 'position_crosses_window_boundary'}
    if set(flags)-known:
        add('unrecognized_quality_flag', 'The evaluator contains an unsupported quality flag.',
            'Review diagnostic compatibility before interpreting the report.')
    if not findings:
        add('diagnostic_evidence_only', 'No supported triage condition was identified.',
            'Continue independent research validation; this is not approval or a forecast.')
    return dict(policy_version=POLICY, source=report['source'], session=report['session'],
        days=report['days'], end_msc=report['end_msc'], findings=findings,
        conclusion='research_review_only', causal_diagnosis='not_established', statistical_drift='not_tested',
        limitations=['Overlapping windows are not independent samples.',
                     'Market session coverage, regime attribution and strategy/evidence semantic matching are unverified.'],
        strategy_changes_applied=False, risk_changes_applied=False, promotion_allowed=False,
        entries_enabled=False, execution_allowed=False)


def read_diagnostics(store, limit=20):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Limit must be 1–100')
    with store.connect('virtual') as db:
        if not exists(db, 'virtual_diagnostics'):
            return []
        result = []
        for row in db.execute('SELECT source_row,source_digest,payload FROM virtual_diagnostics ORDER BY source_row DESC LIMIT ?', (limit,)):
            source = db.execute('SELECT payload FROM virtual_eval_reports WHERE rowid=?', (row[0],)).fetchone()
            if source is None or hash_payload(source[0]) != row[1]:
                raise DiagnosticError('Original evaluation evidence changed or disappeared')
            payload = parse_payload(row[2])
            if payload.get('policy_version') != POLICY or payload != triage(parse_payload(source[0])):
                raise DiagnosticError('Diagnostic interpretation integrity failure')
            result.append(payload | dict(source_digest=row[1]))
        return result


class VirtualDiagnostics:
    def __init__(self, store):
        self.store = store
        with store.connect('virtual') as db:
            db.executescript(SCHEMA)
            for action in ('UPDATE', 'DELETE'):
                db.execute(f'CREATE TRIGGER IF NOT EXISTS virtual_diagnostics_no_{action.lower()} '
                           f"BEFORE {action} ON virtual_diagnostics BEGIN SELECT RAISE(ABORT,'append only'); END")

    def run_batch(self, limit=10):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Batch must be 1–100')
        self.store.killed()  # Fail closed on missing safety state; never clear it.
        with self.store.connect('virtual') as db:
            db.execute('BEGIN IMMEDIATE')
            if not exists(db, 'virtual_eval_reports'):
                return dict(created=0, state='no_evaluations', execution_allowed=False)
            cursor = db.execute('SELECT source_row FROM virtual_diagnostic_cursor WHERE id=1').fetchone()
            if cursor is None:
                raise DiagnosticError('Missing diagnostic cursor')
            rows = list(db.execute('SELECT rowid,session,days,end_msc,payload FROM virtual_eval_reports WHERE rowid>? ORDER BY rowid LIMIT ?', (cursor[0], limit)))
            for row in rows:
                report = parse_payload(row[4])
                if (report.get('session'), report.get('days'), report.get('end_msc')) != tuple(row[1:4]):
                    raise DiagnosticError('Evaluation identity mismatch')
                payload = triage(report)
                db.execute('INSERT INTO virtual_diagnostics VALUES (?,?,?,?,?,?)',
                    (row[0], row[1], row[2], row[3], hash_payload(row[4]), json.dumps(payload, sort_keys=True, allow_nan=False)))
                db.execute('UPDATE virtual_diagnostic_cursor SET source_row=? WHERE id=1', (row[0],))
                db.execute('INSERT INTO audit(actor,action,payload,created) VALUES (?,?,?,?)',
                    ('virtual-diagnostics', 'diagnostic.created', json.dumps(dict(session=row[1], days=row[2], end_msc=row[3])), time.time()))
            return dict(created=len(rows), state='batch_processed' if rows else 'caught_up', execution_allowed=False)
