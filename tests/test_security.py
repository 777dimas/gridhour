"""Untrusted input: API responses, redirects, the cache, the config file, terminal output."""
import json
import os
import stat
import time

import pytest
from conftest import NOW, fake_fetch, fixture

from gridhour import cli, grid, output, state
from gridhour.canvas import Canvas
from gridhour.compose import compose
from gridhour.grid import http_json as REAL_HTTP_JSON  # bound before conftest blocks the network
from gridhour.safe import clean, label
from gridhour.themes import C, apply_theme


def carbon_doc(**row):
    """The fixture with its first row changed."""
    doc = fixture("carbon_sw1a.json")
    first = doc["data"]["data"][0]
    for k, v in row.items():
        if k == "forecast":
            first["intensity"]["forecast"] = v
        else:
            first[k] = v
    return doc


# ---------------------------------------------------------------- what reaches the terminal

def test_clean_strips_control_characters():
    assert clean("ok\x1b]52;c;bad\x07\x9b31m\x7f\ud800") == "ok?]52;c;bad??31m??"


def test_label_drops_bidi_zero_width_and_wide():
    assert label("Lon‮don​́ 東京") == "Lon?don?? ??"
    assert label(42) is None and label("x" * 100, 5) == "xxxxx"


def test_region_name_with_escapes_never_reaches_the_terminal(st):
    st.fc.region = "London\x1b]0;pwned\x07"
    st.fc.errors = ["network: \x1b[2J"]
    joined = "".join(compose(120, 40, st, NOW, NOW).lines())
    assert "\x1b]0;" not in joined and "\x07" not in joined and "\x1b[2J" not in joined


def test_canvas_put_cleans():
    cv = Canvas(10, 1)
    cv.put(0, 0, "a\x1bb")
    assert cv.text() == ["a?b       "]


def test_title_bar_has_no_double_width_glyph(st):
    import unicodedata
    for line in compose(120, 40, st, NOW, NOW).text():
        assert not any(unicodedata.east_asian_width(c) in "WF" for c in line), line


def test_tmux_output_cannot_inject_formats_or_commands(st):
    st.fc.slots = []
    st.fc.errors = ["oops #(touch /tmp/x) #[fg=red]"]
    out = output.line_output(st, NOW, "tmux")
    assert "#" not in out.replace("##", "")        # every '#' is an escaped literal
    assert "##(touch" in out and "##[fg=red]" in out


def test_line_output_cleans_errors(st):
    st.fc.slots = []
    st.fc.errors = ["\x1b[31mevil‮"]
    out = output.line_output(st, NOW)
    assert "\x1b" not in out and "‮" not in out


def test_json_is_ascii(st):
    st.fc.region = "x\x9b‮"
    out = output.json_output(st, NOW)
    assert out.isascii()


# ---------------------------------------------------------------- the network

class FakeResponse:
    def __init__(self, body, url="https://api.carbonintensity.org.uk/x", delay=0.0):
        self.body, self.url, self.delay = body, url, delay

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def geturl(self):
        return self.url

    def read(self, n):
        time.sleep(self.delay)
        chunk, self.body = self.body[:n], self.body[n:]
        return chunk


def test_oversized_response_is_refused(monkeypatch):
    monkeypatch.setattr(grid._OPENER, "open", lambda req, timeout: FakeResponse(b"[" * (grid.MAX_BYTES + 10)))
    with pytest.raises(ValueError, match="larger than"):
        REAL_HTTP_JSON(grid.CARBON_API + "/intensity")


def test_response_from_another_host_is_refused(monkeypatch):
    monkeypatch.setattr(grid._OPENER, "open", lambda req, timeout: FakeResponse(b"{}", "http://evil.example/"))
    with pytest.raises(ValueError, match="somewhere else"):
        REAL_HTTP_JSON(grid.CARBON_API + "/intensity")


def test_slow_drip_hits_the_deadline(monkeypatch):
    monkeypatch.setattr(grid, "DEADLINE", 0.05)
    monkeypatch.setattr(grid._OPENER, "open", lambda req, timeout: FakeResponse(b"x" * 10_000_000, delay=0.03))
    with pytest.raises(TimeoutError):
        REAL_HTTP_JSON(grid.CARBON_API + "/intensity")


def test_redirects_are_refused():
    import urllib.request
    handler = grid._RefuseRedirects()
    req = urllib.request.Request(grid.CARBON_API + "/x")
    with pytest.raises(grid.urllib.error.HTTPError, match="redirect refused"):
        handler.redirect_request(req, None, 302, "Found", {}, "http://evil.example/")
    assert any(isinstance(h, grid._RefuseRedirects) for h in grid._OPENER.handlers)
    assert not any(type(h) is urllib.request.HTTPRedirectHandler for h in grid._OPENER.handlers)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://api.octopus.energy/v1/", "https://evil.example/",
                                 "https://api.octopus.energy.evil.example/", None, 42])
