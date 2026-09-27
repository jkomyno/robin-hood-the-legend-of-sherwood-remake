#!/usr/bin/env python3
"""Build library lossy models and previews in disjoint Blender workers.

Run from any directory. Defaults to Sherwood, four workers, two threads each.
The shared Blender render pool still limits total concurrent jobs to four.
Stop overlapping library runs before starting this script.
"""
import argparse
import json
import os
from pathlib import Path
import queue
import shutil
import signal
import subprocess
import tempfile
import threading
import time

EDITOR = Path(__file__).resolve().parents[1]


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def stop(workers):
    for process in workers:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
    for process in workers:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def capture_output(process, identity, path, events):
    """Drain each pipe continuously, retaining the complete Blender output."""
    try:
        with path.open("w", buffering=1) as log:
            for line in process.stdout:
                log.write(line)
                events.put((identity, line.rstrip()))
    except Exception as error:
        events.put((identity, f"Output capture failed: {error}"))
    finally:
        process.stdout.close()
        events.put((identity, None))


def monitor(workers, events):
    finished, closed = set(), set()
    completed = [0] * len(workers)
    started = last_update = time.monotonic()
    while len(finished) < len(workers) or len(closed) < len(workers):
        try:
            identity, line = events.get(timeout=1)
            if line is None:
                closed.add(identity)
            elif line.startswith(("PLAN ", "LOSSY ", "REFUSED ", "Render slot ",
                                  "Waiting for render slot", "Output capture failed:")):
                if line.startswith("LOSSY ") and not line.startswith("LOSSY FAILED "):
                    completed[identity] += 1
                print(f"[worker {identity}] {line}", flush=True)
        except queue.Empty:
            pass
        for identity, process in enumerate(workers):
            if identity not in finished and identity in closed and process.poll() is not None:
                finished.add(identity)
                print(f"[worker {identity}] exited {process.returncode}; "
                      f"{completed[identity]} assets rebuilt", flush=True)
        now = time.monotonic()
        if now - last_update >= 30:
            active = ", ".join(str(i) for i in range(len(workers)) if i not in finished)
            print(f"[{int(now-started)}s] {sum(completed)} assets rebuilt; "
                  f"active workers: {active or 'none'} (full details in logs)", flush=True)
            last_update = now
    return [process.wait() for process in workers]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--maps", nargs="+", default=["Sherwood"])
    selection.add_argument("--all", action="store_true", help="Process every map")
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--threads", type=positive, default=2)
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--root", type=Path, default=EDITOR / "library/3d-assets")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print worker commands without starting Blender or modifying files")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    assets = json.loads((root / "index.json").read_text())["assets"]
    maps = {name.lower() for name in args.maps}
    available = {asset["source_map"].lower() for asset in assets}
    if not args.all and maps - available:
        parser.error("Unknown maps: " + ", ".join(sorted(maps - available)))
    ids = sorted(asset["id"] for asset in assets
                 if args.all or asset["source_map"].lower() in maps)
    if not ids or len(ids) != len(set(ids)):
        parser.error("Selection must contain unique, nonempty asset IDs")
    blender = shutil.which(args.blender)
    if blender is None:
        parser.error("Blender executable not found: " + args.blender)
    run = (EDITOR / "work/preview-parallel-DRY-RUN" if args.dry_run else
           Path(tempfile.mkdtemp(prefix="preview-parallel-", dir=EDITOR / "work")))
    batches = [ids[i::args.workers] for i in range(args.workers)]
    workers = []
    readers = []
    events = queue.Queue()
    try:
        for i, batch in enumerate(batches):
            if not batch:
                continue
            command = [blender, "--background", "--threads", str(args.threads),
                       "--python-exit-code", "1", "--python",
                       str(EDITOR / "refinement/blender/lossy_assets.py"),
                       "--", "library", "--root", str(root),
                       "--run", str(run / f"worker-{i}"), "--assets", *batch, "--apply"]
            print(f"Worker {i}: {len(batch)} assets; log {run / f'worker-{i}.log'}", flush=True)
            if args.dry_run:
                import shlex
                print(shlex.join(command))
                continue
            process = subprocess.Popen(command, cwd=EDITOR.parent,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace", bufsize=1, start_new_session=True,
                env={**os.environ, "PYTHONUNBUFFERED": "1"})
            workers.append(process)
            reader = threading.Thread(target=capture_output,
                args=(process, i, run / f"worker-{i}.log", events), daemon=True)
            readers.append(reader)
            reader.start()
        codes = monitor(workers, events)
        for reader in readers:
            reader.join()
    except KeyboardInterrupt:
        stop(workers)
        print("Stopped workers. Completed derivatives are retained and skipped on rerun.")
        return 130
    except BaseException:
        stop(workers)
        raise
    if any(codes):
        print(f"Some workers failed (exit codes {codes}). Check logs in {run}.")
        return 1
    if not args.dry_run:
        print(f"Completed {len(ids)} assets. Logs and run records: {run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
