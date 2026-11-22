"""Plays a recorded event list back through an input backend, in a thread."""

import random
import threading
import time

from .keys import key_id


class Player:
    def __init__(self, backend, on_progress=None, on_finish=None, clock=time.perf_counter):
        self.backend = backend
        self.on_progress = on_progress  # called with (loop_number, total_loops)
        self.on_finish = on_finish      # called with (loops_completed, error_or_None, reason)
        self._clock = clock
        self._stop = threading.Event()
        self._thread = None
        self._held_keys = {}
        self._held_buttons = set()
        self._deadline = None
        self._timed_out = False

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self, events, loops=0, speed=1.0, loop_delay=0.0, humanize=0.0, move_to_clicks=True,
              stop_after=0.0):
        """Start playback. ``loops=0`` means repeat forever.

        ``stop_after`` (seconds, 0 = never) stops playback after that long,
        whatever loop it is on.

        ``humanize`` is a fraction (0.1 = +/-10%) of random variation applied
        to the gaps between events and to the delay between loops.
        """
        if self.running or not events:
            return False
        self._stop.clear()
        self._timed_out = False
        self._deadline = self._clock() + float(stop_after) if stop_after and stop_after > 0 else None
        self._thread = threading.Thread(
            target=self._run,
            args=(list(events), int(loops), max(0.05, float(speed)), max(0.0, float(loop_delay)),
                  max(0.0, min(0.9, float(humanize))), bool(move_to_clicks)),
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self, wait=True):
        self._stop.set()
        if wait and self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)

    # ---- internals -------------------------------------------------------
    def _wait_until(self, target):
        """Sleep until ``target`` (clock time). Returns False if stopped."""
        if self._deadline is not None and target >= self._deadline:
            if self._wait_plain(self._deadline):
                self._timed_out = True
                self._stop.set()
            return False
        return self._wait_plain(target)

    def _wait_plain(self, target):
        while True:
            remaining = target - self._clock()
            if remaining <= 0:
                return not self._stop.is_set()
            if remaining > 0.003:
                if self._stop.wait(remaining - 0.002):
                    return False
            else:
                if self._stop.is_set():
                    return False
                time.sleep(0)

    def _jitter(self, value, humanize):
        if humanize <= 0 or value <= 0:
            return value
        return value * random.uniform(1 - humanize, 1 + humanize)

    def _dispatch(self, ev, move_to_clicks):
        typ = ev.get("type")
        if typ == "key":
            k = ev["key"]
            down = ev.get("action") == "down"
            self.backend.key(k, down)
            if down:
                self._held_keys[key_id(k)] = k
            else:
                self._held_keys.pop(key_id(k), None)
        elif typ == "click":
            down = ev.get("action") == "down"
            if hasattr(self.backend, "move_to_event"):
                self.backend.move_to_event(ev)  # background: always aim inside the window
            elif move_to_clicks and "x" in ev and "y" in ev:
                self.backend.mouse_move(ev["x"], ev["y"])
            btn = ev.get("button", "left")
            self.backend.mouse_button(btn, down)
            if down:
                self._held_buttons.add(btn)
            else:
                self._held_buttons.discard(btn)
        elif typ == "move":
            if hasattr(self.backend, "move_to_event"):
                self.backend.move_to_event(ev)
            else:
                self.backend.mouse_move(ev["x"], ev["y"])
        elif typ == "scroll":
            self.backend.scroll(ev.get("dx", 0), ev.get("dy", 0))

    def release_all(self):
        for k in list(self._held_keys.values()):
            try:
                self.backend.key(k, False)
            except Exception:
                pass
        for b in list(self._held_buttons):
            try:
                self.backend.mouse_button(b, False)
            except Exception:
                pass
        self._held_keys.clear()
        self._held_buttons.clear()

    def _run(self, events, loops, speed, loop_delay, humanize, move_to_clicks):
        done = 0
        error = None
        try:
            while not self._stop.is_set() and (loops == 0 or done < loops):
                if self.on_progress:
                    self.on_progress(done + 1, loops)
                if hasattr(self.backend, "alive") and not self.backend.alive():
                    raise RuntimeError("the target window was closed")
                if hasattr(self.backend, "prepare"):
                    self.backend.prepare()
                cursor = self._clock()
                prev_t = 0.0
                for ev in events:
                    gap = max(0.0, ev["t"] - prev_t) / speed
                    prev_t = ev["t"]
                    cursor += self._jitter(gap, humanize)
                    if not self._wait_until(cursor):
                        break
                    self._dispatch(ev, move_to_clicks)
                self.release_all()
                if self._stop.is_set():
                    break
                done += 1
                if loops == 0 or done < loops:
                    if not self._wait_until(self._clock() + self._jitter(loop_delay, humanize)):
                        break
        except Exception as e:  # never leave keys held down on a crash
            error = e
        finally:
            self.release_all()
            if self.on_finish:
                reason = "error" if error else "time_limit" if self._timed_out else (
                    "stopped" if self._stop.is_set() else "done")
                self.on_finish(done, error, reason)
