"""The auto-clicker: clicks at a set speed, in a thread, no recording needed."""

import random
import threading
import time

from .timing import GO, PAUSED, Waiter


class Clicker:
    def __init__(self, backend, on_click=None, on_finish=None, clock=time.perf_counter):
        self.backend = backend
        self.on_click = on_click    # () after every click
        self.on_finish = on_finish  # (clicks, error_or_None, reason)
        self._w = Waiter(clock)
        self._clock = clock
        self._thread = None
        self._down = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    @property
    def paused(self):
        return self._w.pause_event.is_set()

    def set_paused(self, paused):
        if paused:
            self._w.pause_event.set()
        else:
            self._w.pause_event.clear()

    def start(self, cps=10.0, button="left", vary=0.0, point=None, stop_after=0.0):
        """``cps`` clicks a second; ``vary`` 0.15 = each gap random within ±15%;
        ``point`` (x, y) clicks there instead of where the mouse is."""
        if self.running:
            return False
        self._w.reset(stop_after)
        self._w.pause_event.clear()
        cps = max(0.2, min(100.0, float(cps)))
        self._thread = threading.Thread(
            target=self._run, args=(cps, button, max(0.0, min(0.9, float(vary))), point), daemon=True)
        self._thread.start()
        return True

    def stop(self, wait=True):
        self._w.stop_event.set()
        if wait and self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)

    def _release(self):
        if self._down:
            try:
                self.backend.mouse_button(self._down, False)
            except Exception:
                pass
            self._down = None

    def _run(self, cps, button, vary, point):
        clicks = 0
        error = None
        interval = 1.0 / cps
        hold = min(0.03, interval / 3)
        try:
            nxt = self._clock()
            while not self._w.stopped():
                r = self._w.wait_until(nxt)
                if r == PAUSED:
                    if not self._w.wait_unpaused():
                        break
                    nxt = self._clock()
                    continue
                if r != GO:
                    break
                if point:
                    self.backend.mouse_move(point[0], point[1])
                self.backend.mouse_button(button, True)
                self._down = button
                time.sleep(hold)
                self.backend.mouse_button(button, False)
                self._down = None
                clicks += 1
                if self.on_click:
                    self.on_click()
                gap = interval * (random.uniform(1 - vary, 1 + vary) if vary else 1.0)
                nxt = max(nxt + gap, self._clock())
        except Exception as e:
            error = e
        finally:
            self._release()
            if self.on_finish:
                reason = "error" if error else "time_limit" if self._w.timed_out else "stopped"
                self.on_finish(clicks, error, reason)
