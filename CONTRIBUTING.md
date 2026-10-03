# Contributing

Bug reports, ideas and pull requests are welcome. For anything bigger than a small fix, open an
issue first so we can agree on the shape before you write the code.

## Setup

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r requirements/dev.txt
pip install --no-deps -e .
pre-commit install          # ruff and a secret scan before each commit (first run downloads Go for gitleaks)
```

## Checks

```sh
pytest                      # a few seconds; sockets are blocked, nothing reaches the network
ruff check .
coverage run -m pytest && coverage report     # CI fails below 80%
python -m gridhour --once --size 120x40       # one frame of the UI with today's data
pip install --require-hashes -r requirements/docs.txt && python tools/screenshots.py   # docs/*.png
```

The tests replay real API responses stored in `tests/fixtures/`. If you need new fixtures, fetch
them with `curl` and commit them; they show up in diffs on purpose.

If you touch `.github/workflows/`, also run `zizmor --persona=pedantic .github/workflows` and
`actionlint`.

## Dependencies

There are no runtime dependencies and there should not be any. Development tools are pinned with
hashes. To change them, edit `requirements/*.in` and recompile:

```sh
uv pip compile --universal --python-version 3.11 --generate-hashes requirements/dev.in -o requirements/dev.txt
```

Dependabot proposes updates weekly, a week after a release appears upstream.

## House rules

* Text from the network or a file passes through `safe.label` before it is stored, and everything
  drawn goes through `Canvas.put`. Nothing outside writes straight to `sys.stdout`.
* New network calls go through `grid.http_json`, which checks the host and refuses redirects.
* New fields from an API are checked in `grid.parse_*` (type, range, known values) and get a case
  in `tests/test_security.py`.
* Match the style around you: `%` formatting, short functions, comments that say why.
* Add a line to `CHANGELOG.md` under "Unreleased" for anything a user would notice.

## Releasing

1. In a pull request: bump `__version__` in `gridhour/__init__.py`, move the "Unreleased" entries
   under `## [X.Y.Z] - YYYY-MM-DD`, and add the compare link at the bottom.
2. Once it is merged, tag the merge commit on `main` and push the tag:
   `git tag vX.Y.Z origin/main && git push origin vX.Y.Z`.
3. The release workflow checks that the commit is on `main`, that the tag matches the version and
   that the changelog has the entry. It then runs the tests, builds, attests and waits for your
   approval in the `pypi` environment before publishing to PyPI and creating the GitHub Release.
