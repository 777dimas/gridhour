# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [semantic versioning](https://semver.org/).

## [Unreleased]

### Added

* Status bar recipes for tmux, Waybar, Polybar and i3blocks, refreshing every five minutes.

### Fixed

* `--json --best DURATION` now includes the requested best window without changing saved jobs.

## [0.4.0] - 2026-10-06

### Added

* `--tariff` for Octopus tariffs other than Agile, such as Go and Go 12M Fixed. Give it the name
  the Octopus app shows (`"Octopus Go 12M Fixed August 2025 v1"`) and gridhour looks up the code
  once; a code like `GO-FIX-12M-25-08-29` works too. The title bar shows the tariff, and jobs
  land in the cheap hours; when the price is the same, carbon decides. `--tariff agile` goes back.
  It's remembered like the postcode.
* `o` in the app switches the tariff: type the name from the Octopus app, a code, or `agile`.
  Names are looked up in the background, so the screen doesn't freeze.
* README: a note on how gridhour is made: largely with an AI assistant, with every change going
  through tests, lint and CodeQL.

### Fixed

* A refresh stops its remaining network requests after the first timeout,
  retaining cached carbon and prices with one error rather than repeated deadlines.
  Thanks @nawaaaaaAaar (#22).

## [0.3.0] - 2026-10-05

### Added

* `--ical` exports the best job windows as an iCalendar document, with one event
  per continuous part, UTC timestamps and stable UIDs. Thanks @zhangbo-yc (#17).

### Changed

* The deadline box (`b`) also takes `by 07:00`. If you type a whole job there, it now says to
  press Esc and then `a`, instead of only "deadlines look like 07:00".
* Adding a job like `EV by 07:00 split` without a duration now asks how long it runs and shows
  the corrected line (`EV 4h by 07:00 split`).
* README: how to get pipx on Fedora, the RHEL family and openSUSE, and what to do where the
  system Python is older than 3.11. It also gains a referral link for Octopus, labelled as an ad.

### Fixed

* Network requests now return within the overall deadline even when DNS resolution stalls,
  allowing status lines to fall back to cached forecasts. Outstanding requests are capped.
  Thanks @jnohclee-rgb (#12).

## [0.2.0] - 2026-10-04

### Added

* Jobs can have a deadline and may run in pieces: `EV charge 4h by 07:00 split` picks the best
  half hours before 07:00, in any order. Add them in the add box, or press `b` (deadline) and
  `s` (pieces) on a selected job. The default EV charge job now uses `by 07:00 split`.
* `--json` gives each job's `deadline`, `deadline_at`, `split` and the `parts` of its best window.
  `--line --best "4h by 07:00 split"` works too.

## [0.1.2] - 2026-10-04

### Fixed

* Chart bars no longer show seams between cells or dark steps at the ends of the price bars in
  terminals whose block glyphs do not fill the whole cell. Solid cells are now drawn as coloured
  backgrounds, and price bars end in real top-aligned blocks instead of inverted colours.

### Changed

* README: an animated demo at the top; a social preview card for link previews.

## [0.1.1] - 2026-10-04

No changes to the program itself. This release refreshes the description on PyPI.

* README: install from PyPI with `pipx install gridhour`, with the GitHub install next to it in
  case PyPI is unreachable; updating, removing and `pipx run` / `uvx` are documented.
* CI and release builds run on pinned runner images (Ubuntu 24.04, macOS 26) instead of `-latest`.

## [0.1.0] - 2026-10-04

First release.

* 48 hour timeline of regional carbon intensity and Octopus Agile prices for a UK postcode.
* Best start time for each job (washing, dishwasher, EV charge, batch job, or your own), ranked by
  carbon, price or both.
* Generation mix rows (wind, solar, gas, nuclear, ...) on the same time axis.
* `--line`, `--tmux`, `--watch` and `--json` for status bars and scripts.
* Six themes (carbon, daylight, slate, ember, mono, colorblind), 12/24 hour clock, compact layout
  for small panes.
* Works offline from cache. Talks only to the two APIs over HTTPS.

[Unreleased]: https://github.com/777dimas/gridhour/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/777dimas/gridhour/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/777dimas/gridhour/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/777dimas/gridhour/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/777dimas/gridhour/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/777dimas/gridhour/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/777dimas/gridhour/releases/tag/v0.1.0
