"""
In-memory job tracking. Deliberately not backed by a database or a
volume (out of scope, spec section 4) - a job that's interrupted by a
container restart must simply be re-run (spec section 7).
"""
import threading
import uuid
from typing import Dict, Optional

_lock = threading.Lock()
_jobs: Dict[str, dict] = {}


def create_job(total_chunks: int, kind: str, source_ext: str, source_filename: Optional[str]) -> str:
    job_id = uuid.uuid4().hex
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "status": "running",  # "running" | "done" | "error"
            "total_chunks": total_chunks,
            "completed_chunks": 0,
            "failed_chunks": 0,
            "kind": kind,
            "source_ext": source_ext,
            "source_filename": source_filename,
            "preview_text": None,
            "has_failures": False,
            "error": None,
        }
    return job_id


def update_job(job_id: str, **fields) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def increment_progress(job_id: str, failed: bool = False) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job:
            job["completed_chunks"] += 1
            if failed:
                job["failed_chunks"] += 1


def get_job(job_id: str) -> Optional[dict]:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None
