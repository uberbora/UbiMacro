"""Shared waiting logic for the player and the auto-clicker: precise sleeps
that wake up early for Stop, Pause or the "stop after" time limit."""

import threading
import time

GO, STOPPED, PAUSED = "go", "stopped", "paused"


class Waiter:
    def __init__(self, clock=time.perf_counter):
        self.clock = clock
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.deadline = None
        self.timed_out = False

    def reset(self, stop_after=0.0):
        self.stop_event.clear()
        self.timed_out = False
        self.deadline = self.clock() + float(stop_after) if stop_after and stop_after > 0 else None

    def stopped(self):
        return self.stop_event.is_set()

    def _past_deadline(self):
        if self.deadline is not None and self.clock() >= self.deadline:
            self.timed_out = True
            self.stop_event.set()
            return True
        return False

    def wait_until(self, target):
        """Sleep until ``target``. Returns GO, STOPPED or PAUSED."""
        while True:
            if self.stop_event.is_set() or self._past_deadline():
                return STOPPED
            if self.pause_event.is_set():
                return PAUSED
            now = self.clock()
            if self.deadline is not None:
                target_now = min(target, self.deadline)
            else:
                target_now = target
            remaining = target_now - now
            if remaining <= 0:
                if target_now < target:
                    continue  # the deadline came first: loop round to stop
                return GO
            if remaining > 0.003:
                # wake at least every 50 ms to notice a pause
                self.stop_event.wait(min(remaining - 0.002, 0.05))
            else:
                time.sleep(0)

    def wait_unpaused(self):
        """Block while paused. Returns False if stopped (or out of time) meanwhile."""
        while self.pause_event.is_set():
            if self.stop_event.wait(0.05) or self._past_deadline():
                return False
        return not self.stop_event.is_set()
