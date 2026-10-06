"""Forecast data: carbon intensity from the NESO Carbon Intensity API and Agile prices from Octopus.

Both APIs are free and need no key. Responses are cached under ~/.cache/gridhour so the app
starts instantly and keeps working without a network, with the age of the data shown on screen.
"""
import http.client
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import Future
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import BoundedSemaphore, Thread

from . import __version__
from .safe import atomic_write, label

CARBON_API = "https://api.carbonintensity.org.uk"
OCTOPUS_API = "https://api.octopus.energy/v1"
FALLBACK_AGILE = "AGILE-24-10-01"
AGILE_PRODUCTS_URL = "https://api.octopus.energy/v1/products/?brand=OCTOPUS_ENERGY&is_variable=true&page_size=100"
SLOT = timedelta(minutes=30)
WINDOW_SLOTS = 96               # 48 hours
PAST = timedelta(hours=2)       # how much of the timeline lies before now
MAX_AGE = 30 * 60               # seconds before cached data is refetched
MAX_BYTES = 4 * 1024 * 1024     # a 48 hour forecast is about 40 kB; anything this big is not one
DEADLINE = 25                   # seconds for a whole request, however slowly the bytes trickle in
MAX_ROWS = 2000                 # rows looked at in one response
PRODUCT_CODE = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+){1,8}", re.ASCII)    # always used with fullmatch
TARIFF_CODE = re.compile(r"E-1R-(?P<product>[A-Z0-9-]+)-(?P<gsp>[A-P])", re.ASCII)
CACHE_KEY = re.compile(r"[a-z]+(?:-[A-Za-z0-9]+)+", re.ASCII)
REPEAT_DAYS = 7                 # how far back a fixed tariff's daily pattern may be borrowed from
ALLOWED = ("https://api.carbonintensity.org.uk/", "https://api.octopus.energy/")
FUELS = {"biomass", "coal", "imports", "gas", "nuclear", "other", "hydro", "solar", "wind"}
INDEXES = {"very low", "low", "moderate", "high", "very high"}

# Carbon Intensity API region id -> (short name, Octopus grid supply point group).
# The fourteen DNO regions are the same areas in both APIs; 15-18 are whole nations.
REGIONS = {
    1: ("North Scotland", "P"), 2: ("South Scotland", "N"), 3: ("North West England", "G"),
    4: ("North East England", "F"), 5: ("Yorkshire", "M"), 6: ("North Wales & Merseyside", "D"),
    7: ("South Wales", "K"), 8: ("West Midlands", "E"), 9: ("East Midlands", "B"), 10: ("East England", "A"),
    11: ("South West England", "L"), 12: ("South England", "H"), 13: ("London", "C"),
    14: ("South East England", "J"), 15: ("England", None), 16: ("Scotland", None), 17: ("Wales", None),
    18: ("GB", None),
}
GSP_REGION = {gsp: rid for rid, (_, gsp) in REGIONS.items() if gsp}
GREEN_INDEX = ("very low", "low")


@dataclass
class Slot:
    start: datetime                 # UTC, on a half hour
    carbon: int = None              # gCO2/kWh
    index: str = None               # "very low" ... "very high", as the API grades it
    mix: dict = None                # fuel -> percent
    price: float = None             # p/kWh including VAT

    @property
    def end(self):
        return self.start + SLOT

    @property
    def green(self):
        return self.index in GREEN_INDEX


@dataclass
class Forecast:
    region: str = "GB"
    region_id: int = 18
    postcode: str = None
    gsp: str = None                 # Octopus region letter, None when prices are off
    tariff: str = None
    tariff_name: str = "Agile"      # short name for the title bar
    slots: list = field(default_factory=list)
    fetched: float = 0.0            # unix time of the oldest data shown
    errors: list = field(default_factory=list)

    def at(self, t):
        """The slot that contains ``t``, or None."""
        for s in self.slots:
            if s.start <= t < s.end:
                return s
        return None

    @property
    def has_prices(self):
        return any(s.price is not None for s in self.slots)


# ---------------------------------------------------------------- where

OUTCODE = re.compile(r"[A-Z]{1,2}[0-9][A-Z0-9]?", re.ASCII)


def normalize_postcode(text):
    """Return the outward code ("SW1A") of a UK postcode, full or partial. Raises ValueError."""
    s = re.sub(r"\s+", " ", str(text or "").strip().upper())
    if " " in s:
        s, _, inward = s.partition(" ")
        if not re.fullmatch(r"[0-9]([A-Z]{2})?", inward, re.ASCII):
            raise ValueError("not a UK postcode: %r" % text)
    elif len(s) >= 5 and re.search(r"[0-9][A-Z]{2}$", s, re.ASCII):
        s = s[:-3]
    if not OUTCODE.fullmatch(s):
        raise ValueError("not a UK postcode: %r" % text)
    if s.startswith("BT"):
        raise ValueError("Northern Ireland is not on the GB grid, so there is no forecast for BT postcodes")
    return s


