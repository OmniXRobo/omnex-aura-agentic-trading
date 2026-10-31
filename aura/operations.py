"""Single local polling runner. Research and virtual diagnostics only; no broker API."""

import argparse
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

from .diagnostics import VirtualDiagnostics
from .store import Store
from .virtual_evaluation import EvaluationPlan, VirtualEvaluator
from .worker import process_one


@contextmanager
def directory_lock(directory):
    """OS releases the held lock on process exit; never unlink the lock inode."""
    path = Path(directory) / 'operations.lock'
    with path.open('a+b') as handle:
        if path.stat().st_size == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError('An operations runner already owns this data directory') from None
        try:
            yield
        finally:
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def runtime_status(store, now=None):
    now = time.time() if now is None else now
    with store.connect() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='operations_runtime'").fetchone():
            return dict(state='not_started', heartbeat_msc=None, tasks=[])
        row = db.execute('SELECT payload FROM operations_runtime WHERE id=1').fetchone()
    if row is None:
        return dict(state='unknown', heartbeat_msc=None, tasks=[])
    result = json.loads(row[0])
    age = now - result['heartbeat_msc'] / 1000
    if result['state'] in ('running', 'degraded') and not 0 <= age <= 20:
        result['state'] = 'stale'
    return result


class OperationsRunner:
    def __init__(self, store, evaluators=(), clock=time.time):
        self.store, self.evaluators, self.clock = store, list(evaluators), clock
        self.failures = [0] * len(self.evaluators)
        self.cycles, self.jobs = 0, 0
        self.diagnostics = VirtualDiagnostics(store)
        self.diagnostic_failures = 0
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS operations_runtime (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')

    def publish(self, state):
        payload = dict(state=state, heartbeat_msc=int(self.clock() * 1000), cycles=self.cycles,
                       jobs_processed=self.jobs, execution_allowed=False, entries_enabled=False,
                       tasks=[dict(role='research_queue', state='polling' if state in ('running', 'degraded') else state)] + [
                           dict(role='virtual_evaluation', state=state if state not in ('running', 'degraded') else 'blocked' if failures >= 3 else
                                'retry_pending' if failures else 'polling') for failures in self.failures] + [
                           dict(role='virtual_diagnostics', state=state if state not in ('running', 'degraded') else
                                'blocked' if self.diagnostic_failures >= 3 else
                                'retry_pending' if self.diagnostic_failures else 'polling')])
        with self.store.connect() as db:
            db.execute('INSERT OR REPLACE INTO operations_runtime VALUES (1,?)', (json.dumps(payload),))

    def step(self):
        # Safety read failure terminates this runner; it never clears or repairs the stop.
        self.store.killed()
        if process_one(self.store):
            self.jobs += 1
        for index, evaluator in enumerate(self.evaluators):
            if self.failures[index] >= 3:
                continue
            try:
                evaluator.run_due()
            except Exception:
                # Never persist exception text, paths, credentials or raw evidence.
                self.failures[index] += 1
            else:
                self.failures[index] = 0
        if self.diagnostic_failures < 3:
            try:
                self.diagnostics.run_batch()
            except Exception:
                self.diagnostic_failures += 1
            else:
                self.diagnostic_failures = 0
        self.cycles += 1
        self.publish('degraded' if any(self.failures) or self.diagnostic_failures else 'running')


def main():
    parser = argparse.ArgumentParser(description='Research queue and virtual diagnostic polling; no execution')
    parser.add_argument('--data-dir', type=Path, default=Path(os.getenv('AURA_DATA_DIR', 'data')))
    parser.add_argument('--evaluation-plan', type=Path, action='append', default=[])
    parser.add_argument('--interval', type=float, default=2)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.interval <= 5 or len(args.evaluation_plan) > 10:
        parser.error('Interval must be 1–5 seconds; at most 10 evaluation plans')
    directory = args.data_dir.resolve()
    runner = None
    try:
        # Read and validate all plans before opening a database or changing any state.
        plans = [EvaluationPlan.model_validate_json(path.read_text()) for path in args.evaluation_plan]
        if len({p.session for p in plans}) != len(plans):
            raise ValueError('Duplicate evaluation sessions')
        directory.mkdir(parents=True, exist_ok=True)
        with directory_lock(directory):
            store = Store(directory)
            evaluators = [VirtualEvaluator(store, plan) for plan in plans]
            runner = OperationsRunner(store, evaluators)
            store.audit('operations', 'runner_started', dict(evaluation_plans=len(plans)))
            print('Research/diagnostic runner started. No collector, entries or broker execution.', flush=True)
            try:
                while True:
                    runner.step()
                    if args.once:
                        break
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                pass
            except Exception:
                runner.publish('failed')
                raise
            else:
                runner.publish('stopped')
            finally:
                # KeyboardInterrupt exits the polling loop through its own except clause.
                if runtime_status(store)['state'] != 'failed':
                    runner.publish('stopped')
                store.audit('operations', 'runner_stopped', {})
    except Exception:
        print('Operations configuration, lock or storage failure; inspect local setup. Execution disabled.', flush=True)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
