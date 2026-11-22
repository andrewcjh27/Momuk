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
| 2026-11-21 | **Automate inside Databricks** (scheduled Jobs): ingestion moves from the laptop into notebooks | Tested from a Free Edition notebook: Open-Meteo (archive and forecast), Naver API HUB and Google Trends are all reachable, so the earlier "collect on the laptop" constraint no longer holds. GitHub Actions kept as the fallback |
| 2026-11-21 | Refresh cadence: Naver and weather weekly, Google regional monthly, calendar yearly; the recommender reads live weather from the Open-Meteo forecast | Search trends move week to week; regional lean is slow-moving and Google rate-limits hard |
| 2026-11-22 | Naver keys stored in a Databricks secret scope (`momuk`), created with the Databricks CLI | Keys never appear in notebooks or git; a test request from a notebook returned data (HTTP 200) |
| 2026-11-22 | **New-dish discovery every two weeks, human-approved**: the job pulls rising food searches from Google Trends, drops dishes already in the catalog, and writes a candidate list; Junho approves dishes and fills in price/solo/hunger/meal by hand. Fading dishes are flagged for review, never auto-removed | Fads appear less often than weekly; rising searches include celebrities, brands and memes, and the recommender's filters need hand-made attributes, so full automation would add junk |

## Data quality and cleaning

