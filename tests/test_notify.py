import io
import json
import subprocess
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from conftest import NOW

from gridhour.app import Screen
from gridhour.grid import Forecast, Slot
from gridhour.keys import handle_key
from gridhour.notify import (
    Notifier,
    _run_cmd,
    build_desktop_cmd,
    fmt_price,
    format_notification,
    notify_window_start,
    send_desktop,
)
from gridhour.plan import Job, Window
from gridhour.state import State, config_path, state_from_config


def test_fmt_price():
    assert fmt_price(None) == ""
    assert fmt_price(6.32) == "6.3p"
    assert fmt_price(0.0) == "0.0p"
    assert fmt_price(-2.5) == "-2.5p"


def test_format_notification_single_piece():
    j = Job("Washing", 120)
    w = Window(j, 0, 3, 0.2, 104.2, 6.31, NOW, NOW + timedelta(hours=2))
    assert format_notification(j, w) == "Washing: best window starts now (104 g, 6.3p)"


def test_format_notification_split():
    j = Job("EV charge", 240, split=True)
    # indices with a gap: 0..1 and 4..5 -> 2 pieces
    w = Window(j, 0, 5, 0.1, 79.8, 5.0, NOW, NOW + timedelta(hours=3), indices=(0, 1, 4, 5))
    assert len(w.parts()) == 2
    assert format_notification(j, w) == "EV charge: best window starts now (first of 2 pieces, 80 g, 5.0p)"


def test_format_notification_stats_variations():
    j = Job("Dryer", 60)
    # Carbon only
    w1 = Window(j, 0, 1, 0.2, 120.0, None, NOW, NOW + timedelta(hours=1))
    assert format_notification(j, w1) == "Dryer: best window starts now (120 g)"
    # Price only
    w2 = Window(j, 0, 1, 0.2, None, 4.5, NOW, NOW + timedelta(hours=1))
    assert format_notification(j, w2) == "Dryer: best window starts now (4.5p)"
    # Neither
    w3 = Window(j, 0, 1, 0.2, None, None, NOW, NOW + timedelta(hours=1))
    assert format_notification(j, w3) == "Dryer: best window starts now"
    # Split with no stats
    j_split = Job("Pump", 60, split=True)
    w4 = Window(j_split, 0, 3, 0.2, None, None, NOW, NOW + timedelta(hours=2), indices=(0, 3))
    assert format_notification(j_split, w4) == "Pump: best window starts now (first of 2 pieces)"


def test_format_notification_label_sanitizes():
    j = Job('EV" & display dialog "hacked" & \x1b[31m', 60)
    w = Window(j, 0, 1, 0.2, None, None, NOW, NOW + timedelta(hours=1))
    msg = format_notification(j, w)
    assert "\x1b" not in msg
    assert 'EV" & display dialog "hacked" & ?' in msg


def test_build_desktop_cmd_macos():
    cmd = build_desktop_cmd("Gridhour", "Washing starts now", platform="darwin", which=lambda x: "/usr/bin/osascript")
    assert cmd == [
        "/usr/bin/osascript",
        "-e", "on run argv",
        "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
        "-e", "end run",
        "--",
        "Gridhour",
        "Washing starts now",
    ]


def test_build_desktop_cmd_macos_missing():
    assert build_desktop_cmd("Title", "Body", platform="darwin", which=lambda x: None) is None


def test_build_desktop_cmd_linux():
    cmd = build_desktop_cmd("Gridhour", "Washing starts now", platform="linux", which=lambda x: "/usr/bin/notify-send")
    assert cmd == ["/usr/bin/notify-send", "--", "Gridhour", "Washing starts now"]


def test_build_desktop_cmd_linux_missing():
    assert build_desktop_cmd("Title", "Body", platform="linux", which=lambda x: None) is None


def test_build_desktop_cmd_other():
    assert build_desktop_cmd("Title", "Body", platform="win32", which=lambda x: "x") is None


def test_run_cmd(monkeypatch):
    called = []

    class DummyProc:
        def wait(self, timeout=None):
            called.append(timeout)

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: DummyProc())
    _run_cmd(["dummy"])
    assert called == [5]


def test_run_cmd_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("fail")

    monkeypatch.setattr(subprocess, "Popen", boom)
    _run_cmd(["dummy"])  # does not raise