def region_from_arg(text):
    """Accept a region id (13), an Octopus letter (C) or a name (london). Returns the region id."""
    t = str(text or "").strip()
    if t.isascii() and t.isdigit() and int(t) in REGIONS:
        return int(t)
    if t.upper().lstrip("_") in GSP_REGION:
        return GSP_REGION[t.upper().lstrip("_")]
    low = t.lower()
    for rid, (name, _) in REGIONS.items():
        if name.lower() == low:
            return rid
    for rid, (name, _) in REGIONS.items():
        if name.lower().startswith(low) and low:
            return rid
    raise ValueError("unknown region %r (try 1-18, a letter A-P, or a name like 'london')" % text)


def normalize_tariff(text):
    """'agile', a product code ('GO-FIX-12M-25-08-29') or a full tariff code from a bill
    ('E-1R-GO-FIX-12M-25-08-29-E') -> (product or None for Agile, region letter or None).
    Raises ValueError."""
    t = str(text or "").strip().upper()
    if t in ("", "AGILE"):
        return None, None
    if t.startswith("E-2R-"):
        raise ValueError("two-rate meters (E-2R, Economy 7 style) aren't supported yet")
    gsp = None
    m = TARIFF_CODE.fullmatch(t)
    if m:
        t, gsp = m.group("product"), m.group("gsp")
    if len(t) > 60 or not PRODUCT_CODE.fullmatch(t):
        raise ValueError("not an Octopus tariff code: %r (try GO-FIX-12M-25-08-29, or 'agile')" % text)
    if "OUTGOING" in t or "EXPORT" in t:
        raise ValueError("that's an export tariff; gridhour needs the tariff you buy electricity on")
    return t, gsp


MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december")


def resolve_tariff_name(name, fetch=None):
    """'Octopus Go 12M Fixed August 2025 v1' (as the Octopus app shows it) -> its product code.

    A version stays on sale for a few months, starting some time in the month it's named after,
    so ask which products were on sale on the 1st and 15th of that month and the next six, and
    stop at the first one whose full name matches. Raises ValueError."""
    text = " ".join(str(name or "").split())
    if not 5 <= len(text) <= 80 or not text.isprintable():
        raise ValueError("give the tariff name as the Octopus app shows it, e.g. 'Octopus Go 12M Fixed August 2025 v1'")
    m = re.search(r"\b(%s)\s+(20[0-9]{2})\b" % "|".join(MONTHS), text.lower(), re.ASCII)
    if not m:
        raise ValueError("the tariff name needs its month and year, like 'August 2025'; "
                         "or pass the tariff code instead")
    month, year = MONTHS.index(m.group(1)) + 1, int(m.group(2))
    wanted = text.lower()
    for k in range(7):
        y, mo = year + (month - 1 + k) // 12, (month - 1 + k) % 12 + 1
        for day in (1, 15):
            url = ("%s/products/?brand=OCTOPUS_ENERGY&available_at=%04d-%02d-%02dT12:00:00Z&page_size=100"
                   % (OCTOPUS_API, y, mo, day))
            try:
                rows = _rows((fetch or http_json)(url), "results")
            except FETCH_ERRORS as e:
                raise ValueError("couldn't look the tariff up (%s); try the tariff code instead" % _why(e)) from None
            for p in rows:
                code, full = p.get("code"), p.get("full_name")
                if (isinstance(code, str) and isinstance(full, str) and PRODUCT_CODE.fullmatch(code)
                        and " ".join(full.split()).lower() == wanted):
                    return code
    raise ValueError("no Octopus tariff called %r; check the name in the app, or use the tariff code" % text)


def tariff_name(product):
    """A short name for the title bar."""
    if not product or product.startswith("AGILE-"):
        return "Agile"
    for prefix, name in (("GO-", "Go"), ("INTELLI-", "Intelligent Go"), ("SILVER-", "Tracker"),
                         ("COSY-", "Cosy"), ("VAR-", "Flexible")):
        if product.startswith(prefix):
            return name
    return product[:24]


# ---------------------------------------------------------------- time

def floor_slot(t):
    return t.replace(minute=t.minute - t.minute % 30, second=0, microsecond=0)


def window_start(now):
    return now.replace(minute=0, second=0, microsecond=0) - PAST


