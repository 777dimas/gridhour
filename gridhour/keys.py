"""Every key press ends up here. Returns "quit", "fetch" (reload, cache allowed), "refetch" or None."""
from . import plan
from .grid import SLOT, floor_slot, normalize_postcode
from .themes import THEME_ORDER, C, apply_theme

LEFT, RIGHT, UP, DOWN = "\x1b[D", "\x1b[C", "\x1b[A", "\x1b[B"
S_LEFT, S_RIGHT = "\x1b[1;2D", "\x1b[1;2C"
HOME, END = ("\x1b[H", "\x1b[1~", "\x1bOH"), ("\x1b[F", "\x1b[4~", "\x1bOF")


def _scrub(st, live, delta=None, to=None):
    slots = st.fc.slots
    if not slots:
        return
    base = st.frozen or floor_slot(live)
    t = to if to is not None else base + delta
    t = max(slots[0].start, min(slots[-1].start, floor_slot(t)))
    st.frozen = t


def handle_key(st, k, live):
    if st.prompt in ("job", "postcode"):
        return _prompt_key(st, k)
    if st.prompt == "help":
        st.prompt = None
        return "quit" if k == "q" else None
    if k in ("q", "Q", "\x03"):
        return "quit"
    if k == "\x1b":
        st.frozen = None
    elif k in (LEFT, "h"):
        _scrub(st, live, -SLOT)
    elif k in (RIGHT, "l"):
        _scrub(st, live, SLOT)
    elif k in (S_LEFT, "H"):
        _scrub(st, live, -SLOT * 4)
    elif k in (S_RIGHT, "L"):
        _scrub(st, live, SLOT * 4)
    elif k in HOME:
        _scrub(st, live, to=st.fc.slots[0].start if st.fc.slots else None)
    elif k in END:
        _scrub(st, live, to=st.fc.slots[-1].start if st.fc.slots else None)
    elif k == "r":
        st.frozen = None
    elif k in (UP, "k"):
        st.sel = max(0, st.sel - 1)
    elif k in (DOWN, "j"):
        st.sel = min(len(st.jobs) - 1, st.sel + 1)
    elif k in ("+", "="):
        _resize_job(st, 30)
    elif k in ("-", "_"):
        _resize_job(st, -30)
    elif k in ("\r", "\n"):
        sc = plan.scores(st.fc.slots, st.mode)
        w = plan.best_window(st.fc.slots, sc, st.job, live) if st.job else None
        if w:
            st.frozen = w.start
    elif k == "a":
        st.prompt, st.buf, st.err = "job", "", ""
    elif k == "d":
        if len(st.jobs) > 1:
            gone = st.jobs.pop(st.sel)
            st.sel = min(st.sel, len(st.jobs) - 1)
            st.say("removed " + gone.name, C.DIM)
            st.save()
        else:
            st.say("keep at least one job", C.AMBER)
    elif k == "w":
        st.mode = plan.MODES[(plan.MODES.index(st.mode) + 1) % len(plan.MODES)]
        eff = plan.effective_mode(st.fc.slots, st.mode)
        st.say("ranking windows by " + {"green": "carbon", "cheap": "price", "both": "carbon and price"}[eff]
               + ("" if eff == st.mode else " (no prices for this region)"), C.TEXT)
        st.save()
    elif k == "p":
        st.prompt, st.buf, st.err = "postcode", st.postcode or "", ""
    elif k == "m":
        st.mix = not st.mix
        st.save()
    elif k == "R":
        return "refetch"
    elif k == "T":
        apply_theme(THEME_ORDER[(THEME_ORDER.index(C.name) + 1) % len(THEME_ORDER)])
        st.say("theme: " + C.name, C.TEXT)
        st.save()
    elif k == "t":
        st.h12 = not st.h12
        st.save()
    elif k == "c":
        st.compact = {"auto": "on", "on": "off", "off": "auto"}[st.compact]
        st.say("layout: " + {"auto": "automatic", "on": "compact", "off": "full"}[st.compact], C.TEXT)
        st.save()
    elif k == "?":
        st.prompt = "help"
    return None


def _resize_job(st, delta):
    job = st.job
    if not job:
        return
    job.minutes = max(30, min(24 * 60, job.minutes + delta))
    st.save()


def _prompt_key(st, k):
    if k == "\x1b":
        st.prompt, st.err = None, ""
    elif k in ("\x7f", "\x08"):
        st.buf, st.err = st.buf[:-1], ""
    elif k in ("\r", "\n"):
        return _submit(st)
    elif len(k) == 1 and k.isprintable() and len(st.buf) < 40:
        st.buf += k
        st.err = ""
    return None


def _submit(st):
    if st.prompt == "job":
        try:
            job = plan.parse_job(st.buf)
        except ValueError as e:
            st.err = str(e)
            return None
        st.jobs.append(job)
        st.sel = len(st.jobs) - 1
        st.prompt = None
        st.save()
        st.say("added %s, %s" % (job.name, plan.fmt_duration(job.minutes)), C.GREEN)
        return None
    text = st.buf.strip()
    if not text:
        st.postcode, st.region_id = None, None
    else:
        try:
            st.postcode = normalize_postcode(text)
        except ValueError as e:
            st.err = str(e)
            return None
    st.prompt = None
    st.frozen = None
    st.save()
    return "refetch"
