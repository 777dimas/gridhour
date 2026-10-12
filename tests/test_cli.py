import json

import pytest
from conftest import fake_fetch

from gridhour import cli, grid


@pytest.fixture(autouse=True)
def fixture_network(monkeypatch):
    monkeypatch.setattr(grid, "http_json", lambda url, timeout=12: fake_fetch(url))


def test_line(capsys):
    cli.main(["SW1A", "1AA", "--line", "--at", "2026-10-03T22:46Z"])
    assert capsys.readouterr().out.strip() == "⚡ 251g · 30p · green in 7h30"


def test_postcode_is_remembered(capsys):
    cli.main(["SW1A", "--line", "--at", "2026-10-03T22:46Z"])
    capsys.readouterr()
    cli.main(["--json", "--at", "2026-10-03T22:46Z"])
    assert json.loads(capsys.readouterr().out)["region"]["postcode"] == "SW1A"


def test_tmux(capsys):
    cli.main(["SW1A", "--tmux", "--at", "2026-10-03T22:46Z"])
    assert "#[fg=#" in capsys.readouterr().out


def test_once(capsys):
    cli.main(["SW1A", "--once", "--size", "100x30", "--at", "2026-10-03T22:46Z"])
    out = capsys.readouterr().out
    assert out.count("\n") == 30 and "\x1b[" in out


def test_bad_postcode():
    with pytest.raises(SystemExit, match="not a UK postcode"):
        cli.main(["hello", "--line"])


def test_reset(capsys):
    cli.main(["SW1A", "--line", "--at", "2026-10-03T22:46Z"])
    cli.main(["--reset"])
    assert "removed" in capsys.readouterr().out
    cli.main(["--reset"])
    assert "nothing to reset" in capsys.readouterr().out


def test_needs_a_terminal():
    with pytest.raises(SystemExit, match="interactive terminal"):
        cli.main([])


def test_ical(capsys):
    cli.main(["SW1A", "--ical", "--at", "2026-10-03T22:46Z"])
    out = capsys.readouterr().out

    assert out.startswith("BEGIN:VCALENDAR\r\n")
    assert out.endswith("END:VCALENDAR\r\n")
    assert "BEGIN:VEVENT\r\n" in out
    assert "SUMMARY:Washing (gridhour)\r\n" in out
    assert "DTSTAMP:20261003T224600Z\r\n" in out
    assert "\n" not in out.replace("\r\n", "")


def test_json_best_uses_ad_hoc_duration_without_saving_it(capsys):
    cli.main(["SW1A", "--json", "--at", "2026-10-03T22:46Z"])
    before = json.loads(capsys.readouterr().out)
    cli.main(["--json", "--best", "2h", "--at", "2026-10-03T22:46Z"])
    requested = json.loads(capsys.readouterr().out)
    assert requested["best"]["from"] == "2026-10-04T11:00Z"
    assert requested["best"]["to"] == "2026-10-04T13:00Z"
    assert requested["best"]["starts_in_minutes"] == 734
    assert requested["jobs"] == before["jobs"]
    cli.main(["--json", "--at", "2026-10-03T22:46Z"])
    after = json.loads(capsys.readouterr().out)
    assert "best" not in after
    assert after["jobs"] == before["jobs"]


def test_json_best_without_forecast_is_null(capsys):
    cli.main(["SW1A", "--json", "--best", "2h", "--at", "2030-01-01T00:00Z"])
    doc = json.loads(capsys.readouterr().out)
    assert doc["best"] is None
