
from conftest import NOW

from gridhour.grid import SLOT
from gridhour.keys import END, HOME, LEFT, RIGHT, S_RIGHT, handle_key


def press(st, *keys):
    out = None
    for k in keys:
        out = handle_key(st, k, NOW)
    return out


def test_scrub_and_back(st):
    press(st, RIGHT, RIGHT)
    assert st.frozen == NOW.replace(minute=30, second=0) + SLOT * 2
    press(st, S_RIGHT)
    assert st.frozen == NOW.replace(minute=30, second=0) + SLOT * 6
    press(st, "r")
    assert st.frozen is None


def test_scrub_is_clamped(st):
    press(st, HOME[0], LEFT, LEFT)
    assert st.frozen == st.fc.slots[0].start
    press(st, END[1], RIGHT)
    assert st.frozen == st.fc.slots[-1].start


def test_enter_jumps_to_best_window(st):
    press(st, "\r")
    assert st.frozen == NOW.replace(day=4, hour=11, minute=0)


def test_select_and_resize_jobs(st):
    press(st, "j", "j")
    assert st.sel == 2 and st.job.name == "EV charge"
    press(st, "+", "+")
    assert st.job.minutes == 300
    press(st, "k", "k", "k")
    assert st.sel == 0
    for _ in range(10):
        press(st, "-")
    assert st.job.minutes == 30


def test_resizing_does_not_touch_the_defaults(st):
    from gridhour.plan import DEFAULT_JOBS
    press(st, "+")
    assert DEFAULT_JOBS[0].minutes == 120


def test_add_job(st):
    press(st, "a", *"Dryer 1h30", "\r")
    assert st.jobs[-1].name == "Dryer" and st.jobs[-1].minutes == 90 and st.sel == len(st.jobs) - 1
    assert st.prompt is None


def test_add_job_error_keeps_prompt(st):
    press(st, "a", *"Dryer", "\r")
    assert st.prompt == "job" and st.err
    press(st, "\x1b")
    assert st.prompt is None


def test_delete_keeps_one(st):
    for _ in range(10):
        press(st, "d")
    assert len(st.jobs) == 1


def test_mode_cycles(st):
    assert st.mode == "both"
    press(st, "w")
    assert st.mode == "green"
    press(st, "w", "w")
    assert st.mode == "both"


def test_postcode_prompt(st):
    st.buf = ""
    assert press(st, "p", *"\x7f" * 10, *"M1 1AE", "\r") == "refetch"
    assert st.postcode == "M1"


def test_postcode_prompt_rejects(st):
    press(st, "p", *"\x7f" * 10, *"nonsense", "\r")
    assert st.prompt == "postcode" and "postcode" in st.err


def test_quit_and_help(st):
    press(st, "?")
    assert st.prompt == "help"
    press(st, "x")
    assert st.prompt is None
    assert press(st, "q") == "quit"


def test_theme_and_clock(st):
    from gridhour.themes import C
    press(st, "T")
    assert C.name == "daylight"
    press(st, "t")
    assert st.h12