| Date | Observation | Decision |
|---|---|---|
| 2026-10-31 | 후라이드치킨 (0.78), 생선구이백반 (0.03), 중화볶음밥 (0.06) had near-zero mean interest | The problem was keywords, not popularity: people don't search those exact phrases |
| 2026-10-31 | → | **Keyword entity resolution.** 202 candidates (spellings, spacing, synonyms, generic terms) for 126 dishes. A candidate is kept if it is searched like the dish (correlation of week-to-week changes in log interest, so shared seasons don't count) — with a looser bar for spelling variants that are clearly the same word (jamo-level edit distance) and a stricter bar for generic or ambiguous terms. Report: [`pipeline/reports/keyword_validation.csv`](pipeline/reports/keyword_validation.csv) |
| 2026-10-31 | In testing, generic terms (냉면, 치킨) had the most searches and pushed out specific names | Only a specific name can be a dish's reference; generic terms must prove they behave like it |
| 2026-10-31 | Result on real data: 177 candidates kept, 25 dropped. Main names 95%, spacing variants 100%, spellings 86%, synonyms 78%, generic terms 22% kept | 46 dishes now use a different or larger keyword set |
| 2026-11-02 | 7 dishes (부리토, 똠얌꿍, 리조또, 인도커리, 브런치, 햄버거, 쌀국수) were sent to Google Trends with pipe-joined keywords, because an outdated script was still in use; four came back with almost no regional data | Google lookups use each dish's top validated keyword; the script re-fetches any dish whose keyword changed |
| 2026-11-02 | Re-fetch finished: all 126 dishes have regional data under their top keyword; 123 cover all 16 provinces (fewest: 중화볶음밥, 10) | Shrinkage now affects only a handful of dishes |
| 2026-11-14 | Province level dilutes city specialties: 추어탕 is famous in Namwon, but leans only 1.31 in Jeollabuk-do as a whole | Accept as a known limit of province data; city specialties are under-weighted, never wrongly boosted |
| 2026-11-14 | Low-volume dishes give noisy leans: Chungcheongbuk-do's top dish is 부리토 (1.39); Ulsan's 닭칼국수 (2.29) has no obvious explanation | Treat as noise for now; consider a minimum national-interest threshold before trusting a dish's regional lean |
| 2026-11-14 | Some raw leans are very large (막국수 5.18 in Gangwon, 밀면 4.01 in Busan), partly from tourists searching before a trip | Keep the 0.5–2.0 clip, so region can at most double a dish's score |
| 2026-11-14 | 곰탕's search term had become 나주곰탕 (slightly more searched than 곰탕), so the regional lookup searched a Naju-named dish and its ×3.68 Jeollanam-do lean was circular | Withdrew the 곰탕 regional finding. Place-named candidates (나주곰탕, 안동찜닭) are now kind `regional`: never the reference, strict bar to be kept. Re-run validation, Naver and Google for 곰탕 |
| 2026-11-14 | Locals may search less for regional food they already know, and visitors search more, so a province's lean may reflect tourists rather than local eating | **Test before adjusting.** Dialing region down for everyone would hurt dishes that are both famous and everyday local food (e.g. 돼지국밥 in Busan). Tourist-season test: does the dish's in-province share rise in holiday and vacation weeks? Adjust only dishes that show a visitor pattern |
| 2026-11-18 | Tourist-season test results ([`pipeline/reports/visitor_signature.csv`](pipeline/reports/visitor_signature.csv)): no dish shows a clear visitor pattern. Ratios ×0.99–1.08; only 칼국수 in Daejeon barely excludes 1 (1.00–1.16). Four province series were too sparse to test (≥ 240 of 260 weeks below Google's reporting minimum), including the Gangwon control | **Keep regional leans unadjusted.** Limits: weekly data can't see year-round weekend trips, and Gangwon's winter ski season counts as an off-season week |
| 2026-11-18 | Fried chicken was under-measured: 치킨 is searched ~36× more than 후라이드치킨, and the three flavour dishes each tracked only their own name, so chicken almost never reached recommendations (크리스마스 → 치킨 only ×1.18) | **Merged 후라이드치킨, 양념치킨 and 간장치킨 into one dish, 치킨**, searched as `치킨\|후라이드치킨\|양념치킨\|간장치킨`. A dish should match how people *choose* (치킨 first, flavour when ordering), not how they order. Alternatives: keep three dishes and split 치킨's demand by flavour share (rests on an assumed split), or leave as is. Applied by `merge_chicken.py`; spice set to 1 for the merged dish (flavours were 0 / 2 / 0). Lesson for the method: when a dish's own name is rarely searched it makes a poor reference, so the right keyword (치킨) had failed the correlation test against it. The app's catalog still has three flavours |
| 2026-11-21 | 냉면 (17× the searches, change correlation 0.74) had been merged into 물냉면's keywords | **Keep 냉면 in 물냉면.** When people say 냉면 they mostly mean 물냉면 |
| 2026-11-21 | 카레 (4.1× the searches) had been merged into 카레라이스 — does it also cover Indian curry? | **Plain 카레 counts as 카레라이스; Indian curry stays separate.** In Korea, plain 카레 usually means the everyday Japanese/Korean-style curry rice, so 카레라이스 is searched as `카레\|일본카레\|카레라이스`, and 커리 (인도 카레) keeps its own `인도커리\|인도카레` |
| 2026-11-21 | Should food days like 설날 and 추석, when many people eat at home, be handled differently? | **Leave as is.** People eating at home won't be looking at a recommendation anyway |
| 2026-11-21 | Holiday foods missing from the catalog (송편, 모둠전) | **Not added.** 추석 → 김치전 stays as measured |
| 2026-11-21 | 동지 was dropped because its food wasn't in the catalog | **Added 팥죽 and brought 동지 back, for 팥죽 only.** 팥죽: hot, soupy, mild, light, cheap, solo, quick, lunch and dinner. On 동지 (Dec 21–22) many dishes rise with Christmas-dinner searches, so `EVENT_ONLY` keeps 동지's boost to 팥죽 alone |
| 2026-11-21 | While re-adding 동지: the solar-term calculation used the sun's J2000 position and was up to 15 minutes off, which put 2025's 동지 (00:02 KST on Dec 22) on Dec 21 | **Fixed** to use the sun's apparent position, which matches the astronomy library's solstice times exactly. Only 2025's 동지 moved; every 복날 date was unchanged |
| 2026-11-21 | Planning automatic refreshes: which pieces need fresh data, and how often? | **Weekly** for recent popularity and weather; weekly-to-monthly for the weather and food-day lifts and monthly for regional leans (they need years of data or are rate-limited); live in the app for today's weather, hour, date and the 3 answers. Build after the cleaning notebook |
| 2026-11-21 | 막창 and 대창 had been tested as other names for 곱창 and rejected: each has about two-thirds of 곱창's searches but doesn't move with it (change correlation 0.33 and 0.14) | **Added 막창 and 대창 as their own dishes**, with 곱창's attributes. Unlike chicken (flavour names rarely searched), these are well searched and behave independently — distinct cravings, not other names |
| 2026-11-21 | Lamb was missing from the catalog | **Added 양꼬치** (중식; skewers, shared, mid-price, dinner and late night) **and 양고기** (grilled lamb such as 양갈비; shared, pricey, dinner). Each is searched under its own name; 양갈비 is a candidate synonym for 양고기, left for validation to test |
| 2026-11-21 | A review of the catalog found common eat-out and delivery foods missing | **Added 14 dishes** (catalog now 143): 닭발, 아구찜 (해물찜 as a synonym), 김치찜, 샤브샤브, 오므라이스, 함박스테이크, 육회, 오리고기, 닭한마리, and, for testing findings, 백숙 and 장어구이 (복날), 낙곱새 (a Busan-born dish), 조개구이 (seaside outings), 포케 (health trend). Attributes are drafted and open to review. Not added: 붕어빵, 호떡, 핫도그 — snacks, not meals; 죽 was drafted, then removed |
| 2026-10-31 | 마라탕 and 로제떡볶이 sit near zero before their boom years | **Open** — see below |

## Personalization design

| Date | Decision | Why |
|---|---|---|
| 2026-10-31 | Population model first; personal layers on top, weighted more as data accumulates | Population data alone gives everyone in the same place and weather the same answer |
| 2026-10-31 | Time of day (morning / lunch / dinner / late night) as catalog columns | Naver data is daily, so time of day can't be learned from it; drafted by rule, to be reviewed |
| 2026-10-31 | Weekday vs weekend measured from data (weekend lift) | Daily data supports it directly |
| 2026-10-31 | Optional onboarding: up to 5 dishes you love, any you never want | Fixes day one. "Never" is a hard exclusion; "love" boosts similar dishes through catalog attributes (content-based filtering) |
| 2026-10-31 | Personal patterns (e.g. 해장 on Saturday mornings) from the app's own logs | No public data can show an individual's habits |

## Recommender v0

| Date | Observation | Decision |
|---|---|---|
| 2026-11-14 | First sanity checks (Busan, rainy, solo vs Seoul, dry, group of 3): filters and regional dishes behave sensibly, but 밀면 — a cold noodle — ranked 5th on a rainy day | **Add temperature to the score.** `temp_boost` = a dish's average interest in today's 5 °C temperature bin ÷ its overall average, clipped to 0.5–2.0. Predictive, not causal: it captures season and temperature together |
| 2026-11-14 | Regional lean (up to ×2) outweighs rain (≤ ×1.25): 곱창 beat 삼겹살 in Seoul despite half the national popularity | **Lowered the cap to ×1.5** (and the floor to ×0.67), decided 2026-11-21. Region can now move a score by at most 50%. Trade-off: every lean above 1.5 ties (밀면 at ×4.0 and 어묵 at ×1.7 both count as 1.5); the backtest can tune the cap later |
| 2026-11-14 | Time of day matters: people eat 고기 less at lunch than dinner, and 브런치 at lunch, not dinner | **Add a time-of-day fit** from the catalog's `meal_*` columns: ×1.0 if the dish fits the current meal (morning 5–10, lunch 11–15, dinner 16–20, late night 21–4), ×0.3 if not. Soft, so off-meal dishes stay possible. Fixed 브런치 to count as lunch. Naver data is daily, so this comes from the catalog, not from search data |
| 2026-11-14 | Weekend lift was measured but not used, and Korean food days (복날 → 삼계탕, 설날 → 떡국, 크리스마스 → 치킨 …) were missing | **Add a calendar boost.** Weekend lift on Sat/Sun. For food days, an event study: each event day vs the same weekday 1–3 weeks before and after (removes weekday and season), median across 2016–2026, clipped to 0.5–3.0. Calendar built by `build_calendar.py`: 설날/추석 from the lunar calendar, 복날 from solar terms and the 경일 rule (checked against published 2023–2025 dates), 동지 (later removed), 크리스마스, 수능, 삼겹살데이, 블랙데이 |
| 2026-11-14 | Payday (25th–29th) was in the first calendar draft | **Removed from the pipeline calendar** — a monthly 5-day window isn't a food day, and its effect belongs to budget rather than dish choice. The app's own payday term is unchanged |
| 2026-11-18 | First food-day results: 복날 → 삼계탕, 설날 → 떡국 and 삼겹살데이 → 삼겹살 all hit the ×3 cap, hiding their true size | **Report the true lift; cap only the score.** `event_lift_raw` is kept for findings; the 0.5–3.0 clip applies only when scoring. True sizes: 삼계탕 ×9.73 on 복날, 떡국 ×8.16 on 설날, 삼겹살 ×4.01 on 삼겹살데이, 스테이크 ×3.59 at Christmas |
| 2026-11-18 | 동지's top dishes were 스테이크 and pasta: as Dec 21–22 it picked up Christmas-dinner searches, and its own food (팥죽) isn't in the catalog | **Dropped 동지** from the calendar rather than patching its baseline — it carried only Christmas noise |
| 2026-11-18 | 추석 → 김치전 came out ×0.76 | Not a failure of the folklore so much as a catalog gap: 명절 전 are 동그랑땡, 동태전, 모둠전. See open questions |
| 2026-11-14 | Fried chicken never appears, even for a hungry group | Caused by the keyword issue below; settle that first |
| 2026-11-14 | 파전 and 김치전 are hidden from solo diners (`solo = 0`), even on rainy days | **Keep them hidden from solo diners** (decided 2026-11-21): 전 is a sharing dish, so `solo` stays 0 |
| 2026-11-22 | COVID years (2020–2022) might look unusual | **Keep them as ordinary data, no flag**: people still searched for and ordered food, and the searches are the signal the app cares about. Holidays are already handled by the food calendar |

## Open questions

- **Dish start dates:** from when should each newer dish (마라탕, 로제떡볶이, 마라샹궈…) count? Zeros before a boom aren't "low interest".
- **Viral spikes:** keep, flag or remove — and how large a spike counts as an outlier?
- **Coarse series:** below how many distinct values is a dish too coarse to model?
- **Rainy-day definition:** national average rain ≥ 1 mm, or share of the population that got rain?
- **Meal-time columns:** drafted by rule; review dish by dish.
