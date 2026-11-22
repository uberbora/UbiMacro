"""Plays a recorded event list back through an input backend, in a thread."""

import random
import threading
import time

from .keys import key_id
from .timing import GO, PAUSED, STOPPED, Waiter


class Player:
    def __init__(self, backend, on_progress=None, on_finish=None, on_click=None, clock=time.perf_counter):
        self.backend = backend
        self.on_progress = on_progress  # (loop_number, total_loops)
        self.on_finish = on_finish      # (loops_completed, error_or_None, reason)
        self.on_click = on_click        # () for every mouse button press played
        self._w = Waiter(clock)
        self._clock = clock
        self._thread = None
        self._held_keys = {}
        self._held_buttons = set()

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def set_paused(self, paused):
        """Pause (e.g. you touched the mouse). Held keys are released and the
        current loop starts again from the top when unpaused."""
        if paused:
            self._w.pause_event.set()
        else:
            self._w.pause_event.clear()

    @property
    def paused(self):
        return self._w.pause_event.is_set()

    def start(self, events, loops=0, speed=1.0, loop_delay=0.0, humanize=0.0, move_to_clicks=True,
              stop_after=0.0):
        """Start playback. ``loops=0`` means repeat forever.

        ``stop_after`` (seconds, 0 = never) stops playback after that long.
        ``humanize`` is a fraction (0.1 = +/-10%) of random variation applied
        to the gaps between events and to the delay between loops.
        """
        if self.running or not events:
            return False
        self._w.reset(stop_after)
        self._w.pause_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(list(events), int(loops), max(0.05, float(speed)), max(0.0, float(loop_delay)),
                  max(0.0, min(0.9, float(humanize))), bool(move_to_clicks)),
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self, wait=True):
        self._w.stop_event.set()
        if wait and self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)

    # ---- internals -------------------------------------------------------
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
            if move_to_clicks and "x" in ev and "y" in ev:
                self.backend.mouse_move(ev["x"], ev["y"])
            btn = ev.get("button", "left")
            self.backend.mouse_button(btn, down)
            if down:
                self._held_buttons.add(btn)
                if self.on_click:
                    self.on_click()
            else:
                self._held_buttons.discard(btn)
        elif typ == "move":
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

    def _play_once(self, events, speed, humanize, move_to_clicks):
        """One pass. Returns GO (finished), STOPPED or PAUSED."""
        cursor = self._clock()
        prev_t = 0.0
        for ev in events:
            gap = max(0.0, ev["t"] - prev_t) / speed
            prev_t = ev["t"]
            cursor += self._jitter(gap, humanize)
            r = self._w.wait_until(cursor)
            if r != GO:
                return r
            self._dispatch(ev, move_to_clicks)
        return GO

    def _run(self, events, loops, speed, loop_delay, humanize, move_to_clicks):
        done = 0
        error = None
        try:
            while not self._w.stopped() and (loops == 0 or done < loops):
                if self.on_progress:
                    self.on_progress(done + 1, loops)
                r = self._play_once(events, speed, humanize, move_to_clicks)
                self.release_all()
                if r == PAUSED:
                    if not self._w.wait_unpaused():
                        break
                    continue  # redo this loop from the top
                if r == STOPPED:
                    break
                done += 1
                if loops == 0 or done < loops:
                    target = self._clock() + self._jitter(loop_delay, humanize)
                    while True:
                        r = self._w.wait_until(target)
                        if r == PAUSED:
                            if not self._w.wait_unpaused():
                                break
                            continue
                        break
                    if self._w.stopped():
                        break
        except Exception as e:  # never leave keys held down on a crash
            error = e
        finally:
            self.release_all()
            if self.on_finish:
                reason = "error" if error else "time_limit" if self._w.timed_out else (
                    "stopped" if self._w.stopped() else "done")
                self.on_finish(done, error, reason)
