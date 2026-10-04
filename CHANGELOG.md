# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [semantic versioning](https://semver.org/).

## [Unreleased]

### Fixed

* Network requests now return within the overall deadline even when DNS resolution stalls,
  allowing status lines to fall back to cached forecasts. Outstanding requests are capped.

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

[Unreleased]: https://github.com/777dimas/gridhour/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/777dimas/gridhour/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/777dimas/gridhour/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/777dimas/gridhour/releases/tag/v0.1.0
