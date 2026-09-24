import fcntl
import multiprocessing
from pathlib import Path
import tempfile
import time
import unittest

import render_slots


def worker(directory, index, events):
    render_slots.acquire(2, directory=directory)
    events.put(('start', index, time.monotonic()))
    time.sleep(.1)
    events.put(('end', index, time.monotonic()))
    render_slots.release()


class RenderSlotsTest(unittest.TestCase):
    def test_fifo_capacity_and_stale_ticket(self):
        context = multiprocessing.get_context('spawn')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holders = [(root / f'{i}.lock').open('a+') for i in range(2)]
            for handle in holders:
                fcntl.flock(handle, fcntl.LOCK_EX)
            stale = root / '00000000000000000000-dead.ticket'
            stale.write_text('999999\n')
            events = context.Queue()
            workers = []
            try:
                for index in range(6):
                    process = context.Process(target=worker, args=(directory, index, events))
                    process.start()
                    workers.append(process)
                    deadline = time.monotonic() + 5
                    while len(list(root.glob('*.ticket'))) != index + 1 or stale.exists():
                        if time.monotonic() > deadline:
                            self.fail('Worker failed to join FIFO queue')
                        time.sleep(.01)
                for handle in holders:
                    handle.close()
                for process in workers:
                    process.join(10)
                    self.assertEqual(process.exitcode, 0)
                records = sorted([events.get(timeout=1) for _ in range(12)], key=lambda row: row[2])
                active = peak = 0
                starts = []
                for kind, index, _ in records:
                    active += 1 if kind == 'start' else -1
                    peak = max(peak, active)
                    if kind == 'start':
                        starts.append(index)
                self.assertEqual(starts, list(range(6)))
                self.assertEqual(peak, 2)
                self.assertEqual(active, 0)
                self.assertFalse(list(root.glob('*.ticket')))
            finally:
                for handle in holders:
                    handle.close()
                for process in workers:
                    if process.is_alive():
                        process.terminate()
                        process.join()


if __name__ == '__main__':
    unittest.main()