def test_send_desktop_missing_utility(monkeypatch):
    monkeypatch.setattr("gridhour.notify.build_desktop_cmd", lambda *args: None)
    thread = MagicMock()
    monkeypatch.setattr("gridhour.notify.threading.Thread", thread)
    send_desktop("Gridhour", "Body")
    thread.assert_not_called()


def test_notify_window_start(monkeypatch):
    sent = []
    monkeypatch.setattr("gridhour.notify.send_desktop", lambda t, b: sent.append((t, b)))
    mock_screen = MagicMock()

    j = Job("Washing", 120)
    w = Window(j, 0, 3, 0.2, 104.0, 6.3, NOW, NOW + timedelta(hours=2))
    notify_window_start(j, w, mock_screen)

    assert mock_screen.bell.called
    assert len(sent) == 1
    assert sent[0][0] == "Gridhour"
    assert "Washing: best window starts now" in sent[0][1]


def test_screen_bell():
    buf = io.StringIO()
    screen = Screen(buf)
    screen.bell()
    assert buf.getvalue() == "\a"


def test_key_n_toggles_and_saves(st):
    st.persist = True
    assert not st.notify
    handle_key(st, "n", NOW)
    assert st.notify is True
    assert "notifications: on" in st.msg[0]

    with open(config_path(), encoding="utf-8") as f:
        cfg = json.load(f)
    assert cfg.get("notify") is True

    handle_key(st, "n", NOW)
    assert st.notify is False
    assert "notifications: off" in st.msg[0]

    with open(config_path(), encoding="utf-8") as f:
        cfg = json.load(f)
    assert cfg.get("notify") is False