def test_only_the_two_api_hosts_over_https(url):
    with pytest.raises(ValueError, match="refusing"):
        REAL_HTTP_JSON(url)


# ---------------------------------------------------------------- hostile responses

@pytest.mark.parametrize("doc", [[], "x", {"data": "x"}, {"data": {"data": [{"from": "x"}]}},
                                 {"data": {"data": [{"from": "2026-10-03T20:00Z", "intensity": {"forecast": "x"}}]}},
                                 {"data": {"data": "x" * 10}}, {"data": [[]]}])
def test_garbage_carbon_response_is_an_error_not_a_crash(doc):
    fc = grid.load(NOW, "SW1A", fetch=lambda url: doc if "carbon" in url else fake_fetch(url))
    assert fc.errors and len(fc.slots) == 96


@pytest.mark.parametrize("value", [1e999, float("nan"), -5, 99999, True, "200", None, [1]])
def test_bad_numbers_cost_one_slot(value):
    fc = grid.load(NOW, "SW1A", fetch=lambda url: carbon_doc(forecast=value) if "carbon" in url else fake_fetch(url))
    assert not fc.errors
    assert fc.slots[0].carbon is not None          # the window starts at 20:00, the bad row is 19:30


@pytest.mark.parametrize("field,value", [("regionid", [1]), ("regionid", True), ("shortname", 5),
                                         ("shortname", "\ud800\x1b[2J"), ("postcode", {"a": 1})])
def test_bad_region_fields_do_not_crash(field, value, st):
    doc = fixture("carbon_sw1a.json")
    doc["data"][field] = value
    fc = grid.load(NOW, "SW1A", fetch=lambda url: doc if "carbon" in url else fake_fetch(url))
    st.fc = fc
    compose(120, 40, st, NOW, NOW).lines()
    output.json_output(st, NOW).encode("ascii")
    assert fc.region and "\x1b" not in fc.region


def test_bad_index_and_fuel_names_are_dropped():
    doc = fixture("carbon_sw1a.json")
    row = doc["data"]["data"][2]
    row["intensity"]["index"] = ["x"]
    row["generationmix"] = [{"fuel": 7, "perc": 3}, {"fuel": "wind", "perc": "9"}, {"fuel": "\x1b", "perc": 1},
                            {"fuel": "gas", "perc": 50}]
    _, data = grid.parse_carbon(doc)
    g, idx, mix = data[grid.parse_time(row["from"])]
    assert idx is None and mix == {"gas": 50.0}


@pytest.mark.parametrize("price", [1e400, "nan", float("inf"), "12", None, True])
def test_bad_prices_are_skipped(price, st):
    doc = fixture("agile_c.json")
    for r in doc["results"]:
        r["value_inc_vat"] = price
    fc = grid.load(NOW, "SW1A", force=True,
                   fetch=lambda url: doc if "standard-unit-rates" in url else fake_fetch(url))
    st.fc = fc
    assert not fc.has_prices
    output.line_output(st, NOW)
    compose(120, 40, st, NOW, NOW).lines()


@pytest.mark.parametrize("doc", [[], {"results": "x"}, {"results": [{"valid_from": "nope"}]}])
def test_garbage_price_response_has_no_prices(doc):
    fc = grid.load(NOW, "SW1A", fetch=lambda url: doc if "standard-unit-rates" in url else fake_fetch(url))
    assert not fc.has_prices


def test_deep_nesting_is_an_error_not_a_crash():
    def deep(url):
        return json.loads("[" * 100000 + "]" * 100000)
    fc = grid.load(NOW, "SW1A", fetch=deep)
    assert fc.errors


@pytest.mark.parametrize("code", ["AGILE-24-10-01/../../evil", "AGILE-24-10-01?x=1", "AGILE 24", "../AGILE-1",
                                  "AGILE-24-10-01\n", "AGILE-24-10-01\r\nX: y", "AGILE-٢٤"])
def test_hostile_product_codes_are_ignored(code):
    assert grid.pick_agile({"results": [{"code": code, "direction": "IMPORT"}]}) == grid.FALLBACK_AGILE


def test_price_url_refuses_bad_parts():
    with pytest.raises(ValueError):
        grid.prices_url("AGILE-1/../x", "C", NOW, NOW)
    with pytest.raises(ValueError):
        grid.prices_url("AGILE-24-10-01\n", "C", NOW, NOW)
    with pytest.raises(ValueError):
        grid.prices_url("AGILE-24-10-01", "Z/..", NOW, NOW)


# ---------------------------------------------------------------- the cache

def test_a_broken_response_is_never_cached():
    grid.load(NOW, "SW1A", fetch=lambda url: {"data": "poison"} if "carbon" in url else fake_fetch(url))
    assert not os.path.exists(os.path.join(grid.cache_dir(), "carbon-SW1A.json"))