def iso(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")


TIME = re.compile(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:?\d\d)?", re.ASCII)


def parse_time(s):
    """ISO 8601 -> aware UTC datetime. Without an offset the time is taken as UTC."""
    if not isinstance(s, str) or not TIME.fullmatch(s.strip()):
        raise ValueError("not a time: %r" % (s if isinstance(s, str) and len(s) < 40 else type(s).__name__))
    s = s.strip().replace("Z", "+00:00")
    if re.search(r"T\d\d:\d\d[+-]", s):
        s = s[:16] + ":00" + s[16:]
    try:
        t = datetime.fromisoformat(s)
        if t.tzinfo is None:
            t = t.replace(tzinfo=UTC)
        return t.astimezone(UTC)
    except (ValueError, OverflowError) as e:
        raise ValueError("not a time: %r" % s) from e


# ---------------------------------------------------------------- parsing (everything here is untrusted)

def number(v, lo, hi):
    """A finite real number within [lo, hi]. Booleans and strings are refused."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError("not a number")
    f = float(v)
    if not math.isfinite(f) or not lo <= f <= hi:
        raise ValueError("number out of range")
    return f


def _rows(container, key):
    rows = container.get(key) if isinstance(container, dict) else None
    if not isinstance(rows, list):
        raise ValueError("unexpected response")
    return [r for r in rows[:MAX_ROWS] if isinstance(r, dict)]


def parse_carbon(doc):
    """Regional fw48h response -> (region info dict, {start: (carbon, index, mix)})."""
    data = doc.get("data") if isinstance(doc, dict) else None
    if isinstance(data, list):          # the regionid endpoint wraps the region in a list
        data = data[0] if data else None
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ValueError("no carbon intensity data for that place")
    rid = data.get("regionid")
    info = {"region_id": rid if type(rid) is int and rid in REGIONS else None,
            "region": label(data.get("shortname"), 30), "postcode": label(data.get("postcode"), 8)}
    out = {}
    for row in _rows(data, "data"):
        try:
            it = row.get("intensity")
            if not isinstance(it, dict) or it.get("forecast") is None:
                continue
            g = int(number(it["forecast"], 0, 2000))
            idx = it.get("index")
            idx = idx if isinstance(idx, str) and idx in INDEXES else None
            mix = {}
            gen = row.get("generationmix")
            for m in gen[:20] if isinstance(gen, list) else []:
                fuel = m.get("fuel") if isinstance(m, dict) else None
                if isinstance(fuel, str) and fuel in FUELS:
                    try:
                        mix[fuel] = number(m.get("perc"), 0, 100)
                    except ValueError:
                        pass            # a bad share loses that fuel, not the half hour
            out[parse_time(row.get("from"))] = (g, idx, mix or None)
        except (ValueError, TypeError):
            continue                    # one bad row costs that half hour, not the forecast
    if not out:
        raise ValueError("no carbon intensity data for that place")
    return info, out


def parse_prices(doc, start=None, end=None):
    """Octopus standard-unit-rates response -> {half-hour start: pence per kWh including VAT}.

    Agile rows are half hours already. Other tariffs (Go and friends) come as long intervals,
    say 05:30-00:30; with a window [start, end) those are spread over the half hours they cover,
    and only inside the window, so a year-long rate can't blow up the result."""
    out = {}
    for row in _rows(doc, "results"):
        if row.get("payment_method") not in (None, "DIRECT_DEBIT"):
            continue
        try:
            t0 = parse_time(row.get("valid_from"))
            price = number(row.get("value_inc_vat"), -200, 500)
            t1 = parse_time(row["valid_to"]) if row.get("valid_to") is not None else None
        except (ValueError, KeyError):
            continue
        if start is None or end is None:
            out.setdefault(t0, price)
            continue
        t = max(floor_slot(t0), start)
        stop = min(t1, end) if t1 is not None else end
        while t < stop:
            out.setdefault(t, price)
            t += SLOT
    return out


def repeat_daily(prices, start, end):
    """Fill half hours with no price from the same time on an earlier day. Octopus only lists
    a fixed time-of-use tariff's rates up to today, but its daily pattern repeats."""
    out = dict(prices)
    t = start
    while t < end:
        if t not in out:
            for days in range(1, REPEAT_DAYS + 1):
                earlier = prices.get(t - timedelta(days=days))
                if earlier is not None:
                    out[t] = earlier
                    break
        t += SLOT
    return out


def pick_agile(doc):
    """The newest Agile import product in an Octopus product list."""
    codes = []
    for p in _rows(doc, "results"):
        code = p.get("code")
        if (isinstance(code, str) and PRODUCT_CODE.fullmatch(code) and code.startswith("AGILE-")
                and "OUTGOING" not in code
                and p.get("direction", "IMPORT") == "IMPORT" and not p.get("available_to")):
            codes.append(code)
    codes.sort(key=lambda c: c.split("-")[-3:] if re.search(r"[0-9]{2}-[0-9]{2}-[0-9]{2}$", c) else ["0"])
    return codes[-1] if codes else FALLBACK_AGILE


def build_slots(start, carbon, prices, n=WINDOW_SLOTS):
    slots = []
    for i in range(n):
        t = start + SLOT * i
        g, idx, mix = carbon.get(t, (None, None, None))
        slots.append(Slot(t, g, idx, mix, prices.get(t)))
    return slots


# ---------------------------------------------------------------- network and cache

def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "gridhour")


