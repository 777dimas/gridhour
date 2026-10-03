"""Render frames to PNG for the README. Needs Pillow and the DejaVu Sans Mono fonts.

    python3 tools/screenshots.py            # regenerate docs/*.png from the test fixtures
    python3 tools/screenshots.py --live     # the same from today's real data

Frames are drawn straight from the Canvas (characters plus colours), so there is no ANSI parsing.
Block characters are painted as rectangles so the bars line up without gaps.
"""
import argparse
import os
import sys
import tempfile
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from gridhour.compose import compose  # noqa: E402
from gridhour.grid import load  # noqa: E402
from gridhour.state import State  # noqa: E402
from gridhour.themes import C, apply_theme  # noqa: E402

FONT_DIRS = ["/usr/share/fonts/truetype", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/TTF",
             "/Library/Fonts", os.path.expanduser("~/Library/Fonts")]
CW, CH, SIZE = 9, 19, 15
LOWER = " ▁▂▃▄▅▆▇█"
ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURE_NOW = datetime(2026, 10, 3, 22, 46, tzinfo=UTC)


def font(bold=False):
    name = "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf"
    for d in FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return ImageFont.truetype(p, SIZE)
    sys.exit("DejaVu Sans Mono not found")


def render(cv, path, pad=10):
    img = Image.new("RGB", (cv.w * CW + pad * 2, cv.h * CH + pad * 2), C.BG)
    d = ImageDraw.Draw(img)
    regular, bold = font(), font(True)
    for y in range(cv.h):
        for x in range(cv.w):
            c = cv.cell(x, y)
            ch, fg, bg, b = c.char, c.fg, c.bg, c.bold
            fg = fg or C.TEXT
            px, py = pad + x * CW, pad + y * CH
            d.rectangle([px, py, px + CW - 1, py + CH - 1], fill=bg or C.BG)
            if ch in LOWER and ch != " ":
                h = round(CH * LOWER.index(ch) / 8)
                d.rectangle([px, py + CH - h, px + CW - 1, py + CH - 1], fill=fg)
            elif ch != " ":
                d.text((px, py + 1), ch, font=bold if b else regular, fill=fg)
    img.save(path)
    print("wrote", path)


def fixture_fetch(url):
    import json
    fx = os.path.join(ROOT, "tests", "fixtures")
    name = "carbon_sw1a.json" if "carbonintensity" in url else (
        "products.json" if url.rstrip("/").endswith("is_variable=true&page_size=100") else "agile_c.json")
    with open(os.path.join(fx, name), encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--only", help="render one shot by name")
    args = ap.parse_args()
    os.environ["XDG_CACHE_HOME"] = tempfile.mkdtemp()
    now = datetime.now(UTC).replace(microsecond=0) if args.live else FIXTURE_NOW
    st = State()
    st.persist = False
    st.postcode = "SW1A"
    st.fc = load(now, "SW1A", force=True, fetch=None if args.live else fixture_fetch)
    out = os.path.join(ROOT, "docs")
    os.makedirs(out, exist_ok=True)
    shots = {
        "main": dict(W=120, H=40),
        "compact": dict(W=72, H=16),
        "light": dict(W=120, H=40, theme="daylight"),
        "scrub": dict(W=120, H=40, frozen=2 * 3600 * 6),
    }
    for name, o in shots.items():
        if args.only and name != args.only:
            continue
        apply_theme(o.get("theme", "carbon"))
        st.frozen = now + timedelta(seconds=o["frozen"]) if o.get("frozen") else None
        st.frozen = st.frozen.replace(minute=0) if st.frozen else None
        render(compose(o["W"], o["H"], st, st.frozen or now, now), os.path.join(out, name + ".png"))


if __name__ == "__main__":
    main()
