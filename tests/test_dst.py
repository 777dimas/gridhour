from datetime import UTC, datetime, timedelta

import pytest

from gridhour.canvas import Canvas
from gridhour.compose import Axis, day_hm, hour_ticks, job_hm


@pytest.mark.parametrize('hour,zone', [(0, 'BST'), (1, 'GMT')])
@pytest.mark.parametrize('h12,clock', [(False, '01:30'), (True, '1:30am')])
def test_both_repeated_times_are_disambiguated(hour, zone, h12, clock):
    t = datetime(2026, 10, 25, hour, 30, tzinfo=UTC)
    assert job_hm(t, h12) == clock + ' ' + zone
    assert day_hm(t, t, h12) == clock + ' ' + zone


def test_ordinary_and_spring_times_remain_short():
    for t, expected in [(datetime(2026, 10, 25, 2, 30, tzinfo=UTC), '02:30'),
                        (datetime(2027, 3, 28, 1, 30, tzinfo=UTC), '02:30')]:
        assert job_hm(t) == expected


@pytest.mark.parametrize('transition,zone', [
    (datetime(2026, 10, 25, 1, tzinfo=UTC), 'GMT'),
    (datetime(2027, 3, 28, 1, tzinfo=UTC), 'BST'),
])
@pytest.mark.parametrize('width', [44, 120])
def test_axis_marks_clock_change(transition, zone, width):
    cv = Canvas(width, 1)
    axis = Axis(0, width, transition - timedelta(hours=12))
    hour_ticks(cv, 0, axis, False)
    assert zone in cv.text()[0]


@pytest.mark.parametrize('hour,zone', [(0, 'BST'), (1, 'GMT')])
def test_repeated_hour_job_in_frame_and_line(st, hour, zone):
    from gridhour.compose import compose
    from gridhour.grid import SLOT, Slot
    from gridhour.output import ical_output, json_output, line_output
    from gridhour.plan import Job

    now = datetime(2026, 10, 24, 22, tzinfo=UTC)
    start = datetime(2026, 10, 25, hour, 30, tzinfo=UTC)
    st.fc.slots = [Slot(now + SLOT * k, carbon=10 if now + SLOT * k == start else 300,
                        price=10) for k in range(96)]
    st.mode = 'green'
    st.jobs = [Job('Dryer', 30)]
    frame = '\n'.join(compose(180, 40, st, now, now).text())
    assert '01:30 ' + zone in frame
    assert 'start Sun 01:30 ' + zone in frame.splitlines()[-2]
    assert 'best 01:30 ' + zone in line_output(st, now, best=st.jobs[0])
    assert start.strftime('%Y-%m-%dT%H:%MZ') in json_output(st, now)
    assert start.strftime('%Y%m%dT%H%M%SZ') in ical_output(st, now)


@pytest.mark.parametrize('width', [63, 72, 120])
@pytest.mark.parametrize('h12', [False, True])
def test_clock_change_preserves_midnight_day_label(width, h12):
    cv = Canvas(width, 1)
    axis = Axis(0, width, datetime(2026, 10, 24, 22, tzinfo=UTC))
    hour_ticks(cv, 0, axis, h12, small=True)
    row = cv.text()[0]
    assert 'Sun' in row
    assert 'GMT' in row
    assert row.index('Sun') + 3 <= row.index('GMT')