def offline():
    return os.environ.get("GRIDHOUR_OFFLINE", "") not in ("", "0")


def _cache_path(key):
    if not CACHE_KEY.fullmatch(key):
        raise ValueError("bad cache key")
    return os.path.join(cache_dir(), key + ".json")


def _read_cache(key):
    try:
        with open(_cache_path(key), encoding="utf-8") as f:
            box = json.loads(f.read(MAX_BYTES + 1))
        at = number(box["at"], 0, time.time() + 300)    # a timestamp from the future would never expire
        return at, box["doc"]
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return None, None


def _write_cache(key, doc):
    try:
        atomic_write(_cache_path(key), json.dumps({"at": time.time(), "doc": doc}))
    except (OSError, ValueError):
        pass


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Both APIs answer directly. A redirect could lead anywhere, plain http included."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


_OPENER = urllib.request.build_opener(_RefuseRedirects)
# A resolver cannot be cancelled; cap abandoned requests and never let them delay process exit.
_REQUEST_SLOTS = BoundedSemaphore(2)


def http_json(url, timeout=12):
    if not isinstance(url, str) or not url.startswith(ALLOWED):
        raise ValueError("refusing to fetch %r" % url)
    deadline = time.monotonic() + DEADLINE
    slots = _REQUEST_SLOTS
    if not slots.acquire(timeout=DEADLINE):
        raise TimeoutError("took longer than %s seconds" % DEADLINE)
    result = Future()

    def fetch():
        try:
            result.set_result(_http_json(url, timeout, deadline))
        except Exception as e:  # noqa: BLE001 -- forward worker failures to the calling thread
            result.set_exception(e)
        finally:
            slots.release()

    worker = Thread(target=fetch, daemon=True)
    try:
        worker.start()
    except RuntimeError:
        slots.release()
        raise
    try:
        return result.result(timeout=max(0, deadline - time.monotonic()))
    except TimeoutError:
        raise TimeoutError("took longer than %s seconds" % DEADLINE) from None


