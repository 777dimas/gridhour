from datetime import UTC, datetime

import pytest
from conftest import NOW, fake_fetch, fixture

from gridhour import grid


@pytest.mark.parametrize("text,out", [
    ("SW1A 1AA", "SW1A"), ("sw1a1aa", "SW1A"), ("SW1A", "SW1A"), (" m1 ", "M1"), ("EH1 1YZ", "EH1"),
    ("CF10", "CF10"), ("B338TH", "B33"),
])
def test_normalize_postcode(text, out):
    assert grid.normalize_postcode(text) == out


@pytest.mark.parametrize("text", ["", "hello", "12345", "SW1A 1AA 2"])
def test_normalize_postcode_rejects(text):
    with pytest.raises(ValueError):
        grid.normalize_postcode(text)


def test_northern_ireland_is_explained():
    with pytest.raises(ValueError, match="Northern Ireland"):
        grid.normalize_postcode("BT1 5GS")


@pytest.mark.parametrize("text,rid", [("13", 13), ("C", 13), ("_c", 13), ("london", 13), ("north scot", 1),
                                      ("GB", 18), ("Scotland", 16)])
def test_region_from_arg(text, rid):
    assert grid.region_from_arg(text) == rid


def test_every_dno_region_has_its_own_letter():
    letters = [gsp for _, gsp in grid.REGIONS.values() if gsp]
    assert len(letters) == len(set(letters)) == 14


def test_parse_carbon():
    info, data = grid.parse_carbon(fixture("carbon_sw1a.json"))
    assert info == {"region_id": 13, "region": "London", "postcode": "SW1A"}
    first = min(data)
    assert first == datetime(2026, 10, 3, 19, 30, tzinfo=UTC)
    g, idx, mix = data[first]
    assert isinstance(g, int) and idx and abs(sum(mix.values()) - 100) < 1


def test_parse_carbon_null_means_no_data():
    with pytest.raises(ValueError):
        grid.parse_carbon({"data": None})


def test_parse_prices():
    prices = grid.parse_prices(fixture("agile_c.json"))
    assert len(prices) == 52
    assert prices[datetime(2026, 10, 3, 22, 30, tzinfo=UTC)] == 30.18


def test_pick_agile_ignores_outgoing():
    assert grid.pick_agile(fixture("products.json")) == "AGILE-24-10-01"
    doc = {"results": [{"code": "AGILE-24-10-01", "direction": "IMPORT"},
                       {"code": "AGILE-26-04-01", "direction": "IMPORT"},
                       {"code": "AGILE-OUTGOING-19-05-13", "direction": "EXPORT"},
                       {"code": "AGILE-22-08-31", "direction": "IMPORT", "available_to": "2023-01-01"}]}
    assert grid.pick_agile(doc) == "AGILE-26-04-01"
    assert grid.pick_agile({"results": []}) == grid.FALLBACK_AGILE


def test_load_builds_48_hours(fc):
    assert fc.region == "London" and fc.gsp == "C"
    assert fc.tariff == "E-1R-AGILE-24-10-01-C"
    assert len(fc.slots) == 96
    assert fc.slots[0].start == datetime(2026, 10, 3, 20, 0, tzinfo=UTC)
    assert all(s.carbon is not None for s in fc.slots)
    assert fc.has_prices and fc.slots[-1].price is None      # tomorrow's prices are not out yet
    assert fc.at(NOW).start == datetime(2026, 10, 3, 22, 30, tzinfo=UTC)


def test_load_without_prices():
    fc = grid.load(NOW, "SW1A", prices=False, fetch=fake_fetch)
    assert fc.gsp is None and not fc.has_prices


def test_cache_is_used_when_offline(monkeypatch):
    grid.load(NOW, "SW1A", fetch=fake_fetch)
    monkeypatch.setenv("GRIDHOUR_OFFLINE", "1")
    fc = grid.load(NOW, "SW1A", force=True, fetch=lambda url: pytest.fail("fetched while offline"))
    assert fc.region == "London" and fc.has_prices and not fc.errors


def test_network_failure_falls_back_to_stale_cache():
    grid.load(NOW, "SW1A", fetch=fake_fetch)

    def broken(url):
        raise OSError("no route to host")

    fc = grid.load(NOW, "SW1A", force=True, fetch=broken)
    assert fc.region == "London" and fc.slots[10].carbon is not None
    assert fc.errors and "no route" in fc.errors[0]


def test_network_failure_with_empty_cache():
    def broken(url):
        raise OSError("down")

    fc = grid.load(NOW, "SW1A", fetch=broken)
    assert fc.errors and all(s.carbon is None for s in fc.slots)
