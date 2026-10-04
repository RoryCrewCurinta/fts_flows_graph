# Aid flows map

An interactive map of humanitarian funding flows per country: who funded whom, how much was passed on,
how much reached national NGOs, and how much is cash.

## Run it

```
powershell -ExecutionPolicy Bypass -File .\setup.ps1      # once: venv, requirements, git init, opens VS Code
.\.venv\Scripts\python.exe build_all.py 2025 2026        # builds from cache/ if present
.\.venv\Scripts\python.exe build_all.py 2025 2026 --refresh   # pulls fresh data from the APIs
```

The page is written to `docs/index.html`. Open it in a browser, or serve `docs/` with GitHub Pages.

To add a country, add a line to `countries.txt` (`ISO3|Name`, with the name as FTS writes it, e.g. `Sudan`),
then run `build_all.py`.

## Files

| Path | What it is |
|---|---|
| `build_country.py` | Pulls and builds one country: `python build_country.py TCD Chad 2025 2026` |
| `build_all.py` | Runs every country in `countries.txt`, then `make_page.py` |
| `make_page.py` | Combines `data/*.json` and `template.html` into `docs/index.html` |
| `template.html` | The page itself (D3, no build step) |
| `overrides/<ISO3>.json` | Manual corrections to organisation labels |
| `review/<ISO3>.csv` | Organisations FTS tags as national or local, with funders, for a person to confirm |
| `reference/` | Two small files from the CALP CVA tracking pipeline (question list, classifier-accepted flows) |
| `cache/` | Raw API pulls (not committed) |
| `data/` | Built country files (not committed) |

## Sources

- OCHA Financial Tracking Service flows and response plan projects: `api.hpc.tools`
- OCHA pooled fund data hub (allocations and sub-grants by partner type): `cbpfapi.unocha.org`
- IATI, through d-portal (implementing partners named by UNICEF and IRC; UNHCR by type)
- Cash estimate rules: The-CALP-Network/CALP-CVA-Tracking-Pipeline, with in-kind flows excluded

## Known limits

- FTS is self-reported. Multi-year flows count in full in each year they touch.
- FTS parent links do not trace money between organisations, so paths beyond direct links are connections, not traced dollars.
- Sub-grants from pooled funds are published by partner type only.
- The cash estimate applies planning-stage project cash shares to funding received. Most plans have no project links, so there it equals the tagged amount.
- IATI figures are spending and can include development money. Only US dollar publishers are read.
- "National or local" follows FTS unless corrected in `overrides/`. Check `review/` before quoting local shares.
- The pooled fund API is sometimes unavailable; rerun if a country fails.
