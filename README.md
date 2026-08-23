# momuk

**오늘 뭐 먹지** — a menu suggester that answers *what* to eat, not *where*.

It reads the weather, the air quality, the hour and the day, asks you two
things (how hungry, what budget), and returns one dish with a visible reason.
No accounts, no server, no API keys.

Current state: **working logic prototype.** The interface is deliberately
unstyled — visual design is being done separately in Figma.

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

## Files

| File | What's in it |
|---|---|
| `index.html` | The prototype: inputs, weather fetch, result, score breakdown |
| `momuk-data.js` | 126 hand-tagged dishes |
| `momuk-engine.js` | Context builder, scoring terms, sampling, explanations |
| `momuk-data.csv` | The same dishes, for editing in a spreadsheet |
| `tools/sync-data.js` | Round-trips the dataset between the two |

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

## Roadmap

- Restaurant suggestions, as one outbound map link from the accepted state —
  a handoff, not an in-app list
- Log `{context, dish shown, accepted/rejected, reason}` to a lightweight
  endpoint; the data can't be backfilled, so this should land early
- Once ~200 decisions are logged, fit the weights against them and compare
  to the hand-set ones — which folk rules actually held?
