"""Colour themes.

Every drawing function reads colours through ``C`` (the active theme), so switching theme at
runtime is one call to :func:`apply_theme`. The carbon and price scales are built from the
theme's own GREEN, AMBER and RED, so every theme gets a scale that fits it.
"""


class _Theme:
    """Attribute bag holding the colours of the active theme."""

    name = "carbon"


_BASE = dict(
    # carbon: warm graphite with a lime accent
    BG=(20, 21, 19), BAR_BG=(36, 38, 34), SEL_BG=(44, 47, 40), TOP_BG=(28, 30, 26), PANEL_BG=(30, 32, 28),
    BORDER=(64, 68, 58), DIM=(140, 142, 128), TEXT=(222, 220, 206), WHITE=(250, 248, 236),
    ACCENT=(196, 232, 92), INK=(20, 21, 19),
    CLEAN=(64, 196, 120), GREEN=(150, 214, 96), AMBER=(240, 196, 80), ORANGE=(236, 132, 64), RED=(226, 74, 74),
    PLUNGE=(96, 176, 240), SUN=(246, 204, 84), WIND=(120, 200, 230), GAS=(232, 126, 72), NUCLEAR=(186, 140, 232),
    BIOMASS=(176, 150, 96), IMPORTS=(150, 150, 140), HYDRO=(84, 140, 220), COAL=(130, 116, 110),
    FRAME=(110, 116, 98), KEY=(196, 232, 92), CYAN=(120, 200, 230),
)


THEMES = {
    "carbon": dict(_BASE),
    # warm paper, ink-dark text
    "daylight": dict(_BASE, BG=(246, 243, 234), BAR_BG=(228, 224, 210), SEL_BG=(234, 238, 214), TOP_BG=(236, 232, 220),
                     PANEL_BG=(252, 250, 244), BORDER=(196, 190, 172), DIM=(116, 112, 98), TEXT=(44, 42, 36),
                     WHITE=(14, 14, 10), ACCENT=(88, 132, 20), INK=(250, 248, 240), CLEAN=(20, 128, 70),
                     GREEN=(76, 150, 30), AMBER=(196, 140, 0), ORANGE=(206, 96, 20), RED=(192, 40, 40),
                     PLUNGE=(20, 104, 196), SUN=(190, 136, 0), WIND=(10, 120, 170), GAS=(200, 90, 30),
                     NUCLEAR=(120, 70, 190), BIOMASS=(130, 100, 40), IMPORTS=(110, 108, 100), HYDRO=(30, 80, 190),
                     COAL=(90, 80, 76), FRAME=(150, 144, 124), KEY=(88, 132, 20), CYAN=(10, 120, 170)),
    # cool blue-grey with a teal accent
    "slate": dict(_BASE, BG=(30, 34, 40), BAR_BG=(44, 50, 58), SEL_BG=(52, 60, 70), TOP_BG=(38, 43, 50),
                  PANEL_BG=(40, 45, 52), BORDER=(80, 90, 102), DIM=(146, 156, 168), TEXT=(220, 226, 232),
                  WHITE=(248, 250, 252), ACCENT=(64, 210, 190), INK=(30, 34, 40), KEY=(64, 210, 190),
                  FRAME=(110, 124, 140)),
    # dark brown with an amber accent
    "ember": dict(_BASE, BG=(26, 19, 16), BAR_BG=(44, 33, 28), SEL_BG=(56, 41, 33), TOP_BG=(36, 26, 22),
                  PANEL_BG=(38, 28, 23), BORDER=(86, 66, 54), DIM=(170, 146, 124), TEXT=(236, 222, 204),
                  WHITE=(255, 246, 232), ACCENT=(255, 170, 60), INK=(26, 19, 16), KEY=(255, 170, 60),
                  FRAME=(140, 108, 86)),
    "mono": dict(_BASE, BG=(0, 0, 0), BAR_BG=(30, 30, 30), SEL_BG=(52, 52, 52), TOP_BG=(18, 18, 18),
                 PANEL_BG=(14, 14, 14), BORDER=(110, 110, 110), DIM=(160, 160, 160), TEXT=(232, 232, 232),
                 WHITE=(255, 255, 255), ACCENT=(255, 255, 255), INK=(0, 0, 0), KEY=(255, 255, 255),
                 FRAME=(180, 180, 180)),
    # blue to orange, readable with the common forms of colour blindness
    "colorblind": dict(_BASE, CLEAN=(0, 114, 178), GREEN=(86, 180, 233), AMBER=(240, 228, 66),
                       ORANGE=(230, 159, 0), RED=(213, 94, 0), PLUNGE=(204, 121, 167), WIND=(86, 180, 233),
                       GAS=(213, 94, 0), SUN=(240, 228, 66), ACCENT=(86, 180, 233), KEY=(86, 180, 233)),
}


THEME_ORDER = ["carbon", "daylight", "slate", "ember", "mono", "colorblind"]
DEFAULT_THEME = "carbon"
C = _Theme()


def apply_theme(name):
    """Make ``name`` the active theme (unknown names fall back to midnight)."""
    if not isinstance(name, str) or name not in THEMES:
        name = "carbon"
    C.name = name
    for key, value in THEMES[name].items():
        setattr(C, key, value)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _scale(value, stops):
    if value <= stops[0][0]:
        return stops[0][1]
    for (v0, c0), (v1, c1) in zip(stops, stops[1:], strict=False):
        if value <= v1:
            return mix(c0, c1, (value - v0) / (v1 - v0))
    return stops[-1][1]


def carbon_color(g):
    """Colour for a carbon intensity in gCO2/kWh."""
    return _scale(g, [(30, C.CLEAN), (100, C.GREEN), (170, C.AMBER), (240, C.ORANGE), (320, C.RED)])


def price_color(p):
    """Colour for a unit price in pence per kWh. Anything at or below zero gets the plunge colour."""
    if p <= 0:
        return C.PLUNGE
    return _scale(p, [(4, C.CLEAN), (12, C.GREEN), (20, C.AMBER), (28, C.ORANGE), (36, C.RED)])


def score_color(s):
    """Colour for a 0 (best) to 1 (worst) score."""
    return _scale(s, [(0.0, C.CLEAN), (0.3, C.GREEN), (0.55, C.AMBER), (0.8, C.ORANGE), (1.0, C.RED)])


FUEL_COLOR = {"wind": "WIND", "solar": "SUN", "gas": "GAS", "nuclear": "NUCLEAR", "biomass": "BIOMASS",
              "imports": "IMPORTS", "hydro": "HYDRO", "coal": "COAL", "other": "DIM"}


def fuel_color(fuel):
    return getattr(C, FUEL_COLOR.get(fuel, "DIM"))


apply_theme(DEFAULT_THEME)
