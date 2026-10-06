# Security policy

## Reporting a problem

Please report security problems privately through
[GitHub's private vulnerability reporting](https://github.com/777dimas/gridhour/security/advisories/new),
not in a public issue. You should get a reply within 5 working days. Once a fix is out I credit the
reporter in the advisory and the changelog, unless you ask me not to.

## Supported versions

Only the latest release gets fixes.

## What gridhour does that matters for security

**Network.** HTTPS GET requests to two hosts and nothing else: `api.carbonintensity.org.uk` (with the
first half of your postcode, for example `SW1A`) and `api.octopus.energy` (with your region letter).

* `grid.http_json` refuses any other scheme or host, refuses redirects, and checks the final URL.
* A response may be 4 MB at most, and the whole request, DNS lookup included, must finish within
  25 seconds, however slowly it trickles in. Python cannot cancel a stuck resolver, so at most two
  such requests are left running in the background.
* No API keys, no accounts, no telemetry. `GRIDHOUR_OFFLINE=1` turns the network off.

**Untrusted input.** API responses, the cache and the config file are all treated as hostile.

* Every field is type- and range-checked before use: numbers must be finite and plausible
  (booleans and strings are refused), fuel and index names must be known values, times must be
  ISO 8601. A bad row costs that half hour, not the whole forecast.
* A response is checked before it is cached, so a broken one is never stored. A cache entry that
  no longer passes the checks, or carries a timestamp from the future, is ignored.
* Text that is shown (the region name, job names) loses control characters, bidi and zero-width
  characters, combining marks and double-width characters, so it can neither send escape
  sequences to your terminal nor shift or reorder the screen. In `--tmux` output every `#` is
  doubled, so no text can become a tmux format or a `#(command)`. `--json` output is pure ASCII.
* Error messages never repeat response content.
* An Octopus product code, whether from the API or from `--tariff` and the config file, must match
  `[A-Z][A-Z0-9]*(-[A-Z0-9]+)+` exactly, and is at most 60 characters long. The region letter must
  be one of the fourteen known ones, before either goes into a URL or a cache file name.
* Malformed responses, config files and arguments produce an error message, not a crash. The
  test suite in `tests/test_security.py` holds the cases.

**Files.** `~/.config/gridhour/config.json` (postcode outward code, jobs, theme) and
`~/.cache/gridhour/*.json` (checked API responses). Both directories are kept at `0700` (tightened
if they already exist with looser modes) and the files at `0600`. Writes go to a fresh temporary
file created with `O_EXCL` and are renamed into place, so a planted symlink is never followed.
`gridhour --reset` deletes the config and the cache.

**Dependencies.** None at runtime, only the Python standard library.

## Supply chain

* Every GitHub Action is pinned to a full commit SHA. Workflows run with read-only tokens unless a
  job needs more, and never keep the checkout credentials.
* CI installs its tools from hash-locked files (`requirements/*.txt`, `pip --require-hashes`).
* CodeQL (Python and the workflows), OpenSSF Scorecard and dependency review run on the repository.
  `zizmor --persona=pedantic` and `actionlint` are clean.
* A release runs only for a `vX.Y.Z` tag on a commit that is already on `main`, needs approval in
  the `pypi` environment, and goes to PyPI through trusted publishing (OIDC, no stored token). The
  jobs holding an OIDC token install nothing and can reach only an allowlist of hosts.
* Every release file carries signed build provenance. To check a file you downloaded:

  ```sh
  pip download gridhour==0.3.0 --no-deps -d .
  gh attestation verify gridhour-0.3.0-py3-none-any.whl --repo 777dimas/gridhour \
      --signer-workflow 777dimas/gridhour/.github/workflows/release.yml --source-ref refs/tags/v0.3.0
  ```
