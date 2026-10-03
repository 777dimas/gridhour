import pytest
from conftest import NOW

from gridhour.compose import compose
from gridhour.themes import THEME_ORDER, apply_theme


def text(st, W=120, H=40, now=NOW):
    return "\n".join(compose(W, H, st, now, NOW).text())


def test_full_layout(st):
    t = text(st)
    lines = t.splitlines()
    assert "ϟ gridhour" in lines[0] and "London  SW1A  Agile C" in lines[0]
    assert "23:46 BST" in lines[0] and "→" not in lines[0]       # live: no scrub offset
    assert "gCO₂/kWh" in t and "p/kWh" in t
    assert "Sun" in t and "Mon" in t                # day names on the time axis
    assert "GENERATION MIX" in t and "Gas" in t and "Wind" in t
    assert "BEST TIME TO RUN · GREEN + CHEAP" in t
    assert "12:00–14:00 · 104g · 6.3p" in t          # the washing window label in its strip
    assert "start Sun 12:00, in 12h" in t and "Washing 2h" in t.splitlines()[-2]
    assert "prices arrive at about 4pm" in t


def test_every_line_is_exactly_the_width(st):
    for W, H in ((120, 40), (100, 30), (72, 16), (44, 10)):
        lines = compose(W, H, st, NOW, NOW).text()
        assert len(lines) == H and all(len(ln) == W for ln in lines)


def test_compact_layout(st):
    t = text(st, 72, 16)
    assert "Carbon" in t and "Price" in t and "gCO₂/kWh" not in t
    assert "Washing" in t


def test_title_drops_pieces_instead_of_cutting_words(st):
    first = text(st, 72, 16).splitlines()[0]
    assert "Agi " not in first and not first.rstrip().endswith("Agi")


def test_scrubbed_badge_and_info(st):
    st.frozen = NOW.replace(hour=10, minute=0).replace(day=4)
    t = text(st, now=st.frozen)
    assert "+11h30 → 11:00 BST" in t.splitlines()[0]
    assert "Sun 11:00–11:30 BST" in t


def test_mix_toggle(st):
    st.mix = False
    assert "GENERATION MIX" not in text(st)


def test_no_prices_says_so(st):
    st.mode = "cheap"
    for s in st.fc.slots:
        s.price = None
    t = text(st)
    assert "no prices, so carbon only" in t and "p/kWh" not in t


def test_loading_screen(st):
    st.fc.slots = []
    st.loading = True
    assert "fetching the forecast" in text(st)


def test_error_screen(st):
    st.fc.slots = []
    st.fc.errors = ["network: down"]
    assert "network: down" in text(st)


@pytest.mark.parametrize("theme", THEME_ORDER)
def test_every_theme_renders(st, theme):
    apply_theme(theme)
    assert compose(120, 40, st, NOW, NOW).lines()


def test_help_overlay(st):
    st.prompt = "help"
    assert "move the cursor 30 minutes" in text(st)


def test_twelve_hour_clock(st):
    st.h12 = True
    t = text(st)
    assert "11:46pm BST" in t and "12:00pm–2:00pm" in t