def test_a_poisoned_cache_entry_counts_as_missing():
    os.makedirs(grid.cache_dir(), exist_ok=True)
    with open(os.path.join(grid.cache_dir(), "carbon-SW1A.json"), "w") as f:
        json.dump({"at": time.time(), "doc": {"data": {"data": [{"intensity": {"forecast": 1e999}}]}}}, f)
    fc = grid.load(NOW, "SW1A", fetch=fake_fetch)
    assert fc.region == "London" and not fc.errors


def test_a_cache_stamped_in_the_future_expires():
    grid.load(NOW, "SW1A", fetch=fake_fetch)
    path = os.path.join(grid.cache_dir(), "carbon-SW1A.json")
    box = json.load(open(path))
    box["at"] = 9e18
    json.dump(box, open(path, "w"))
    fetched = []
    grid.load(NOW, "SW1A", fetch=lambda url: fetched.append(url) or fake_fetch(url))
    assert any("carbon" in u for u in fetched)


def test_a_planted_symlink_is_not_followed(tmp_path):
    os.makedirs(grid.cache_dir(), exist_ok=True)
    victim = tmp_path / "victim"
    victim.write_text("keep me")
    for name in ("carbon-SW1A.tmp", ".tmp-carbon-SW1A.json"):
        os.symlink(victim, os.path.join(grid.cache_dir(), name))
    grid.load(NOW, "SW1A", fetch=fake_fetch)
    assert victim.read_text() == "keep me"
    assert not os.path.islink(os.path.join(grid.cache_dir(), "carbon-SW1A.json"))


def test_existing_loose_permissions_are_tightened(st):
    os.makedirs(grid.cache_dir(), mode=0o755, exist_ok=True)
    os.chmod(grid.cache_dir(), 0o755)
    path = os.path.join(grid.cache_dir(), "carbon-SW1A.json")
    with open(path, "w") as f:
        f.write("{}")
    os.chmod(path, 0o644)
    grid.load(NOW, "SW1A", force=True, fetch=fake_fetch)
    assert stat.S_IMODE(os.stat(grid.cache_dir()).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_config_and_cache_are_private(st):
    st.persist = True
    st.save()
    assert stat.S_IMODE(os.stat(state.config_path()).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(os.path.dirname(state.config_path())).st_mode) == 0o700
    grid.load(NOW, "SW1A", fetch=fake_fetch)
    for name in os.listdir(grid.cache_dir()):
        assert stat.S_IMODE(os.stat(os.path.join(grid.cache_dir(), name)).st_mode) == 0o600


# ---------------------------------------------------------------- the config file and arguments

@pytest.mark.parametrize("cfg", ['[1, 2]', '"x"', '{"postcode": "../../etc", "gsp": "Z/..", "region": 99}',
                                 '{"jobs": [{"name": "x", "minutes": 999999}]}', 'not json',
                                 '{"theme": [], "region": [], "gsp": {}, "mode": [], "compact": {}}',
                                 '{"jobs": [{"name": "x", "minutes": 1e400}], "region": true}',
                                 '{"jobs": [{"name": "\\u202e\\u001b[2J", "minutes": 60}]}',
                                 '{"postcode": "SW\\u0661"}', "[" * 50000 + "]" * 50000])
def test_hostile_config_is_survivable(cfg):
    path = state.config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(cfg)
    st = state.state_from_config()
    assert st.postcode is None and st.gsp is None and st.region_id is None
    assert all(30 <= j.minutes <= 24 * 60 and j.name.isprintable() and "‮" not in j.name for j in st.jobs)
    assert C.name == "carbon"


def test_apply_theme_with_junk():
    apply_theme([])
    assert C.name == "carbon"


@pytest.mark.parametrize("text", ["SW١", "١٢", "SW1A ١AA"])
def test_postcodes_are_ascii_only(text):
    with pytest.raises(ValueError):
        grid.normalize_postcode(text)


@pytest.mark.parametrize("args,msg", [(["--size", "abc", "--once"], "--size"),
                                      (["--size", "99999x99999", "--once"], "--size"),
                                      (["--at", "0001-01-01T00:00Z", "--line"], "2000"),
                                      (["--at", "yesterday", "--line"], "not a time")])
def test_bad_arguments_exit_cleanly(args, msg):
    with pytest.raises(SystemExit, match=msg):
        cli.main(args)


def test_at_without_offset_is_utc():
    assert grid.parse_time("2026-07-01T12:00") == grid.parse_time("2026-07-01T12:00Z")


def test_reset_removes_the_cache_with_the_postcode_in_its_name(capsys):
    grid.load(NOW, "SW1A", fetch=fake_fetch)
    assert any(n.startswith("carbon-SW1A") for n in os.listdir(grid.cache_dir()))
    cli.main(["--reset"])
    assert not any(n.startswith("carbon-") for n in os.listdir(grid.cache_dir()))