def test_state_from_config_loads_notify(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    st = State()
    st.notify = True
    st.save()

    loaded = state_from_config()
    assert loaded.notify is True


def test_notifier_check_conditions(st):
    notifier = Notifier()
    screen = MagicMock()

    # Disabled
    st.notify = False
    notifier.check(st, NOW, screen)
    assert not screen.bell.called
    assert notifier.pending_window is None

    # Scrubbed
    st.notify = True
    st.frozen = NOW
    notifier.check(st, NOW, screen)
    assert not screen.bell.called

    # No job
    st.frozen = None
    st.jobs = []
    notifier.check(st, NOW, screen)
    assert not screen.bell.called


def test_notifier_session_start_no_alert(st):
    # Best window starts at or before NOW -> already in progress, avoid session-start alert
    st.notify = True
    notifier = Notifier()
    screen = MagicMock()

    # At NOW, the best window for Washing starts at 12:00 tomorrow (in the fixture),
    # but suppose we query at 12:05 tomorrow when it is already in progress:
    future_now = datetime(2026, 10, 4, 12, 5, tzinfo=UTC)
    notifier.check(st, future_now, screen)

    # Window was already active, so it should not alert
    assert not screen.bell.called
    assert notifier.pending_window is None
    assert notifier.last_notified is not None


def test_notifier_lifecycle_tracks_and_fires_once(st, monkeypatch):
    st.notify = True
    notifier = Notifier()
    notifications = []
    monkeypatch.setattr("gridhour.notify.notify_window_start", lambda j, w, s: notifications.append((j.name, w.start)))

    # At NOW (22:46 on Oct 3), best window for Washing is 12:00 on Oct 4
    notifier.check(st, NOW)
    assert notifier.pending_window is not None
    win_start = notifier.pending_window.start
    assert win_start > NOW
    assert len(notifications) == 0

    # 1 second before window start: still pending
    t_before = win_start - timedelta(seconds=1)
    notifier.check(st, t_before)
    assert len(notifications) == 0
    assert notifier.pending_window is not None

    # Window starts! Boundary reached
    notifier.check(st, win_start)
    assert len(notifications) == 1
    assert notifications[0] == ("Washing", win_start)
    assert notifier.pending_window is None

    # Ticks after window start: does not re-alert (once per window)
    t_after = win_start + timedelta(seconds=5)
    notifier.check(st, t_after)
    assert len(notifications) == 1


def test_notifier_late_alert_avoided(st, monkeypatch):
    st.notify = True
    notifier = Notifier()
    notifications = []
    monkeypatch.setattr("gridhour.notify.notify_window_start", lambda j, w, s: notifications.append(w.start))

    notifier.check(st, NOW)
    win_start = notifier.pending_window.start

    # System was asleep and wakes up 10 minutes late
    t_late = win_start + timedelta(minutes=10)
    notifier.check(st, t_late)

    # Late alert avoided
    assert len(notifications) == 0
    assert notifier.pending_window is None
    assert notifier.last_notified == ("Washing", win_start)


def test_notifier_job_or_data_change(st):
    st.notify = True
    notifier = Notifier()

    notifier.check(st, NOW)
    orig_pending = notifier.pending_window
    assert orig_pending is not None

    # Switch job
    st.sel = 1  # Dishwasher
    notifier.check(st, NOW)
    assert notifier.pending_window is not None
    assert notifier.pending_window.job.name == "Dishwasher"

    # Fresh data gen
    st.gen += 1
    notifier.check(st, NOW)
    assert notifier.pending_window is not None


def test_send_desktop_spawns_thread(monkeypatch):
    monkeypatch.setattr("gridhour.notify.build_desktop_cmd", lambda t, b: ["dummy", t, b])
    threads = []

    class DummyThread:
        def __init__(self, target=None, args=(), name=None, daemon=None):
            self.target, self.args, self.name, self.daemon = target, args, name, daemon

        def start(self):
            threads.append(self)

    import threading
    monkeypatch.setattr(threading, "Thread", DummyThread)
    send_desktop("Title", "Body")
    assert len(threads) == 1
    assert threads[0].args == (["dummy", "Title", "Body"],)
    assert threads[0].name == "gridhour-notify"
    assert threads[0].daemon is True


def test_notifier_recovers_pending_when_none(st):
    st.notify = True
    notifier = Notifier()
    # Populate initial job cache
    notifier.check(st, NOW)
    assert notifier.pending_window is not None
    # Force pending_window to None while job/data unchanged
    notifier.pending_window = None
    # Now check again: it should re-evaluate and restore pending_window because win.start > NOW
    notifier.check(st, NOW)
    assert notifier.pending_window is not None


def test_notifier_already_notified_key_at_boundary(st, monkeypatch):
    st.notify = True
    notifier = Notifier()
    notifications = []
    monkeypatch.setattr("gridhour.notify.notify_window_start", lambda j, w, s: notifications.append(w.start))

    notifier.check(st, NOW)
    win_start = notifier.pending_window.start
    # Manually set last_notified to the upcoming window
    notifier.last_notified = ("Washing", win_start)

    # Reach boundary
    notifier.check(st, win_start)
    # Does not fire because already marked notified
    assert len(notifications) == 0


def test_compose_help_and_chips(st):
    from gridhour.compose import HELP, compose

    # Check 'n' in HELP
    help_keys = [k for k, _ in HELP]
    assert "n" in help_keys

    # The optional last chip appears when the footer has enough room.
    cv = compose(200, 40, st, NOW, NOW)
    rendered_text = "\n".join(cv.text())
    assert "notify" in rendered_text


def test_pausing_notifications_discards_pending_boundary(st, monkeypatch):
    sent = []
    monkeypatch.setattr("gridhour.notify.notify_window_start", lambda *args: sent.append(args))
    for pause in ("disabled", "scrubbed"):
        st.notify, st.frozen = True, None
        notifier = Notifier()
        notifier.check(st, NOW)
        start = notifier.pending_window.start
        if pause == "disabled":
            st.notify = False
        else:
            st.frozen = start
        notifier.check(st, start)
        st.notify, st.frozen = True, None
        notifier.check(st, start + timedelta(seconds=1))
        assert sent == []


def test_starting_fetch_at_boundary_keeps_armed_alert(st, monkeypatch):
    sent = []
    monkeypatch.setattr("gridhour.notify.notify_window_start", lambda *args: sent.append(args))
    st.notify = True
    notifier = Notifier()
    notifier.check(st, NOW)
    start = notifier.pending_window.start
    st.gen += 1  # A request starts; the forecast itself has not changed.
    notifier.check(st, start)
    assert len(sent) == 1


def test_notification_timeout_reaps_child(monkeypatch):
    proc = MagicMock()
    proc.wait.side_effect = [subprocess.TimeoutExpired("dummy", 5), None]
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: proc)
    _run_cmd(["dummy"])
    proc.kill.assert_called_once_with()
    assert proc.wait.call_count == 2


