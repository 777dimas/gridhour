"""Tariffs other than Agile: Octopus Go and friends, chosen with --tariff."""
import json
import os
from datetime import timedelta

import pytest
from conftest import NOW, fake_fetch, fixture

from gridhour import cli, grid, output, plan, state
from gridhour.compose import compose
from gridhour.grid import SLOT

GO = "GO-FIX-12M-25-08-29"


@pytest.mark.parametrize("text,out", [
    ("agile", (None, None)), ("", (None, None)), ("AGILE", (None, None)),
    (GO, (GO, None)), (GO.lower(), (GO, None)),
    ("E-1R-%s-E" % GO, (GO, "E")), (" e-1r-%s-c " % GO, (GO, "C")),
    ("VAR-22-11-01", ("VAR-22-11-01", None)),
])
def test_normalize_tariff(text, out):
    assert grid.normalize_tariff(text) == out


@pytest.mark.parametrize("text,msg", [
    ("E-2R-GO-FIX-12M-25-08-29-E", "two-rate"), ("AGILE-OUTGOING-19-05-13", "export"),
    ("GO/../x", "not an Octopus tariff"), ("GO-FIX?x=1", "not an Octopus tariff"), ("go", "not an Octopus tariff"),
    ("X-" + "A" * 70, "not an Octopus tariff"), ("GO-FIX\n-12M", "not an Octopus tariff"),
    ("GO-ＦIX-1", "not an Octopus tariff"),
])
def test_normalize_tariff_rejects(text, msg):
    with pytest.raises(ValueError, match=msg):
        grid.normalize_tariff(text)


def test_tariff_names():
    assert [grid.tariff_name(p) for p in (None, "AGILE-24-10-01", GO, "INTELLI-VAR-24-10-29",
                                          "SILVER-24-12-31", "VAR-22-11-01")] == \
        ["Agile", "Agile", "Go", "Intelligent Go", "Tracker", "Flexible"]


def test_intervals_spread_over_half_hours_inside_the_window_only():
    start = NOW.replace(hour=0, minute=0)
    end = start + timedelta(hours=6)
    doc = {"results": [
        {"valid_from": "2026-10-01T00:00Z", "valid_to": None, "value_inc_vat": 20.0},          # open-ended
        {"valid_from": "2026-10-03T01:00Z", "valid_to": "2026-10-03T02:00Z", "value_inc_vat": 5.0},
    ]}
    prices = grid.parse_prices(doc, start, end)
    assert len(prices) == 12                                      # 6 hours of half hours, nothing outside
    assert prices[start] == 20.0
    assert prices[start + timedelta(hours=1)] == 20.0             # first row listed wins, as Octopus orders them
    assert grid.parse_prices({"results": [{"valid_from": "2020-01-01T00:00Z", "valid_to": None,
                                           "value_inc_vat": 1.0}]}, start, end) == {start + SLOT * i: 1.0
                                                                                    for i in range(12)}


def test_repeat_daily_borrows_the_same_time_on_an_earlier_day():
    day = NOW.replace(hour=0, minute=0)
    known = {day + SLOT * i: (4.75 if i < 10 else 25.1) for i in range(48)}
    filled = grid.repeat_daily(known, day, day + timedelta(days=2))
    assert len(filled) == 96
    assert filled[day + timedelta(days=1)] == 4.75 and filled[day + timedelta(days=1, hours=12)] == 25.1
    assert grid.repeat_daily({}, day, day + SLOT * 4) == {}     # nothing to repeat: stays empty


def test_load_with_go(st):
    calls = []

    def logged(url):
        calls.append(url)
        return fake_fetch(url)

    fc = grid.load(NOW, "SW1A", tariff=GO, fetch=logged)
    assert fc.tariff == "E-1R-%s-C" % GO and fc.tariff_name == "Go"
    assert not any("is_variable" in u for u in calls)             # no Agile product lookup
    assert all(s.price is not None for s in fc.slots)
    assert {s.price for s in fc.slots} == {4.755, 24.6932}       # exact API values, VAT included
    night = [s for s in fc.slots if s.price < 10]
    assert {s.start.astimezone(plan.UK).strftime("%H:%M") for s in night} >= {"00:30", "05:00"}
    assert not {s.start.astimezone(plan.UK).strftime("%H:%M") for s in night} & {"00:00", "05:30"}


def test_go_and_agile_are_cached_separately():
    grid.load(NOW, "SW1A", fetch=fake_fetch)
    grid.load(NOW, "SW1A", tariff=GO, fetch=fake_fetch)
    names = os.listdir(grid.cache_dir())
    assert "prices-C.json" in names and "prices-%s-C.json" % GO.lower() in names


def test_go_jobs_land_in_the_cheap_night(st):
    st.fc = grid.load(NOW, "SW1A", tariff=GO, fetch=fake_fetch)
    for mode in ("cheap", "both"):
        st.mode = mode
        sc = plan.scores(st.fc.slots, mode)
        w = plan.best_window(st.fc.slots, sc, plan.Job("Washing", 120), NOW)
        local = w.start.astimezone(plan.UK)
        assert w.price < 5 and (local.hour, local.minute) >= (0, 30) and local.hour < 6


def test_go_screen_says_go_and_skips_the_4pm_note(st):
    st.fc = grid.load(NOW, "SW1A", tariff=GO, fetch=fake_fetch)
    text = "\n".join(compose(120, 40, st, NOW, NOW).text())
    assert "Go C" in text and "Agile" not in text.splitlines()[0]
    assert "4pm" not in text


def test_json_reports_the_tariff(st):
    st.fc = grid.load(NOW, "SW1A", tariff=GO, fetch=fake_fetch)
    assert json.loads(output.json_output(st, NOW))["tariff"] == "E-1R-%s-C" % GO


def test_cli_tariff_is_remembered_and_sets_the_region(monkeypatch, capsys):
    monkeypatch.setattr(grid, "http_json", lambda url, timeout=12: fake_fetch(url))
    cli.main(["SW1A", "--tariff", "E-1R-%s-E" % GO, "--line", "--at", "2026-10-03T22:46Z"])
    st = state.state_from_config()
    assert st.tariff == GO and st.gsp == "E"
    cli.main(["--tariff", "agile", "--line", "--at", "2026-10-03T22:46Z"])
    st = state.state_from_config()
    assert st.tariff is None and st.gsp is None
    capsys.readouterr()


def test_cli_rejects_a_bad_tariff():
    with pytest.raises(SystemExit, match="not an Octopus tariff"):
        cli.main(["--tariff", "GO/../../etc", "--line"])


@pytest.mark.parametrize("value", ["GO/../x", 42, ["GO-FIX-1"], "E-2R-GO-FIX-12M-25-08-29-E", "\x1b[2J"])
def test_hostile_tariff_in_config_is_ignored(value):
    path = state.config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"tariff": value}, f)
    assert state.state_from_config().tariff is None


def test_fixture_is_a_real_go_response():
    rows = fixture("go_c.json")["results"]
    assert {r["value_inc_vat"] for r in rows} == {4.755, 24.6932}
