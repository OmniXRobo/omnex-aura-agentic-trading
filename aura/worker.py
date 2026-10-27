"""Bounded single-job worker. A supervisor/scheduler is a later milestone."""

import asyncio

from .agents import Orchestrator, Snapshot
from .store import Store


def process_one(store: Store):
    job = store.claim()
    if job is None:
        return False
    try:
        if job["topic"] != "research.snapshot":
            raise ValueError("Unsupported job topic")
        asyncio.run(Orchestrator(store).run(Snapshot.model_validate(job["payload"])))
    except Exception:
        store.finish(job["id"], job["lease_token"], success=False)
    else:
        store.finish(job["id"], job["lease_token"], success=True)
    return True
