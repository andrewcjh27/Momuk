# Decision log

What was decided, what the alternatives were, and why. Newest sections at the
bottom. Open questions are listed at the end, waiting for data or a decision.

## Project direction

| Date | Decision | Alternatives considered | Why |
|---|---|---|---|
| 2026-08 | Ship v1 as a hand-weighted rules engine, not ML | A learned model | No usage data yet; a model trained on nothing is a worse rules engine that can't explain itself |
| 2026-10-31 | Test the folklore terms with public data instead of waiting for ~200 logged user decisions | Wait for users | Answers the core question months earlier, and teaches the data stack (PySpark, Databricks, cloud) |
| 2026-10-31 | Databricks + Spark for this project; a separate small AWS project for cloud practice | One project for both | Each stack gets a project shaped for it |
| 2026-10-31 | $0 budget for every tool and data source | Paid data (KT delivery data, paid regional keyword APIs) | Personal constraint; every source below is free |
| 2026-10-31 | First three skills to focus on: forecasting, causal inference, experimentation design | Also geospatial, MLOps, dashboards | These come up in nearly every data science interview loop; others can be added later |

## Data sources

| Date | Decision | Alternatives considered | Why |
|---|---|---|---|
| 2026-10-31 | Korean data only | US data (Yelp, Food.com) | The app is for Korean users |
| 2026-10-31 | Drop KT delivery order data | — | Not reachable from the US; the platform now sells it |
| 2026-10-31 | **Naver search trends** as the demand signal | Delivery orders, NEIS school meals | Free, daily since 2016, nationally representative. Measures craving, not purchases — acceptable for a "what do I feel like" app |
| 2026-10-31 | Register through NAVER API HUB | Naver Developers Center | Developers Center stopped taking new DataLab applications (moved to API HUB on 2026-07-31) |
| 2026-10-31 | Daily resolution, 2016-01-01 → one week before the pull | Weekly / monthly | Weather changes daily; daily can be rolled up later, monthly can't be split back |
| 2026-10-31 | **Anchor rescaling** (김치찌개 in every request) | Tournament of winners | Naver scales each request to its own peak. The anchor puts all 126 dishes on one scale; a tournament keeps only winners and no magnitudes |
| 2026-10-31 | Mid-popularity anchor | A very popular dish | A dominant anchor would squash other dishes in each batch into rounding noise |
| 2026-10-31 | Add **Google Trends by province** as a regional layer | Naver only | Naver has no regional split. Google is noisier in Korea, so it adjusts the national signal rather than replacing it |
| 2026-10-31 | Province is the finest level for analysis | City level | Checked in Google Trends: province is the smallest unit it offers for Korea. City-level detail enters only through the user's live weather in the app |
| 2026-10-31 | Weather from Open-Meteo (ERA5 reanalysis), one point per province (17) | KMA station data; 8 cities | Free and keyless, no missing days. 17 provinces match Google's province codes |
| 2026-10-31 | Keep all 9 weather variables (temperature mean/max/min, apparent temperature, precipitation, rain, snow, precipitation hours, wind) | Temperature + precipitation only | Briefly trimmed to two, then reversed: rain vs snow, drizzle vs downpour and "feels like" temperature are all testable hypotheses |

## Pipeline engineering

| Date | Decision | Why |
|---|---|---|
| 2026-10-31 | Collect data on the laptop, process on Databricks | Free Edition limits outbound internet; raw files are saved untouched so processing can be rerun without re-downloading |
| 2026-10-31 | Medallion layout: bronze (raw) → silver (cleaned) → gold (analysis-ready) | Standard, easy to rebuild from raw when a cleaning step changes |
| 2026-10-31 | Population-weighted national weather, plus per-province weather kept separately | Naver is national, so it needs a national weather series; Google is per province, so it needs per-province weather |
| 2026-10-31 | Save each weather province as soon as it downloads; resume on rerun | One 10-year request counts as ~280 API calls, so the hourly limit was hit and 14 provinces were lost on the first attempt |

## Data quality and cleaning

| Date | Observation | Decision |
|---|---|---|
| 2026-10-31 | 후라이드치킨 (0.78), 생선구이백반 (0.03), 중화볶음밥 (0.06) had near-zero mean interest | The problem was keywords, not popularity: people don't search those exact phrases |
| 2026-10-31 | → | **Keyword entity resolution.** 202 candidates (spellings, spacing, synonyms, generic terms) for 126 dishes. A candidate is kept if it is searched like the dish (correlation of week-to-week changes in log interest, so shared seasons don't count) — with a looser bar for spelling variants that are clearly the same word (jamo-level edit distance) and a stricter bar for generic or ambiguous terms. Report: [`pipeline/reports/keyword_validation.csv`](pipeline/reports/keyword_validation.csv) |
| 2026-10-31 | In testing, generic terms (냉면, 치킨) had the most searches and pushed out specific names | Only a specific name can be a dish's reference; generic terms must prove they behave like it |
| 2026-10-31 | Result on real data: 177 candidates kept, 25 dropped. Main names 95%, spacing variants 100%, spellings 86%, synonyms 78%, generic terms 22% kept | 46 dishes now use a different or larger keyword set |
| 2026-11-02 | 7 dishes (부리토, 똠얌꿍, 리조또, 인도커리, 브런치, 햄버거, 쌀국수) were sent to Google Trends with pipe-joined keywords, because an outdated script was still in use; four came back with almost no regional data | Google lookups use each dish's top validated keyword; the script re-fetches any dish whose keyword changed |
| 2026-10-31 | 마라탕 and 로제떡볶이 sit near zero before their boom years | **Open** — see below |

## Personalization design

| Date | Decision | Why |
|---|---|---|
| 2026-10-31 | Population model first; personal layers on top, weighted more as data accumulates | Population data alone gives everyone in the same place and weather the same answer |
| 2026-10-31 | Time of day (morning / lunch / dinner / late night) as catalog columns | Naver data is daily, so time of day can't be learned from it; drafted by rule, to be reviewed |
| 2026-10-31 | Weekday vs weekend measured from data (weekend lift) | Daily data supports it directly |
| 2026-10-31 | Optional onboarding: up to 5 dishes you love, any you never want | Fixes day one. "Never" is a hard exclusion; "love" boosts similar dishes through catalog attributes (content-based filtering) |
| 2026-10-31 | Personal patterns (e.g. 해장 on Saturday mornings) from the app's own logs | No public data can show an individual's habits |

## Open questions

- **Dish start dates:** from when should each newer dish (마라탕, 로제떡볶이, 마라샹궈…) count? Zeros before a boom aren't "low interest".
- **Viral spikes:** keep, flag or remove — and how large a spike counts as an outlier?
- **Coarse series:** below how many distinct values is a dish too coarse to model?
- **Rainy-day definition:** national average rain ≥ 1 mm, or share of the population that got rain?
- **냉면 → 물냉면:** the validation kept 냉면 (17× the searches, change correlation 0.74), so 물냉면's series is now mostly generic 냉면, which also covers 비빔냉면. Keep, or keep 물냉면 alone?
- **카레 → 카레라이스:** kept (correlation 0.84), but 카레 also covers Indian curry, which is its own dish.
- **Fried chicken is still under-measured:** 후라이드 and 프라이드치킨 behaved differently and 치킨 is generic, so 후라이드치킨 remains alone. Split 치킨 across the three chicken dishes, or merge them?
- **Holidays and COVID (2020–2022):** flag, model, or exclude?
- **Meal-time columns:** drafted by rule; review dish by dish.
