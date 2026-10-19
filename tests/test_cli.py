import json
import os
import subprocess
import sys

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
    with pytest.raises(SystemExit) as exc:
        cli.main(["SW1A", "--json", "--best", "2h", "--at", "2030-01-01T00:00Z"])
    assert exc.value.code == 2
    doc = json.loads(capsys.readouterr().out)
    assert doc["best"] is None
    assert doc["slots"] == []


@pytest.mark.parametrize("args,check", [
    (["--json"], lambda out: json.loads(out)["slots"] == [] and bool(json.loads(out)["errors"])),
    (["--ical"], lambda out: out.startswith("BEGIN:VCALENDAR\r\n") and "BEGIN:VEVENT" not in out),
    (["--once", "--size", "80x24"], lambda out: out.count("\n") == 24 and "network: down" in out),
])
def test_script_modes_exit_2_without_forecast(monkeypatch, capsys, args, check):
    def broken(url, timeout=12):
        raise OSError("down")

    monkeypatch.setattr(grid, "http_json", broken)
    with pytest.raises(SystemExit) as exc:
        cli.main(["SW1A", "--at", "2026-10-03T22:46Z", *args])
    assert exc.value.code == 2
    assert check(capsys.readouterr().out)


@pytest.mark.parametrize("mode", ["--line", "--tmux"])
def test_status_bar_modes_keep_error_text_at_exit_0(monkeypatch, capsys, mode):
    def broken(url, timeout=12):
        raise OSError("down")

    monkeypatch.setattr(grid, "http_json", broken)
    cli.main(["SW1A", "--at", "2026-10-03T22:46Z", mode])
    assert capsys.readouterr().out.strip() == "⚡ network: down"


def test_partial_and_cached_forecasts_exit_0(monkeypatch, capsys):
    # Price-only partial forecast (carbon fails, prices succeed for a known region) -> exit 0
    def prices_only(url, timeout=12):
        if "carbonintensity" in url:
            raise OSError("carbon down")
        return fake_fetch(url)

    monkeypatch.setattr(grid, "http_json", prices_only)
    cli.main(["--region", "london", "--json", "--at", "2026-10-03T22:46Z"])
    doc = json.loads(capsys.readouterr().out)
    assert doc["slots"] and all(s["carbon"] is None and s["price"] is not None for s in doc["slots"])
    assert doc["errors"] == ["network: carbon down"]

    # Carbon-only partial forecast (prices fail, carbon succeeds) -> exit 0
    cli.main(["--reset"])
    capsys.readouterr()

    def carbon_only(url, timeout=12):
        if "octopus" in url:
            raise OSError("prices down")
        return fake_fetch(url)

    monkeypatch.setattr(grid, "http_json", carbon_only)
    cli.main(["SW1A", "--line", "--at", "2026-10-03T22:46Z"])
    assert capsys.readouterr().out.strip() == "⚡ 251g · green in 7h30"

    # Cached forecast served when live refresh fails (errors present, data present) -> exit 0
    monkeypatch.setattr(grid, "http_json", lambda url, timeout=12: fake_fetch(url))
    cli.main(["SW1A", "--line", "--at", "2026-10-03T22:46Z"])
    capsys.readouterr()
    monkeypatch.setattr(grid, "_read_cache", lambda key, _orig=grid._read_cache: (
        (1.0, _orig(key)[1]) if _orig(key)[1] is not None else (None, None)
    ))
    monkeypatch.setattr(grid, "http_json", lambda url, timeout=12: (_ for _ in ()).throw(OSError("offline now")))
    cli.main(["SW1A", "--json", "--at", "2026-10-03T22:46Z"])
    cached_doc = json.loads(capsys.readouterr().out)
    assert len(cached_doc["slots"]) == 96
    assert cached_doc["errors"]


def test_subprocess_offline_empty_cache_exits_2(tmp_path):
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(tmp_path / "cfg")
    env["XDG_CACHE_HOME"] = str(tmp_path / "cache")
    env["GRIDHOUR_OFFLINE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "gridhour", "SW1A", "--json", "--at", "2026-10-03T22:46Z"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert proc.stderr == ""
    doc = json.loads(proc.stdout)
    assert doc["slots"] == []
    assert doc["errors"] == ["offline and nothing cached yet"]
