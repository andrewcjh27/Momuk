# momuk data pipeline

Tests the app's food folklore ("전 on rainy days", "해장 food on weekends")
against ten years of Korean search and weather data, and builds a first
data-driven recommender. Every tool and source is free.

```
 laptop (collect)                                Databricks (process, PySpark)
 ───────────────                                 ─────────────────────────────
 momuk-data.csv ─┐                               bronze   raw files as tables
 Naver API ──────┼─► ingest_local.py ─┐             │
 Open-Meteo ─────┘                    ├─► raw/ ─►  silver   rescaled, filled, weighted, flagged
 Google Trends ─────► ingest_google_  │             │
                      trends.py ──────┘          gold     one row per dish per day / per province
 validate_keywords.py → search_keyword column       │
                                                 analysis + recommender v0
```

## Data sources

| Source | What | Level | Access |
|---|---|---|---|
| [Naver search trends](https://guide.ncloud-docs.com/docs/apihub-overview) (NAVER API HUB) | Relative search interest, 0–100 per request | National, daily, 2016 → | Free tier, key required |
| [Google Trends](https://trends.google.com) via [trendspyg](https://pypi.org/project/trendspyg/) | Interest by province, last 5 years | 16–17 provinces | Free, no key, strict rate limits |
| [Open-Meteo historical](https://open-meteo.com/en/docs/historical-weather-api) (ERA5 reanalysis) | 9 daily weather variables | 17 provinces, daily | Free, no key, non-commercial |
| `momuk-data.csv` | 126 dishes with hand-made attributes and tags | — | Hand-written, see the main README |

Raw data is not committed (`raw/` is git-ignored): it is large, and the
sources' terms apply to it. The scripts recreate it.

## Files

| File | Role |
|---|---|
| `ingest_local.py` | Naver trends in batches of 4 dishes + the 김치찌개 anchor, and province weather. `--naver-only`, `--weather-only`; weather resumes after rate limits |
| `validate_keywords.py` | Keyword entity resolution: keeps a candidate keyword only if it behaves like the dish in search data. Writes `search_keyword` into `momuk-data.csv` |
| `keyword_candidates.csv` | 202 hand-listed candidates (spellings, spacing, synonyms, generic, ambiguous) |
| `ingest_google_trends.py` | Province profile for each dish's top keyword. Resumable; re-fetches dishes whose keyword changed |
| `momuk-data.csv` | Pipeline copy of the catalog: the app's 14 columns plus `meal_*` time-of-day columns and `search_keyword` |
| `notebooks/momuk_01_bronze_silver_gold.py` | Databricks: anchor rescaling, missing-day fill, weather (national + province), gold table, rain lift, weekend lift |
| `notebooks/momuk_02_regional.py` | Databricks: regional lean with shrinkage, regional hypotheses, recommender v0 |
| `reports/keyword_validation.csv` | Every keyword candidate with volume share, change correlation, string similarity, decision and reason |

## Run it

```bash
pip3 install requests pandas trendspyg
# .env next to the scripts:  NAVER_CLIENT_ID=...  NAVER_CLIENT_SECRET=...
python3 validate_keywords.py          # resolve keywords (few minutes)
python3 ingest_local.py               # Naver + weather (weather may need an hourly rerun)
caffeinate -i python3 ingest_google_trends.py   # hours; rerun after rate limits
```

Upload `momuk-data.csv` and `raw/*.csv` to the Databricks volume
`/Volumes/workspace/momuk/raw`, then run notebook 01, then 02.

## Methods in brief

- **Anchor rescaling.** Naver scales each request to its own peak. 김치찌개 is
  in every request; each batch is multiplied by
  `mean anchor total / this batch's anchor total`, which puts all 126 dishes
  on one scale without distorting day-to-day movement.
- **Keyword entity resolution.** Two signals per candidate: jamo-level
  Levenshtein similarity (spelled like the dish?) and correlation of
  week-to-week changes in log interest (searched like the dish? — changes, so
  that shared seasons don't count as similarity).
- **Rain and weekend lift.** Median ratio of interest on rainy vs dry days
  within the same month × weekday (and weekend vs weekday within the same
  month × rain state), so season and weekday don't masquerade as weather.
- **Regional lean.** Province value ÷ the dish's average across provinces,
  shrunk toward 1 when few provinces have data, and clipped to 0.5–2.
- **Recommender v0.** `score = √popularity × rain boost × regional lean`,
  after filtering by the three questions.

## Known limitations

- Searches measure craving, not purchases, and include people cooking at home.
- Naver is national only; regional differences come from Google, which is used
  less in Korea and is noisier.
- Search interest is relative, so absolute demand can't be estimated.
- The cleaning decisions listed as open in [`DECISIONS.md`](../DECISIONS.md)
  are not applied yet; the first findings in the main README are provisional.
