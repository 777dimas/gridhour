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
