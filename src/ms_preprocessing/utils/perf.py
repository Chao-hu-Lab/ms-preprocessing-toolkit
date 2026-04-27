"""
Performance utilities for timing and memory usage.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

try:
    import psutil  # type: ignore
except Exception:
    psutil = None


@dataclass
class PerfSnapshot:
    """Snapshot of timing and memory usage."""
    time: float
    rss_mb: float | None


def _current_rss_mb() -> float | None:
    if psutil is None:
        return None
    try:
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)
    except Exception:
        return None


def take_snapshot() -> PerfSnapshot:
    """Take a performance snapshot."""
    return PerfSnapshot(time=time.perf_counter(), rss_mb=_current_rss_mb())


def format_perf_delta(start: PerfSnapshot, end: PerfSnapshot) -> str:
    """Format elapsed time and memory delta for logging."""
    elapsed = end.time - start.time
    if start.rss_mb is None or end.rss_mb is None:
        return f"{elapsed:.2f}s"
    delta_mb = end.rss_mb - start.rss_mb
    return f"{elapsed:.2f}s, ΔRSS {delta_mb:+.1f} MB"
