"""Limit concurrent full-scene bakes without changing their pixels or settings."""
import fcntl
import os
from pathlib import Path
import time

_lease = None


def acquire(slots=2):
    """Hold one process-scoped render lease until exit; repeated calls are safe."""
    global _lease
    if _lease is not None:
        return
    root = Path(__file__).resolve().parents[2] / 'work/nottingham-refinement/render-slots'
    root.mkdir(parents=True, exist_ok=True)
    handles = [(root / f'{i}.lock').open('a+') for i in range(slots)]
    started = time.monotonic()
    last_notice = -30.0
    while True:
        for index, handle in enumerate(handles):
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                continue
            _lease = handle
            handle.seek(0)
            handle.truncate()
            handle.write(str(os.getpid()) + '\n')
            handle.flush()
            for other in handles:
                if other is not handle:
                    other.close()
            print(f'Nottingham render slot {index} acquired by {os.getpid()}', flush=True)
            return
        elapsed = time.monotonic() - started
        if elapsed - last_notice >= 30:
            print(f'Waiting for Nottingham render slot ({elapsed:.0f}s)', flush=True)
            last_notice = elapsed
        time.sleep(1)


def release():
    """Release the current asset's lease so queued work can run between bakes."""
    global _lease
    if _lease is not None:
        fcntl.flock(_lease, fcntl.LOCK_UN)
        _lease.close()
        _lease = None
        return True
    return False
