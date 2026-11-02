# momuk

**오늘 뭐 먹지** — a menu suggester that answers *what* to eat, not *where*.

It reads the weather, the air quality, the hour and the day, asks you three
things (how many people, how hungry, what budget), and returns one dish with a
visible reason. No accounts, no server, no API keys.

The project has two parts, built in this order:

| Part | State | What it is |
|---|---|---|
| **The app** (this folder) | Working end to end, built from the Figma designs | A transparent, hand-weighted rules engine in the browser |
| **The data pipeline** ([`pipeline/`](pipeline/)) | Data collected, first results in | PySpark on Databricks, testing the app's food folklore against ten years of Korean search and weather data |

How the project got from the first to the second, and every decision along the
way, is written up in [How the project has evolved](#how-the-project-has-evolved)
and in [`DECISIONS.md`](DECISIONS.md).

## Run it

Open `index.html` in a browser. That's it — no build step, no server.

## How it works

The model is a transparent weighted sum, deliberately not machine learning.
There is no usage data yet, and a learned model with no data is just a worse
rules engine that cannot explain itself.

```
score(dish) = Σ wᵢ · fᵢ(context, dish)     each fᵢ returns -1..1
P(dish)     = softmax(score / τ)           sample, don't argmax
why         = the top positive terms, rendered as text
```

Three consequences worth knowing:

- **Sampling, not argmax.** Taking the maximum would mean the same weather
  always returns the same dish, which reads as broken rather than confident.
- **τ is a design control.** It's exposed as a slider — low is safe, high is
  adventurous.
- **The explanation is free.** The reason chips are the top contributing
  terms, so they are real feature attribution rather than copy written to
  sound intelligent.

Terms resting on cultural heuristics rather than established fact — rain,
fine dust, payday, season — are flagged `folklore: true` in the code. Those
are exactly the ones worth testing against real decisions later.

> **Update:** "later" turned out to be possible before any users existed.
> The [data pipeline](pipeline/) tests these folklore terms against national
> search behaviour — see [First findings](#first-findings).

## Files

| File | What's in it |
|---|---|
| `index.html` | Screen markup for the whole flow |
| `momuk.css` | Design tokens and components |
| `momuk-app.js` | Flow controller: screens, inputs, weather, rendering |
| `momuk-data.js` | 126 hand-tagged dishes |
| `momuk-engine.js` | Context builder, scoring terms, sampling, explanations |
| `momuk-data.csv` | The same dishes, for editing in a spreadsheet |
| `tools/sync-data.js` | Round-trips the dataset between the two |
| `pipeline/` | Data collection scripts and Databricks notebooks — see its [README](pipeline/README.md) |
| `DECISIONS.md` | Decision log: what was chosen, what was rejected, and why |

## The flow

Landing → how many people → how hungry → price range → a brief thinking
beat → one dish with its reasons. Weather and location load quietly in the
background while the questions are being answered, so nothing ever waits on
the network.

The bowl is a single element for the whole flow. It travels from the centre
of the landing screen to the foot of the question screens, and fills as
answers come in — a progress indicator that never looks like one. At the
answer it steams.

Design tokens live in `momuk.css` under `:root`, named to match the Figma
variables so the two stay legible against each other.

Add `?debug=1` to the URL for the score breakdown: the ranked shortlist and
the term-by-term contributions behind the pick.

## Data

`momuk-data.js` holds 126 dishes across 한식 · 중식 · 일식 · 양식 · 분식 ·
아시안. Each carries serve temperature, soup level, spice, heaviness, price
band, speed, solo/share suitability, a ubiquity rating and tags
(해장 · 야식 · 보양 · 비오는날 · 미세먼지 · 다이어트 …).

`ubiquity` — how findable a dish is near anywhere — stands in for a nearby
places API. Biasing toward common dishes covers the "suggested something with
nowhere to get it" risk without needing an integration.

### Editing the dishes

`momuk-data.csv` is the comfortable place to work — open it in Excel, Numbers
or Google Sheets, sort and filter, then convert back:

```bash
node tools/sync-data.js to-js     # csv -> js, validates before writing
node tools/sync-data.js to-csv    # js  -> csv, if you edited the js instead
```

`to-js` refuses to write if anything is off — an unknown `temp` value, a
number out of range, a duplicate id, a stray comma — and lists every problem
with its row number. Tags are separated by `|`, not commas, so they survive
the CSV. Adding a dish means adding a row; nothing else needs to change.

**This data is hand-written and unvalidated.** It came from general knowledge
of Korean food, not from any database or API. The numeric fields are judgment
calls, and `price` is the least reliable of them — bands are estimates and
vary by neighbourhood. Since budget is a hard filter, a wrong band silently
removes a dish from consideration. Corrections welcome.

The tags are now being checked against data: the pipeline measures, for every
dish, how much interest rises on rainy days and weekends, and compares that
with the hand-written tags. The pipeline keeps its own extended copy of the
catalog (`pipeline/momuk-data.csv`, with meal-time columns and validated search
keywords), so the app's 14-column file and `sync-data.js` are unaffected.

## Weather

[Open-Meteo](https://open-meteo.com) for temperature, apparent temperature,
precipitation and humidity; its air-quality endpoint for PM2.5. Both are free,
keyless and CORS-enabled, so they're called directly from the browser — which
is why this needs no server. Free tier is non-commercial.

Location comes from the browser's geolocation API. When it's denied or
unavailable, the page falls back to manually entered context rather than
failing.

## Deploy

Static files, so anything works. GitHub Pages: enable it on the default
branch in Settings → Pages.

## How the project has evolved

**v1 — a rules engine, on purpose (Aug 2026).** With no usage data, a learned
model would have been a worse rules engine that couldn't explain itself. So
the app shipped as a hand-weighted sum, with the culturally-based terms
flagged as folklore and a plan to test them once ~200 user decisions had been
logged.

**The shift — don't wait for users to test the folklore (Oct 2026).** Waiting
for 200 logged decisions meant the core question ("does rain really make
people want 전?") would stay open for months. Public data could answer a
population-level version of it now. That turned the project from a front-end
build into a data project, and a chance to learn the industry stack properly:
PySpark, Databricks, cloud data, and a real cleaning problem. The constraints
set at that point were: **$0 budget**, data that represents **Korean** users,
and the three skills to focus on first — **forecasting, causal inference and
experimentation design**.

**Finding data, and what changed because of it.**

| Plan | What happened | Decision |
|---|---|---|
| Delivery order counts (KT telecom data) | Not reachable from the US, and now sold as paid data | Dropped |
| Individual users' order history | Not public anywhere in Korea | Use population data now; personal data comes from the app later |
| **Naver search trends** as the demand signal | Free, national, daily since 2016 | Adopted — searches measure *craving*, which suits a "what do I feel like" app |
| Region from Naver | Naver has no regional split | Added **Google Trends by province** as a second, regional layer |
| City-level search data | Checked: province is the smallest unit Google offers for Korea | Province for analysis; city-level only via the user's live weather in the app |
| Weather | Open-Meteo historical (ERA5 reanalysis), keyless | Adopted, all 17 provinces, 9 daily variables |

**Data problems that changed the method.**

- Naver scales every request to its own peak, so numbers from different
  requests can't be compared. Solved with an **anchor dish** (김치찌개) in
  every request and rescaling every batch onto its scale. A tournament-style
  alternative was considered and rejected: it finds winners but loses the
  numbers for every other dish.
- The first data-quality check showed 후라이드치킨 with almost no interest —
  not because nobody eats it, but because nobody *searches that exact phrase*.
  That led to **keyword entity resolution**: 202 candidate spellings and
  synonyms, kept only if they are spelled like the dish (jamo-level edit
  distance) *and* searched like it (correlation of week-to-week changes).
- Open-Meteo's hourly limit silently lost downloaded provinces, and an
  out-of-date script sent pipe-joined keywords to Google for 7 dishes. Both are
  fixed (resumable, per-province caching; one keyword per Google lookup) and
  logged in [`DECISIONS.md`](DECISIONS.md).

**Personalization, rethought.** Population data alone would give everyone in
the same place and weather the same answer. The design now layers personal
signals on top of the population prior: time of day and weekday, an optional
"5 dishes you love / dishes you never want" onboarding, a recency penalty, and
feedback-driven learning once there are users.

## First findings

First pass on ten years of daily data (2016-01-01 → 2026-10-24), *before* the
keyword fix and data cleaning — to be re-checked.

**Rain.** Comparing rainy and dry days within the same month and weekday, the
five most rain-sensitive dishes were all ones hand-tagged 비오는날:

| Dish | Interest on rainy vs comparable dry days |
|---|---|
| 김치전 | ×1.79 |
| 해물파전 | ×1.74 |
| 수제비 | ×1.34 |
| 칼국수 | ×1.25 |
| 바지락칼국수 | ×1.19 |

The data also found rain-sensitive dishes the tags missed: hot, spicy soups
like 짬뽕, 마라탕 and 부대찌개.

**Weekends.** Two stories the tags didn't predict: hangover food rises
(콩나물국밥 ×1.59, 감자탕, 돼지국밥), and so do day-trip foods — 매운탕 ×1.67,
막국수 ×1.65, 바지락칼국수 ×1.64 — dishes people tend to eat on an outing.

## Roadmap

- **Now:** data cleaning, with each choice recorded in `DECISIONS.md` (dish
  launch dates, viral spikes, coarse low-volume series, holidays, a better
  "rainy day" definition)
- Forecasting daily interest from the weather forecast, then causal estimates
  of weather effects — and feed the estimated effects back into the app's
  hand-set weights
- Restaurant suggestions, as one outbound map link from the accepted state —
  a handoff, not an in-app list
- Log `{context, dish shown, accepted/rejected, reason}` to a lightweight
  endpoint; the data can't be backfilled, so this should land early
- A/B test: population-only recommendations vs personalized ones, measured by
  how often a suggestion is accepted