def _http_json(url, timeout, deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError("request deadline expired")
    # scheme and host are checked above and redirects are refused, so S310 cannot apply
    req = urllib.request.Request(url, headers={"User-Agent": "gridhour/" + __version__,  # noqa: S310
                                               "Accept": "application/json"})
    chunks, size = [], 0
    with _OPENER.open(req, timeout=timeout) as r:
        if not r.geturl().startswith(ALLOWED):
            raise ValueError("response came from somewhere else")
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError("took longer than %d seconds" % DEADLINE)
            chunk = r.read(64 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("response larger than %d bytes" % MAX_BYTES)
            chunks.append(chunk)
    return json.loads(b"".join(chunks).decode("utf-8"))


def _why(e):
    """A short reason for the status line that never echoes response content."""
    if isinstance(e, urllib.error.HTTPError):
        return "HTTP %d" % e.code
    if isinstance(e, urllib.error.URLError):
        return label(str(e.reason), 50) or "unreachable"
    if isinstance(e, (json.JSONDecodeError, UnicodeDecodeError, RecursionError)):
        return "unreadable response"
    if isinstance(e, (TimeoutError, OSError)):
        return label(str(e), 50) or type(e).__name__
    if isinstance(e, ValueError) and str(e).startswith(("response", "refusing", "took")):
        return label(str(e), 60)
    return type(e).__name__


FETCH_ERRORS = (urllib.error.URLError, OSError, ValueError, http.client.HTTPException, RecursionError,
                OverflowError)


def cached_json(key, url, parse, max_age=MAX_AGE, force=False, fetch=None, cache_only=False):
    """(fetched_at, parsed, error). A response is parsed before it is cached, so a broken one is
    never stored; a cache entry that no longer parses counts as missing. Falls back to a stale
    cache when the network fails."""
    at, doc = _read_cache(key)
    parsed = None
    if doc is not None:
        try:
            parsed = parse(doc)
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
            at, parsed = None, None
    if parsed is not None and not force and time.time() - at < max_age:
        return at, parsed, None
    if offline() or cache_only:
        return at, parsed, None if parsed is not None or cache_only else "offline and nothing cached yet"
    try:
        fresh = (fetch or http_json)(url)
        result = parse(fresh)
    except FETCH_ERRORS as e:
        return at, parsed, "network: %s" % _why(e)
    except (TypeError, KeyError, AttributeError):
        return at, parsed, "network: unreadable response"
    _write_cache(key, fresh)
    return time.time(), result, None


def carbon_url(start, postcode=None, region_id=None):
    if postcode:
        return "%s/regional/intensity/%s/fw48h/postcode/%s" % (CARBON_API, iso(start), postcode)
    return "%s/regional/intensity/%s/fw48h/regionid/%d" % (CARBON_API, iso(start), region_id or 18)


def prices_url(product, gsp, start, end):
    if not isinstance(product, str) or not PRODUCT_CODE.fullmatch(product) or gsp not in GSP_REGION:
        raise ValueError("refusing to build a price URL from %r and %r" % (product, gsp))
    tariff = "E-1R-%s-%s" % (product, gsp)
    return ("%s/products/%s/electricity-tariffs/%s/standard-unit-rates/?period_from=%s&period_to=%s&page_size=1500"
            % (OCTOPUS_API, product, tariff, iso(start), iso(end)))


def load(now, postcode=None, region_id=None, gsp=None, prices=True, force=False, fetch=None, tariff=None):
    """Fetch (or read from cache) everything for the 48 hour window around ``now``."""
    timed_out = False

    def refresh_fetch(url):
        nonlocal timed_out
        try:
            return (fetch or http_json)(url)
        except TimeoutError:
            timed_out = True
            raise
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                timed_out = True
            raise

    start = window_start(now)
    end = start + SLOT * WINDOW_SLOTS
    if postcode is not None:
        postcode = normalize_postcode(postcode)
    if region_id not in REGIONS:
        region_id = None
    fc = Forecast(postcode=postcode)
    key = "carbon-" + (postcode or "r%d" % (region_id or 18))
    at, parsed, err = cached_json(key, carbon_url(start, postcode, region_id), parse_carbon,
                                  force=force, fetch=refresh_fetch)
    carbon = {}
    fc.region_id = region_id or 18
    if parsed is not None:
        info, carbon = parsed
        fc.region_id = info["region_id"] or fc.region_id
        fc.fetched = at
        fc.region = info["region"] or REGIONS[fc.region_id][0]
    else:
        fc.region = REGIONS[fc.region_id][0]
    if err:
        fc.errors.append(err)
    price_map = {}
    fc.gsp = gsp if gsp in GSP_REGION else REGIONS[fc.region_id][1]
    if prices and fc.gsp:
        product = tariff if isinstance(tariff, str) and PRODUCT_CODE.fullmatch(tariff) else None
        if product is None:
            _, product, perr = cached_json("agile-product", AGILE_PRODUCTS_URL, pick_agile, max_age=86400,
                                           fetch=refresh_fetch, cache_only=timed_out)
            if perr and timed_out:
                fc.errors.append(perr)
            product = product or FALLBACK_AGILE
        fc.tariff = "E-1R-%s-%s" % (product, fc.gsp)
        fc.tariff_name = tariff_name(product)
        agile = product.startswith("AGILE-")
        key = "prices-" + fc.gsp if agile else "prices-%s-%s" % (product.lower(), fc.gsp)
        # Octopus lists a fixed tariff's rates only up to today, so ask from a couple of days back
        # to have whole earlier days to repeat forward
        since = start if agile else start - timedelta(days=2)
        rat, parsed, rerr = cached_json(key, prices_url(product, fc.gsp, since, end + SLOT * 48),
                                        lambda doc: parse_prices(doc, start - timedelta(days=REPEAT_DAYS),
                                                                 end + SLOT * 48),
                                        force=force, fetch=refresh_fetch, cache_only=timed_out)
        if parsed is not None:
            price_map = parsed if agile else repeat_daily(parsed, start, end)
            if rat and (not fc.fetched or rat < fc.fetched):
                fc.fetched = rat
        if rerr:
            fc.errors.append(rerr.replace("network", "prices", 1))
    elif not prices:
        fc.gsp = None
    fc.slots = build_slots(start, carbon, price_map)
    return fc
