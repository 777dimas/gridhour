import json
import os
import socket
from datetime import UTC, datetime

import pytest

from gridhour.grid import load
from gridhour.state import State
from gridhour.themes import apply_theme

FX = os.path.join(os.path.dirname(__file__), "fixtures")
NOW = datetime(2026, 10, 3, 22, 46, tzinfo=UTC)


def fixture(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return json.load(f)


def fake_fetch(url):
    if "carbonintensity" in url:
        return fixture("carbon_sw1a.json")
    if "standard-unit-rates" in url:
        return fixture("go_c.json" if "GO-FIX" in url else "agile_c.json")
    return fixture("products.json")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """No test touches the real config, cache or network."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.delenv("GRIDHOUR_OFFLINE", raising=False)

    def no_network(url, timeout=12):
        raise AssertionError("tests must not hit the network: " + url)

    def no_socket(*args, **kwargs):
        raise AssertionError("tests must not open network connections")

    monkeypatch.setattr("gridhour.grid.http_json", no_network)
    # and below that, in case some code path ever reaches the network without http_json
    monkeypatch.setattr(socket.socket, "connect", no_socket)
    monkeypatch.setattr(socket, "create_connection", no_socket)
    monkeypatch.setattr(socket, "getaddrinfo", no_socket)
    apply_theme("carbon")


@pytest.fixture
def fc():
    return load(NOW, "SW1A", fetch=fake_fetch)


@pytest.fixture
def st(fc):
    s = State()
    s.persist = False
    s.postcode = "SW1A"
    s.fc = fc
    return s
