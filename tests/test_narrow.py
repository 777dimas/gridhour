"""Short job windows on narrow screens, where there are fewer columns than half hours."""
from datetime import UTC, datetime, timedelta

import pytest

from gridhour import plan
from gridhour.canvas import Canvas
from gridhour.compose import UK, Axis, compose, hour_ticks
from gridhour.grid import SLOT, WINDOW_SLOTS, Forecast, build_slots, window_start
from gridhour.state import State

NOW = datetime(2026, 11, 3, 10, 10, tzinfo=UTC)


def state_with_best_at(slot, minutes):
    start = window_start(NOW)
    n = minutes // 30
    carbon = {start + SLOT * i: (20 if slot <= i < slot + n else 300, "moderate", None) for i in range(96)}
    st = State()
    st.persist = False
    st.fc = Forecast(region="London", region_id=13, slots=build_slots(start, carbon, {}))
    st.jobs = [plan.Job("Dryer", minutes)]
    st.mode = "green"
    return st


@pytest.mark.parametrize("minutes", [30, 60, 120])
@pytest.mark.parametrize("compact", ["on", "off"])
def test_short_windows_never_crash_on_narrow_screens(minutes, compact):
    for slot in range(4, 90, 3):
        for width in range(40, 130, 7):
            st = state_with_best_at(slot, minutes)
            st.compact = compact
            text = "\n".join(compose(width, 40, st, NOW, NOW).text())
            assert "Dryer" in text


def test_span_always_has_a_column():
    for width in (10, 37, 49, 95, 96, 150):
        axis = Axis(0, width, NOW)
        for a in range(WINDOW_SLOTS):
            cols = axis.span(a, a)
            assert cols and all(0 <= c < width for c in cols)


def test_wide_screens_keep_the_exact_span():
    axis = Axis(0, 192, NOW)                      # two columns per half hour
    assert axis.span(10, 11) == [20, 21, 22, 23]


@pytest.mark.parametrize("day", [datetime(2026, 10, 9, tzinfo=UTC), datetime(2026, 12, 9, tzinfo=UTC)])  # BST, GMT
@pytest.mark.parametrize("small", [True, False])                       # compact layout, or the chart
def test_narrow_axes_name_every_midnight(day, small):
    """A terminal of 40 to 70 columns has an axis of 17 to 47. Below 48 a column spans more than
    an hour; midnight shared one with 23:00 and was dropped, which could leave the axis with no
    labels at all. On the chart, under 32 columns, 6-hourly labels crowded the day names out."""
    for width in range(17, 48):
        for k in range(48):
            start = day + timedelta(minutes=30 * k)
            axis = Axis(0, width, start)
            cv = Canvas(width, 1)
            hour_ticks(cv, 0, axis, False, small=small)
            row = cv.text()[0]
            midnights = {(start + timedelta(hours=h)).astimezone(UK).replace(hour=0, minute=0) for h in range(49)}
            due = [m for m in midnights if (c := axis.col(m)) is not None and c + 3 <= width]
            assert sum(row.count(m.strftime("%a")) for m in due) == len(due), (width, start, row)
