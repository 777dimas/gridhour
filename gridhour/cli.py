"""Command line entry point."""
import argparse
import os
import re
import shutil
import sys

from . import __version__
from .app import run, utcnow
from .compose import MAX_H, MAX_W, compose
from .grid import cache_dir, load, normalize_postcode, parse_time, region_from_arg
from .output import json_output, line_output, watch
from .plan import MODES, parse_job
from .state import config_path, state_from_config
from .themes import THEME_ORDER, apply_theme


def parse_size(text):
    m = re.fullmatch(r"([0-9]{1,4})x([0-9]{1,4})", text.strip().lower())
    if not m:
        raise ValueError("--size looks like 120x40")
    W, H = int(m.group(1)), int(m.group(2))
    if not (40 <= W <= MAX_W and 8 <= H <= MAX_H):
        raise ValueError("--size must be between 40x8 and %dx%d" % (MAX_W, MAX_H))
    return W, H


def reset():
    """Delete the config and the cache (cache file names contain the postcode)."""
    gone = 0
    paths = [config_path()]
    try:
        paths += [os.path.join(cache_dir(), n) for n in os.listdir(cache_dir())
                  if n.endswith(".json") and (n.startswith(("carbon-", "prices-", "agile-", ".tmp-")))]
    except OSError:
        pass
    for p in paths:
        try:
            os.remove(p)
            gone += 1
        except FileNotFoundError:
            pass
        except OSError as e:
            print("gridhour: could not remove %s: %s" % (p, e.strerror), file=sys.stderr)
    print("gridhour: saved settings and cache removed" if gone else "gridhour: nothing to reset")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gridhour",
                                 description="When British electricity is green and cheap: a 48 hour carbon and "
                                             "Agile price timeline for the terminal.")
    ap.add_argument("postcode", nargs="*", help="your postcode, full or the first half (remembered)")
    ap.add_argument("--region", help="a region instead of a postcode: 1-18, an Agile letter A-P, or a name")
    ap.add_argument("--no-prices", action="store_true", help="carbon only, skip Octopus Agile prices")
    ap.add_argument("--mode", choices=MODES, help="rank windows by carbon, price or both")
    ap.add_argument("--at", help="freeze the clock at this time (ISO 8601, UTC unless it has an offset)")
    ap.add_argument("--line", action="store_true", help="print one line for a status bar and exit")
    ap.add_argument("--best", metavar="DURATION", help="with --line/--watch: the best start for a job this long")
    ap.add_argument("--tmux", action="store_true", help="like --line with tmux colour codes")
    ap.add_argument("--watch", action="store_true", help="the one-liner, updating in place")
    ap.add_argument("--json", action="store_true", help="print JSON and exit")
    ap.add_argument("--once", action="store_true", help="print one frame of the full UI and exit")
    ap.add_argument("--size", help="WxH for --once (default: terminal size)")
    ap.add_argument("--theme", choices=THEME_ORDER, help="colour theme")
    ap.add_argument("--12h", dest="h12", action="store_true", help="12-hour clock")
    ap.add_argument("--compact", action="store_true", help="small-pane layout without the chart")
    ap.add_argument("--reset", action="store_true", help="forget saved settings and jobs")
    ap.add_argument("--version", action="version", version="gridhour " + __version__)
    args = ap.parse_args(argv)
    if args.reset:
        reset()
        return
    st = state_from_config()
    try:
        if args.postcode:
            st.postcode = normalize_postcode(" ".join(args.postcode))
            st.region_id = None
            st.save()
        if args.region:
            st.region_id = region_from_arg(args.region)
            st.postcode = None
            st.persist = False
        best = parse_job("job " + args.best) if args.best else None
        at = parse_time(args.at) if args.at else None
        if at and not 2000 <= at.year <= 2100:
            raise ValueError("--at must be between the years 2000 and 2100")
        size = parse_size(args.size) if args.size else None
    except ValueError as e:
        sys.exit("gridhour: %s" % e)
    if args.no_prices:
        st.prices = False
    if args.mode:
        st.mode = args.mode
    if args.theme:
        apply_theme(args.theme)
    if args.h12:
        st.h12 = True
    if args.compact:
        st.compact = "on"
    if args.watch:
        watch(st, utcnow, "ansi" if sys.stdout.isatty() else "plain", best)
        return
    if args.line or args.tmux or args.json or args.once:
        now = at or utcnow().replace(microsecond=0)
        st.fc = load(now, st.postcode, st.region_id, st.gsp, st.prices)
        if args.json:
            print(json_output(st, now))
        elif args.once:
            W, H = size or shutil.get_terminal_size((120, 40))
            print("\n".join(compose(W, H, st, now, now).lines()))
        else:
            color = "tmux" if args.tmux else ("ansi" if sys.stdout.isatty() else "plain")
            print(line_output(st, now, color, best))
        return
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.exit("gridhour: needs an interactive terminal (use --once, --line or --json otherwise)")
    if at:
        st.frozen = at
    try:
        run(st)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
