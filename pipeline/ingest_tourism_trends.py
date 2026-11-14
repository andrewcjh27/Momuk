"""
momuk — locals or visitors? A tourist-season test for regional dishes (run on your laptop)

Question
  A province's regional lean (e.g. 닭갈비 ×3.5 in Gangwon) counts every search made IN the
  province — locals and visitors alike. Is the lean driven by visitors?

Test
  For each regional dish, pull 5 years of weekly Google Trends interest twice:
    - in its home province (e.g. 닭갈비 in KR-42 Gangwon)
    - in all of Korea (닭갈비 in KR)
  Their ratio, province ÷ national, is the province's share of attention to the dish.
  Dividing by the national series removes the dish's own season (막국수 rises every
  summer everywhere) and national hype.

  If visitors drive the lean, the share should RISE in travel weeks — summer vacation
  (휴가철, July 25 - August 15) and the 설날 / 추석 holidays — and stay lower the rest of
  the year. A steady share suggests locals.

    visitor_ratio = average share in travel weeks ÷ average share in other weeks
                    (geometric means of the weekly ratios; 95% bootstrap interval)

  Controls: 김치찌개 in the same tourist provinces. An everyday dish should show no
  visitor pattern; if it does, the effect is tourism in general, not the dish.

  Uses each dish's plain name (닭갈비), never place-named keywords (나주곰탕), so the
  test can't be circular.

  Limits: weekly data can't show weekends; "travel weeks" also contain locals' own
  holiday eating (설날 food), so read holiday-heavy results with care.

Setup    pip3 install trendspyg pandas numpy  (Google Chrome must be installed)
Run      python3 ingest_tourism_trends.py --test      # one lookup: check KR-42 works
         caffeinate -i python3 ingest_tourism_trends.py   # ~25 lookups, resumable
         python3 ingest_tourism_trends.py --analyze   # results only, from saved data
Outputs  raw/tourism_json/<dish>__<geo>.json   untouched responses
         raw/tourism_trends_raw.csv            dish_id, geo, keyword, date, value
         reports/visitor_signature.csv         one row per (dish, province)
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
JSON_DIR = RAW / "tourism_json"
REPORTS = ROOT / "reports"
for d in (JSON_DIR, REPORTS):
    d.mkdir(parents=True, exist_ok=True)

MENU_CSV = ROOT / "momuk-data.csv"
CALENDAR_CSV = ROOT / "calendar_kr.csv"
TIMEFRAME = "today 5-y"
WAIT_SECONDS = (60, 120)

# (dish_id, home province) — the strongest regional leans from notebook 02
PAIRS = [
    ("makguksu", "KR-42"), ("dakgalbi", "KR-42"),                 # Gangwon
    ("milmyeon", "KR-26"), ("dwaeji-gukbap", "KR-26"),            # Busan
    ("daegutang", "KR-26"), ("eomuk", "KR-26"),
    ("gomtang", "KR-46"),                                         # Jeollanam-do
    ("kongnamul-gukbap", "KR-45"),                                # Jeollabuk-do
    ("jjimdak", "KR-47"),                                         # Gyeongsangbuk-do
    ("kalguksu", "KR-30"),                                        # Daejeon
    ("pyeongyang-naengmyeon", "KR-11"),                           # Seoul
]
CONTROLS = [("kimchi-jjigae", "KR-42"), ("kimchi-jjigae", "KR-26")]

SUMMER = ((7, 25), (8, 15))


# ---------------------------------------------------------------- fetching
def fetch(keyword: str, geo: str) -> list[dict]:
    from trendspyg import download_google_trends_explore
    from ingest_google_trends import call_supported
    env = call_supported(download_google_trends_explore, keyword, geo=geo, timeframe=TIMEFRAME,
                         engine="auto", cache="disk", cookies="disk")
    return env.get("interest_over_time", []) or []


def rows_to_frame(rows: list[dict], keyword: str) -> pd.DataFrame:
    out = []
    for r in rows:
        value = r.get("value", r.get(keyword))
        if value is None or r.get("is_partial"):
            continue
        date = pd.to_datetime(r["date"], utc=True).tz_convert(None).normalize()
        out.append({"date": date, "value": float(value)})
    return pd.DataFrame(out)


def lookups() -> list[tuple[str, str]]:
    pairs = PAIRS + CONTROLS
    return pairs + sorted({(d, "KR") for d, _ in pairs})


def run_test() -> None:
    print("Test: 닭갈비 over time in Gangwon (KR-42) ...")
    rows = fetch("닭갈비", "KR-42")
    if not rows:
        sys.exit("No time series came back. Tell Claude — province time series may not be supported.")
    print("Fields in each row:", sorted(rows[0].keys()))
    for r in rows[:3] + rows[-3:]:
        print(" ", r)
    print(f"\nLooks good: {len(rows)} weekly points. Run without --test for all lookups.")


def run_fetch(menu: pd.DataFrame) -> None:
    from ingest_google_trends import is_rate_limit
    name = dict(zip(menu["id"], menu["ko"]))
    todo = [(d, g) for d, g in lookups() if not (JSON_DIR / f"{d}__{g}.json").exists()]
    print(f"{len(lookups()) - len(todo)} lookups saved, {len(todo)} to go.")
    for i, (dish_id, geo) in enumerate(todo, 1):
        kw = name[dish_id]
        try:
            rows = fetch(kw, geo)
        except Exception as err:  # noqa: BLE001
            if is_rate_limit(err):
                print(f"\nGoogle rate limit after {i - 1} new lookups. Wait ~40 minutes and rerun.")
                return
            print(f"  ! {dish_id} {geo} failed: {err}")
            continue
        (JSON_DIR / f"{dish_id}__{geo}.json").write_text(
            json.dumps({"dish_id": dish_id, "geo": geo, "keyword": kw, "timeframe": TIMEFRAME,
                        "interest_over_time": rows}, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"[{i}/{len(todo)}] {kw} in {geo}: {len(rows)} weeks")
        if i < len(todo):
            time.sleep(random.uniform(*WAIT_SECONDS))


# ---------------------------------------------------------------- analysis
def travel_weeks(dates: pd.Series, holidays: pd.Series) -> pd.Series:
    """A week (Google labels weeks by their first day) is a travel week if any of its
    7 days falls in summer vacation or on a 설날 / 추석 day."""
    hol = set(holidays)

    def is_travel(start):
        for k in range(7):
            d = start + pd.Timedelta(days=k)
            if (d.month, d.day) >= SUMMER[0] and (d.month, d.day) <= SUMMER[1]:
                return True
            if d in hol:
                return True
        return False

    return dates.map(is_travel)


def visitor_ratio(log_share: np.ndarray, travel: np.ndarray, n_boot: int = 2000, seed: int = 0):
    rng = np.random.default_rng(seed)
    a, b = log_share[travel], log_share[~travel]
    point = float(np.exp(a.mean() - b.mean()))
    boots = [np.exp(rng.choice(a, len(a)).mean() - rng.choice(b, len(b)).mean()) for _ in range(n_boot)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return point, float(lo), float(hi)


def analyze(menu: pd.DataFrame) -> pd.DataFrame:
    cal = pd.read_csv(CALENDAR_CSV)
    holidays = pd.to_datetime(cal[cal["event"].isin(["seollal", "chuseok"])]["date"])
    name = dict(zip(menu["id"], menu["ko"]))

    frames, results = [], []
    for dish_id, geo in lookups():
        path = JSON_DIR / f"{dish_id}__{geo}.json"
        if path.exists():
            saved = json.loads(path.read_text(encoding="utf-8"))
            f = rows_to_frame(saved["interest_over_time"], saved["keyword"]).assign(
                dish_id=dish_id, geo=geo, keyword=saved["keyword"])
            frames.append(f)
    if not frames:
        sys.exit("No saved lookups yet — run the fetch first.")
    data = pd.concat(frames, ignore_index=True)
    data.to_csv(RAW / "tourism_trends_raw.csv", index=False, encoding="utf-8")

    for dish_id, geo in PAIRS + CONTROLS:
        reg = data[(data.dish_id == dish_id) & (data.geo == geo)][["date", "value"]]
        nat = data[(data.dish_id == dish_id) & (data.geo == "KR")][["date", "value"]]
        if reg.empty or nat.empty:
            continue
        m = reg.merge(nat, on="date", suffixes=("_prov", "_nat"))
        zero_weeks = int(((m.value_prov == 0) | (m.value_nat == 0)).sum())
        m = m[(m.value_prov > 0) & (m.value_nat > 0)].copy()
        if len(m) < 52:
            continue
        m["log_share"] = np.log(m.value_prov / m.value_nat)
        m["travel"] = travel_weeks(m.date, holidays)
        point, lo, hi = visitor_ratio(m.log_share.to_numpy(), m.travel.to_numpy())
        if lo > 1.1:
            verdict = "visitor pattern"
        elif hi < 1.0 or (lo > 0.9 and hi < 1.1):
            verdict = "steady (local)"
        else:
            verdict = "unclear"
        results.append({"dish": name[dish_id], "dish_id": dish_id, "province": geo,
                        "control": (dish_id, geo) in CONTROLS,
                        "visitor_ratio": round(point, 3), "ci_low": round(lo, 3), "ci_high": round(hi, 3),
                        "travel_weeks": int(m.travel.sum()), "other_weeks": int((~m.travel).sum()),
                        "zero_weeks_dropped": zero_weeks, "verdict": verdict})

    res = pd.DataFrame(results).sort_values(["control", "visitor_ratio"], ascending=[True, False])
    res.to_csv(REPORTS / "visitor_signature.csv", index=False, encoding="utf-8")
    print(res.drop(columns="dish_id").to_string(index=False))
    print(f"\nSaved {REPORTS / 'visitor_signature.csv'}")
    print("visitor_ratio 1.3 = the province's share of attention is 30% higher in travel weeks.")
    return res


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--test", action="store_true", help="one lookup to check province time series work")
    p.add_argument("--analyze", action="store_true", help="skip fetching; analyze saved data")
    args = p.parse_args()
    menu = pd.read_csv(MENU_CSV)
    if args.test:
        run_test()
    else:
        if not args.analyze:
            run_fetch(menu)
        analyze(menu)
