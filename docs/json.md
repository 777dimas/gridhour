# JSON output: schema 1

`gridhour --json` prints one JSON object. Check `schema` before consuming it. Within schema 1,
changes are additive only: existing keys are not removed or renamed, and their types, units and
meanings stay compatible. A breaking change requires a new schema number. Consumers should ignore
unknown keys, accept documented nulls and avoid depending on object key order.

All date-times are UTC ISO 8601 strings ending in `Z`, with minute precision. Carbon intensity is
in gCO₂/kWh; prices are p/kWh including VAT. A missing measurement is `null`, never zero: zero and
negative prices are real values. `errors` describes refresh problems; cached or partial data can
still be present. `slots` contains only half hours with some carbon or price data, so it can have
gaps and can be empty. The current half hour may be missing or contain null measurements.

## Top-level fields

| Key | Type | Meaning and nullability |
| --- | --- | --- |
| `schema` | integer | Format version, currently `1`; never null. |
| `at` | string | Evaluation time (including a requested `--at`), not fetch time. |
| `region` | object | Region fields below; never null. |
| `tariff` | string or null | Octopus electricity tariff code; null when no prices are available. |
| `mode` | string | Effective ranking mode: `green`, `cheap` or `both`; may fall back when prices are missing. |
| `now` | slot or null | Half hour containing `at`; null when no slot contains it. |
| `green_now` | boolean | Whether the current slot is graded low or very low; false without one. |
| `green_until` | string or null | End of the current continuous green period; null if not green now. |
| `next_green` | object or null | Next/current green slot; null when none exists in the forecast. |
| `jobs` | array of jobs | Saved jobs and their recommended windows; can be empty. |
| `slots` | array of slots | Available half-hour measurements in chronological order; can be empty. |
| `fetched` | string or null | Oldest fetch time of the data shown; null if no fetch time is known. |
| `errors` | array of strings | Refresh/cache diagnostics; empty when none are reported. |
| `best` | window or null, optional | Present only with `--best DURATION`; null without a complete window. |

## Nested fields

| Object | Key | Type | Meaning and nullability |
| --- | --- | --- | --- |
| region | `id` | integer | NESO region identifier; never null. |
| region | `name` | string | Region display name; never null. |
| region | `postcode` | string or null | Normalized outward postcode; null when using a region. |
| slot | `from`, `to` | string | Half-hour start (inclusive) and end (exclusive). |
| slot | `carbon` | number or null | Forecast carbon intensity in gCO₂/kWh; null if unavailable. |
| slot | `index` | string or null | NESO grade: very low, low, moderate, high or very high; null if unavailable. |
| slot | `price` | number or null | Price in p/kWh including VAT; null if unavailable. |
| slot | `mix` | object or null | Fuel names mapped to numeric generation percentages; null if unavailable. Fuel keys can vary. |
| next_green | `from` | string | Start of the green half hour. |
| next_green | `in_minutes` | integer | Whole minutes until it starts, clamped to zero for a current slot. |
| job | `name` | string | Saved job name. |
| job | `minutes` | integer | Required running duration in minutes. |
| job | `deadline` | string or null | UK-local `HH:MM` deadline; null without one. |
| job | `deadline_at` | string or null | Resolved deadline in UTC; null without one. |
| job | `split` | boolean | Whether the job may run in separate pieces. |
| job | `best` | window or null | Best complete window; null when no complete window is available. |
| job | `if_started_now` | object | Starting-now comparison; each of `carbon` and `price` is a number or null, with the units above. |
| window | `from`, `to` | string | First start and final end, including gaps for split jobs. |
| window | `starts_in_minutes` | integer | Whole minutes to the first start, clamped to zero. |
| window | `carbon`, `price` | number or null | Whole-window averages, rounded to 1/2 decimal places respectively; null when unavailable. |
| window | `parts` | array of objects | Continuous running pieces; each has UTC string `from` and `to`. |

## Example shape

This fixture-derived example shortens `jobs` and `slots` to one entry each. Its values illustrate
the format; they are not live market data. The documented keys are checked against fixture-backed
output in `test_json_documented_shape`.

```json
{
  "schema": 1,
  "at": "2026-10-03T22:46Z",
  "region": {
    "id": 13,
    "name": "London",
    "postcode": "SW1A"
  },
  "tariff": "E-1R-AGILE-24-10-01-C",
  "mode": "both",
  "now": {
    "from": "2026-10-03T22:30Z",
    "to": "2026-10-03T23:00Z",
    "carbon": 251,
    "index": "very high",
    "price": 30.18,
    "mix": {
      "biomass": 11.9,
      "coal": 0.0,
      "imports": 2.8,
      "gas": 60.1,
      "nuclear": 19.0,
      "other": 0.0,
      "hydro": 0.2,
      "solar": 0.0,
      "wind": 6.1
    }
  },
  "green_now": false,
  "green_until": null,
  "next_green": {
    "from": "2026-10-04T06:30Z",
    "in_minutes": 464
  },
  "jobs": [
    {
      "name": "Washing",
      "minutes": 120,
      "deadline": null,
      "deadline_at": null,
      "split": false,
      "best": {
        "from": "2026-10-04T11:00Z",
        "to": "2026-10-04T13:00Z",
        "starts_in_minutes": 734,
        "carbon": 104.2,
        "price": 6.25,
        "parts": [
          {
            "from": "2026-10-04T11:00Z",
            "to": "2026-10-04T13:00Z"
          }
        ]
      },
      "if_started_now": {
        "carbon": 243.0,
        "price": 28.64
      }
    }
  ],
  "slots": [
    {
      "from": "2026-10-03T20:00Z",
      "to": "2026-10-03T20:30Z",
      "carbon": 279,
      "index": "very high",
      "price": 33.28,
      "mix": {
        "biomass": 8.0,
        "coal": 0.0,
        "imports": 7.8,
        "gas": 66.6,
        "nuclear": 14.3,
        "other": 0.0,
        "hydro": 0.1,
        "solar": 0.0,
        "wind": 3.2
      }
    }
  ],
  "fetched": "2026-10-03T22:46Z",
  "errors": [],
  "best": {
    "from": "2026-10-04T11:00Z",
    "to": "2026-10-04T13:00Z",
    "starts_in_minutes": 734,
    "carbon": 104.2,
    "price": 6.25,
    "parts": [
      {
        "from": "2026-10-04T11:00Z",
        "to": "2026-10-04T13:00Z"
      }
    ]
  }
}
```
