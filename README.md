# Nebraska County Atlas, version 2

Schools, property taxes and the local economy for Nebraska's 93 counties and 244 school systems,
built from public data. A personal project by Tyler Kelley, not a product of the Nebraska Department of Education.

**Status:** under construction. The site carries a draft banner and tells search engines not to index it until launch (target February 15, 2027).

## How it fits together

| Piece | Where | What it does |
|---|---|---|
| Data pipeline | `nebraska-economy` (private) | Pulls sources, keeps raw files, builds DuckDB and the measures, audits them |
| Measures bundle | `data/` here | Pushed by the pipeline after each passing build |
| Indicator registry | `registry/indicators.csv` | Every label, unit, source, bin edge, legend and ramp. Edit in Excel |
| Crosswalks | `registry/crosswalk_*.csv` | Display names, NDE names, counties, tiers |
| Design tokens | `design/tokens.css` | Rusted Modern colors and type. The only place colors are defined |
| Templates | `templates/` | One per page type |
| Tests | `tests/` | Must pass before anything publishes |

## Color rules

- Rust and slate mean down and up since the base year, on change measures only.
- Tan to dark brown means how much. Darker is more.
- Charcoal is for text, dark bands and buttons.
- Every map uses exactly one ramp and always shows its legend; every change number carries a + or − sign.

## Build locally

```
pip install jinja2 pytest numpy
python -m pytest -q tests
python scripts/build.py   # writes _site/
```
