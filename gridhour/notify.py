"""Job best-window start notifications: desktop alert and terminal bell."""
import shutil
import subprocess
import sys
import threading

from . import plan
from .safe import label


def fmt_price(p, digits=1):
    if p is None:
        return ""
    return ("%.*fp" % (digits, p)) if p >= 0 else ("-%.*fp" % (digits, abs(p)))


def format_notification(job, window):
    name = label(job.name) if job else "Job"
    parts = []
    if window.carbon is not None:
        parts.append("%d g" % round(window.carbon))
    if window.price is not None:
        parts.append(fmt_price(window.price))
    stats = ", ".join(parts)

    pieces = len(window.parts()) if window else 1
    if pieces > 1:
        prefix = "first of %d pieces" % pieces
        extra = ("%s, %s" % (prefix, stats)) if stats else prefix
    else:
        extra = stats

    if extra:
        return "%s: best window starts now (%s)" % (name, extra)
    return "%s: best window starts now" % name


def _run_cmd(cmd):
    try:
        proc = subprocess.Popen(  # noqa: S603
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    except OSError:
        pass


def build_desktop_cmd(title, body, platform=None, which=shutil.which):
    plat = platform if platform is not None else sys.platform
    title_safe = label(title) or "Gridhour"
    body_safe = label(body) or ""
    if plat == "darwin":
        exe = which("osascript")
        if exe:
            return [
                exe,
                "-e", "on run argv",
                "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
                "-e", "end run",
                "--",
                title_safe,
                body_safe,
            ]
    elif plat.startswith("linux"):
        exe = which("notify-send")
        if exe:
            return [exe, "--", title_safe, body_safe]
    return None


def send_desktop(title, body):
    cmd = build_desktop_cmd(title, body)
    if cmd:
        threading.Thread(target=_run_cmd, args=(cmd,), name="gridhour-notify", daemon=True).start()


def notify_window_start(job, window, screen=None):
    if screen and hasattr(screen, "bell"):
        screen.bell()
    title = "Gridhour"
    body = format_notification(job, window)
    send_desktop(title, body)


class Notifier:
    """Tracks the upcoming best window and triggers notifications when it starts."""

    def __init__(self):
        self.pending_window = None
        self.last_notified = None       # (job_name, window_start)
        self.last_job = None            # (name, minutes, deadline, split, mode)
        self.last_forecast = None
        self.active_windows = {}

    def check(self, st, live, screen=None):
        if not st.notify or st.frozen is not None or not st.job or not st.fc.slots:
            self.pending_window = None
            self.last_job = None
            self.last_forecast = None
            return

        job = st.job
        job_key = (job.name, job.minutes, job.deadline, job.split, st.mode,
                   st.postcode, st.region_id, st.gsp, st.tariff, st.prices)
        # A started split window remains one job until its final piece ends.
        self.active_windows = {key: end for key, end in self.active_windows.items() if end > live}
        if job_key in self.active_windows:
            self.pending_window = None
            self.last_job, self.last_forecast = job_key, st.fc
            return
        job_changed = self.last_job != job_key
        # Requests increment gen before data arrives. Watch the actual forecast instead.
        data_changed = self.last_forecast is not st.fc
        due = self.pending_window is not None and live >= self.pending_window.start
        job_or_data_changed = job_changed or (data_changed and not due)

        if job_or_data_changed:
            self.last_job = job_key
            self.last_forecast = st.fc
            sc = plan.scores(st.fc.slots, st.mode)
            w = plan.best_window(st.fc.slots, sc, job, live)
            if w and w.start > live:
                self.pending_window = w
            else:
                self.pending_window = None
                if w:
                    # Already active at tracking time; avoid session-start / job-switch alert
                    self.last_notified = (job.name, w.start)

        if self.pending_window is None:
            sc = plan.scores(st.fc.slots, st.mode)
            w = plan.best_window(st.fc.slots, sc, job, live)
            if w and w.start > live:
                self.pending_window = w
            return

        if live < self.pending_window.start:
            return

        # Boundary reached!
        w = self.pending_window
        self.pending_window = None
        key = (job.name, w.start)

        if self.last_notified == key:
            return

        self.active_windows[job_key] = w.end
        delay = (live - w.start).total_seconds()
        if delay > 60.0:
            # Avoid late alerts (e.g. machine asleep)
            self.last_notified = key
            return

        self.last_notified = key
        notify_window_start(job, w, screen)
