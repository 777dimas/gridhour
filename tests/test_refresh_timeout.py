"""One stalled network request must not multiply a refresh's deadline."""

import time
import urllib.error
from threading import BoundedSemaphore, Event

from conftest import NOW, fake_fetch

from gridhour import grid
from gridhour.grid import http_json as REAL_HTTP_JSON


def test_hanging_opener_uses_one_deadline_and_cached_forecast(monkeypatch):
    grid.load(NOW, "SW1A", fetch=fake_fetch)
    release = Event()
    calls = []

    def hanging(req, timeout):
        calls.append(req.full_url)
        release.wait(2)
        raise TimeoutError("simulated offline resolver")

    monkeypatch.setattr(grid._OPENER, "open", hanging)
    monkeypatch.setattr(grid, "_REQUEST_SLOTS", BoundedSemaphore(2))
    monkeypatch.setattr(grid, "DEADLINE", 0.1)
    start = time.monotonic()
    try:
        forecast = grid.load(NOW, "SW1A", force=True, fetch=REAL_HTTP_JSON)
        elapsed = time.monotonic() - start
        assert len(calls) == 1
        assert elapsed < 0.5
        assert len(forecast.errors) == 1
        assert forecast.region == "London"
        assert forecast.has_prices
        assert all(slot.carbon is not None for slot in forecast.slots)
    finally:
        release.set()


def test_product_timeout_skips_prices_and_next_refresh_recovers(monkeypatch):
    grid.load(NOW, "SW1A", fetch=fake_fetch)
    grid._write_cache("agile-product", {})
    calls = []

    def broken_product(url):
        calls.append(url)
        if "/products/?" in url:
            raise urllib.error.URLError(TimeoutError("deadline"))
        return fake_fetch(url)

    forecast = grid.load(NOW, "SW1A", force=True, fetch=broken_product)
    assert len(calls) == 2
    assert forecast.has_prices
    assert len(forecast.errors) == 1
    assert "deadline" in forecast.errors[0]
    calls.clear()

    def healthy(url):
        calls.append(url)
        return fake_fetch(url)

    recovered = grid.load(NOW, "SW1A", force=True, fetch=healthy)
    assert len(calls) == 3
    assert recovered.errors == []


def test_non_timeout_errors_do_not_disable_other_requests():
    calls = []

    def bad_carbon(url):
        calls.append(url)
        if "carbonintensity" in url:
            raise ValueError("invalid JSON shape")
        return fake_fetch(url)

    forecast = grid.load(NOW, "SW1A", gsp="C", force=True, fetch=bad_carbon)
    assert len(calls) == 3
    assert forecast.has_prices
    assert len(forecast.errors) == 1


def test_timeout_without_cache_keeps_one_error_and_no_fabricated_data():
    calls = []

    def timeout(url):
        calls.append(url)
        raise TimeoutError("deadline")

    forecast = grid.load(NOW, "SW1A", gsp="C", fetch=timeout)
    assert len(calls) == 1
    assert len(forecast.errors) == 1
    assert not forecast.has_prices
    assert all(slot.carbon is None for slot in forecast.slots)
