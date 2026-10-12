# gridhour

[![PyPI](https://img.shields.io/pypi/v/gridhour)](https://pypi.org/project/gridhour/)
[![Python](https://img.shields.io/pypi/pyversions/gridhour)](https://pypi.org/project/gridhour/)
[![CI](https://github.com/777dimas/gridhour/actions/workflows/ci.yml/badge.svg)](https://github.com/777dimas/gridhour/actions/workflows/ci.yml)
[![CodeQL](https://github.com/777dimas/gridhour/actions/workflows/codeql.yml/badge.svg)](https://github.com/777dimas/gridhour/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/777dimas/gridhour/badge)](https://scorecard.dev/viewer/?uri=github.com/777dimas/gridhour)

When is British electricity green and cheap? gridhour shows the next 48 hours of carbon
intensity for your postcode and Octopus Agile prices on one timeline in the terminal, then
picks the best time to start the washing, charge the car or kick off a batch job.

```console
$ gridhour --line
⚡ 142g · 14p · green in 2h
```

![gridhour demo: scrubbing the 48 hour timeline, jumping to the best window, switching ranking and themes](https://raw.githubusercontent.com/777dimas/gridhour/main/docs/demo.gif)

## What you see

![gridhour main view](https://raw.githubusercontent.com/777dimas/gridhour/main/docs/main.png)

* **The chart.** Carbon intensity (gCO₂/kWh) rises above the time axis, the Agile unit price
  hangs below it. Green is clean or cheap, red is dirty or dear, blue is a plunge price where
  Octopus pays you to use power. The hours already gone are dimmed.
* **Generation mix.** Wind, solar, gas, nuclear and the rest, as shares of your region's
  supply, on the same time axis. Handy for seeing *why* tomorrow afternoon is clean.
* **Best time to run.** One row per job. Each row is shaded by how good every start time is,
  and the bright block is the best window, with its average carbon and price next to it. The
  status line tells you how much that saves against starting right now.
* **A cursor** runs straight down through all of it. Move it with the arrow keys to read any
  half hour; `Enter` jumps to the selected job's best window.

Jobs are ranked by carbon, by price, or by both (each normalised over the 48 hours and
averaged). `w` switches between them.

### Deadlines and jobs that can run in pieces

A washing machine runs in one go and rarely has to finish by a set time. A car has to be charged
before you leave, and it doesn't care whether it charges in one block. A job can say both:

```
Washing      2h
EV charge    4h by 07:00 split
Battery      3h by 16:00 split
```

* **`by 07:00`** means the window has to finish by the next 07:00, UK time. If it is already
  past 07:00, that means tomorrow's. An amber `┤` marks the deadline on the job's row. If there
  isn't enough forecast before it, gridhour says so rather than suggesting a time after it.
* **`split`** lets gridhour pick the best half hours before the deadline in any order, so a dear
  half hour sitting between two cheap ones gets skipped. It only splits when the pieces really
  are better than one continuous block.

Type them in the add box (`a`), or select a job and press `b` for the deadline and `s` to
allow pieces.

| Scrubbed to tomorrow morning | Compact layout for a tmux split |
| --- | --- |
| ![scrubbing](https://raw.githubusercontent.com/777dimas/gridhour/main/docs/scrub.png) | ![compact](https://raw.githubusercontent.com/777dimas/gridhour/main/docs/compact.png) |

## Install

You need Python 3.11 or newer, a terminal with truecolor and a UTF-8 locale. Linux and macOS;
on Windows use WSL.

The simplest way is [pipx](https://pipx.pypa.io/), which installs the `gridhour` command for your
user in its own environment:

```sh
pipx install gridhour                                        # from PyPI
pipx install git+https://github.com/777dimas/gridhour        # or straight from GitHub
gridhour SW1A 1AA
```

Either line is enough. The second one is there for when PyPI is unreachable; it builds the latest
code on `main`, which can be ahead of the release.

No pipx yet? Get it from your system's package manager:

| System | Install pipx |
| --- | --- |
| Debian, Ubuntu | `sudo apt install pipx` |
| Fedora | `sudo dnf install pipx` |
| Rocky Linux, AlmaLinux | `sudo dnf install epel-release && sudo dnf install pipx` |
| RHEL | [enable EPEL](https://docs.fedoraproject.org/en-US/epel/getting-started/), then `sudo dnf install pipx` |
| openSUSE Tumbleweed | `sudo zypper install python313-pipx` |
| macOS | `brew install pipx` |

If your shell cannot find `gridhour` afterwards, run `pipx ensurepath` once and open a new
terminal.

**gridhour needs Python 3.11 or newer.** Some long-term-support systems ship an older default:
RHEL, Rocky and AlmaLinux 9 come with 3.9 (version 10 is fine), and openSUSE Leap 15 with 3.6.
There, install a newer Python next to the system one (`sudo dnf install python3.11` on the EL 9
family, `sudo zypper install python311` on Leap 15) and point pipx at it:

```sh
pipx install --python python3.11 gridhour
```

To try it without installing: `pipx run gridhour SW1A` or `uvx gridhour SW1A`.

The postcode you give is remembered, so after the first run plain `gridhour` is enough. Only
the first half (`SW1A`) is ever used or sent anywhere. Northern Ireland is not on the GB grid,
so BT postcodes have no forecast.

### Updating and removing

```sh
pipx upgrade gridhour
gridhour --reset && pipx uninstall gridhour    # --reset first deletes the saved settings and cache
```

`gridhour --version` shows what you have.

### Other ways

* **pip**, in a virtual environment: `pip install gridhour`.
* **From a clone**, nothing to build: `python3 -m gridhour SW1A`.
* **A specific release from GitHub**: `pipx install git+https://github.com/777dimas/gridhour@v0.4.0`.

Every release on PyPI carries signed build provenance; [SECURITY.md](https://github.com/777dimas/gridhour/blob/main/SECURITY.md#supply-chain)
shows how to check a file against it.

### Not on Octopus yet?

**Ad · referral link.** If you switch your home to Octopus Energy with
[my referral link](https://share.octopus.energy/cheeky-melon-215), we each get £50 account
credit (as of October 2026). gridhour works exactly the same whether you use it or not, and it
isn't affiliated with Octopus.

## Usage

```sh
gridhour                           # your saved postcode
gridhour M1 1AE                    # a new postcode (saved)
gridhour --region scotland         # a region instead, for this run only
gridhour --mode green              # rank by carbon only (also: cheap, both)
gridhour --tariff "Octopus Go 12M Fixed August 2025 v1"   # your own tariff, as the app names it
gridhour --no-prices               # carbon only, for any tariff
gridhour --at 2026-10-04T18:00Z    # start with the cursor at a given time
gridhour --theme slate --12h
gridhour --reset                   # delete the saved postcode, jobs, settings and the cache
```

Keys inside the app (`?` lists them all):

| Key | Action |
| --- | --- |
| `←` `→` | move the cursor 30 minutes, Shift or `H` `L` for 2 hours |
| `Home` `End` `r` | start and end of the forecast, back to now |
| `↑` `↓` | select a job |
| `+` `-` | make the selected job 30 minutes longer or shorter |
| `a` `d` | add a job (`Dryer 1h30`, `EV 4h by 07:00 split`), delete the selected one |
| `b` `s` | selected job: finish by a time, allow it to run in pieces |
| `Enter` | jump to the selected job's best window |
| `w` | rank by carbon, price, or both |
| `p` | change postcode |
| `o` | change tariff: its name from the Octopus app, a code, or `agile` |
| `m` `c` `T` `t` | mix rows, compact layout, theme, 12/24h |
| `R` | refetch now |
| `q` | quit |

Settings and jobs live in `~/.config/gridhour/config.json`.

## Status bars and scripts

```console
$ gridhour --line
⚡ 142g · 14p · green in 2h

$ gridhour --line --best 3h
⚡ 142g · 14p · 3h best 13:00 (in 4h30)

$ gridhour --tmux                  # same, with tmux colour codes for status-right
$ gridhour --watch                 # same, updating in place
$ gridhour --json | jq '.jobs[] | {name, start: .best.from}'
```

"Green" means NESO's forecast grades the half hour as *low* or *very low* for your region.
If nothing in the next 48 hours makes that grade, the line says `greenest in 9h` instead.

`--json` gives the current half hour, the next green slot, the best window for every job (its
deadline and the pieces it runs in included, with
the carbon and price you would get starting now, for comparison) and the full 48 hour series.

### Ad-hoc windows in scripts

`gridhour --json --best 2h` adds a top-level `best` window for a two-hour job without
editing saved jobs. For example, `gridhour --json --best 2h | jq '.best'` prints its
UTC `from` and `to`, `starts_in_minutes`, mean `carbon` (gCO₂/kWh), mean `price`
(p/kWh including VAT), and continuous `parts`. Missing carbon or price is `null`;
`best` itself is `null` if no complete window is available. Without `--best`, this
extra key is absent. The selected mode ranks the window, just as for saved jobs.

Export the best job windows to an iCalendar file:

```sh
gridhour --ical > jobs.ics
```

Import `jobs.ics` into your calendar app. Each continuous part of a job's best
window becomes a separate event. Events include the best window's average carbon
intensity and price, with UTC timestamps and stable UIDs for repeat imports.

## Status bar recipes

Waybar, Polybar and i3blocks refresh this module every five minutes (300 seconds).
Tmux uses its normal status interval. Forecast slots are half-hourly; cached runs
do not fetch new data on every refresh. Run gridhour interactively once to
save your postcode and tariff, then check `gridhour --line` in a terminal. The bar must be
able to find `gridhour` on its PATH; otherwise replace it with the absolute path printed by
`command -v gridhour`. Use `--line` for plain text and `--tmux` only inside tmux.
The ⚡ symbol needs an emoji-capable font in your bar.

### tmux

Add to `~/.tmux.conf`, then reload it with `tmux source-file ~/.tmux.conf`:

```tmux
set -g status-right '#(gridhour --tmux) '
```

This replaces the right-hand status text. Tmux reruns the command at its normal
status interval, leaving the refresh rate of clocks and other status items alone.

### Waybar

Merge this module into `~/.config/waybar/config` (or `config.jsonc`) and add
`"custom/gridhour"` to the existing `modules-right` array. Restart Waybar to apply it.

```json
"custom/gridhour": {
  "exec": "gridhour --line",
  "interval": 300,
  "format": "{}",
  "escape": true,
  "tooltip": false
}
```

The command emits plain text, so do not set `return-type` to `json`.
See [Waybar's custom module documentation](https://github.com/Alexays/Waybar/wiki/Module:-Custom).

### Polybar

Add this to `~/.config/polybar/config.ini` and append `gridhour` to your bar's
existing `modules-right` list, then restart Polybar:

```ini
[module/gridhour]
type = custom/script
exec = gridhour --line
interval = 300
tail = false
label = %output%
```

`tail = false` runs the command once per interval rather than expecting a continuous stream.
See [Polybar's script module documentation](https://github.com/polybar/polybar/wiki/Module:-script).

### i3blocks

Append to the i3blocks configuration selected by your i3 or Sway `status_command`
(commonly `~/.config/i3blocks/config`), then restart i3blocks:

```ini
[gridhour]
command=gridhour --line
interval=300
```

The first output line becomes the block text. This recipe uses i3blocks, not i3status.
See [i3blocks' command and interval documentation](https://github.com/vivien/i3blocks#configuration).

## Where the numbers come from

* **Carbon intensity** and the **generation mix**: the [Carbon Intensity API](https://carbonintensity.org.uk/)
  from the National Energy System Operator (NESO), regional forecast by postcode. Free, no key,
  CC BY 4.0.
* **Prices**: the public [Octopus Energy API](https://developer.octopus.energy/), the Agile
  import tariff for your region, including VAT. Octopus publishes the next day's prices at about
  4pm, so before that the price half of the chart stops around 11pm tonight and the "cheap"
  ranking only looks that far ahead.

### On Octopus Go or another tariff

Fixed and time-of-use tariffs keep the rates of the version you signed up to, so tell gridhour
which one you're on. Use the name exactly as the Octopus app shows it on your tariff screen:

```sh
gridhour --tariff "Octopus Go 12M Fixed August 2025 v1"
gridhour --tariff agile                                   # back to Agile
```

In the app itself, press `o` and type the same name. gridhour looks that name up once, finds
Octopus's code for it (here `GO-FIX-12M-25-08-29`) and
remembers it. If you already know the code you can pass it instead. That includes the long form
`E-1R-GO-FIX-12M-25-08-29-E`, whose last letter is your region.

gridhour then reads that version's rates from the same public API. Octopus lists them only up
to today, so later days repeat the same daily pattern, which is how these tariffs work.

On Go, price alone doesn't tell you much: it's cheap from 00:30 to 05:30 and the same price the
rest of the day. What gridhour adds is carbon. It picks the cleaner night for the washing, and
the cleaner hours when you have to run something in the day. Intelligent Go's extra charging
slots are set per account by Octopus and aren't public, so gridhour only knows the standard
Go hours for that tariff.

These are forecasts. The carbon forecast for tomorrow afternoon can be off by a fair
margin; Agile prices, once published, are what you pay. gridhour is not affiliated with Octopus
Energy or NESO.

Responses are cached in `~/.cache/gridhour` for 30 minutes. If the network is down the app
keeps showing the cached data and says how old it is. `GRIDHOUR_OFFLINE=1` stops all network
access.

## Security and privacy

gridhour talks to those two APIs over HTTPS and nothing else (redirects are refused), sends only
the first half of your postcode and your region letter, and has no runtime dependencies.
Responses are checked field by field before they are used or cached, and text from them never
reaches your terminal or tmux with escape sequences or format codes in it. Details and how to
report a problem: [SECURITY.md](https://github.com/777dimas/gridhour/blob/main/SECURITY.md).

## Development

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r requirements/dev.txt && pip install --no-deps -e .
pytest
```

**How it's made.** Most of gridhour's code was written with an AI assistant (Claude), directed
by me. Every change, mine or a contributor's, goes through a pull request with the full test suite,
`ruff`, CodeQL and a security-focused test file (`tests/test_security.py`), and releases are built
and signed in CI.

The tests replay real API responses from `tests/fixtures/`; sockets are blocked while they run.
More in [CONTRIBUTING.md](https://github.com/777dimas/gridhour/blob/main/CONTRIBUTING.md).

| Module | What it does |
| --- | --- |
| `grid.py` | the two APIs, regions and postcodes, the cache |
| `plan.py` | scoring half hours, best windows, "green in 2h" |
| `compose.py` | turns the state into a frame |
| `canvas.py` | character grid with colours, rendered to ANSI |
| `safe.py` | cleaning outside text, private atomic file writes |
| `app.py`, `keys.py` | the terminal loop and every key |
| `output.py` | `--line`, `--tmux`, `--json`, `--ical`, `--watch` |
| `state.py`, `themes.py`, `cli.py` | settings, colours, arguments |

## Licence

MIT, see [LICENSE](https://github.com/777dimas/gridhour/blob/main/LICENSE).