def test_split_job_alerts_only_at_first_piece(st, monkeypatch):
    sent = []
    monkeypatch.setattr("gridhour.notify.notify_window_start", lambda *args: sent.append(args))
    start = NOW.replace(minute=0) + timedelta(hours=1)
    st.fc = Forecast()
    st.fc.slots = [Slot(start + timedelta(minutes=30 * k), carbon=c)
                   for k, c in enumerate([100, 1, 100, 2, 100, 3, 100, 100])]
    st.jobs, st.sel, st.mode, st.notify = [Job("EV", 60, split=True)], 0, "green", True
    notifier = Notifier()
    notifier.check(st, start)
    first = notifier.pending_window.start
    notifier.check(st, first)
    for k in range(1, 5):
        notifier.check(st, first + timedelta(minutes=30 * k))
    assert len(sent) == 1


def test_arriving_forecast_replans_upcoming_window(st):
    from dataclasses import replace

    st.notify = True
    notifier = Notifier()
    st.mode = "green"
    st.jobs = [Job("Short", 30)]
    st.sel = 0
    notifier.check(st, NOW)
    previous = notifier.pending_window.start
    # Same fetch generation, different forecast: newly cheap carbon slot must win.
    target = st.fc.slots[-1].start
    st.fc = replace(st.fc, slots=[replace(slot, carbon=0 if slot.start == target else 999)
                                 for slot in st.fc.slots])
    notifier.check(st, NOW)
    assert notifier.pending_window.start == target
    assert target != previous


def test_build_desktop_cmd_preserves_longer_body_and_stats():
    job = Job("Overnight immersion heater", 120)
    window = Window(job, 0, 3, 0.2, 104.0, 6.3, NOW, NOW + timedelta(hours=2))
    body = format_notification(job, window)
    assert body == "Overnight immersion heater: best window starts now (104 g, 6.3p)"
    assert len(body) == 64

    cmd_linux = build_desktop_cmd("Gridhour", body, platform="linux", which=lambda x: "/usr/bin/notify-send")
    assert cmd_linux == [
        "/usr/bin/notify-send",
        "--",
        "Gridhour",
        "Overnight immersion heater: best window starts now (104 g, 6.3p)",
    ]

    cmd_mac = build_desktop_cmd("Gridhour", body, platform="darwin", which=lambda x: "/usr/bin/osascript")
    assert cmd_mac[-1] == "Overnight immersion heater: best window starts now (104 g, 6.3p)"


def test_build_desktop_cmd_max_job_name_and_split():
    name_60 = "Overnight battery charging and heat pump water heating cycle"
    assert len(name_60) == 60
    job = Job(name_60, 240, split=True)
    window = Window(job, 0, 5, 0.1, 79.8, 5.0, NOW, NOW + timedelta(hours=3), indices=(0, 1, 4, 5))
    body = format_notification(job, window)
    expected = "%s: best window starts now (first of 2 pieces, 80 g, 5.0p)" % name_60
    assert body == expected
    assert len(body) == 116

    cmd_linux = build_desktop_cmd("Gridhour", body, platform="linux", which=lambda x: "/usr/bin/notify-send")
    assert cmd_linux[-1] == expected

    cmd_mac = build_desktop_cmd("Gridhour", body, platform="darwin", which=lambda x: "/usr/bin/osascript")
    assert cmd_mac[-1] == expected


def test_build_desktop_cmd_hostile_controls_and_bounded():
    hostile_body = 'Job\x1b[31m "name" \x00\r\n\u202e: best window starts now (104 g, 6.3p)'
    cmd_mac = build_desktop_cmd("Gridhour\x00", hostile_body, platform="darwin", which=lambda x: "/usr/bin/osascript")
    assert "\x1b" not in cmd_mac[-1]
    assert "\x00" not in cmd_mac[-1]
    assert "\r" not in cmd_mac[-1]
    assert "\n" not in cmd_mac[-1]
    assert "\u202e" not in cmd_mac[-1]
    assert "\x00" not in cmd_mac[-2]

    huge = "A" * 5000
    cmd_bounded = build_desktop_cmd("Gridhour", huge, platform="darwin", which=lambda x: "/usr/bin/osascript")
    assert len(cmd_bounded[-1]) <= 160
