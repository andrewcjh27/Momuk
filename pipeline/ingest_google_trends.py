"""
momuk — Google Trends regional profiles (run on your laptop)

Role in the project
  Naver  = WHEN  : national, daily interest -> how cravings react to weather/time
  Google = WHERE : interest by province     -> which regions over-index on which dishes

What it does
  For each dish in momuk-data.csv, asks Google Trends "how does interest in this
  dish compare across Korean provinces?" over the last 5 years. Google already
  divides by each region's total searches, so a high value means people in that
  province search this dish MORE THAN USUAL for them — a preference, not just
  "Gyeonggi is big".

Google rate-limits hard (roughly 8-10 lookups per 15 minutes), so this script:
  - waits 1-2 minutes between dishes (full run is a few hours — run it overnight)
  - saves each dish as soon as it arrives and SKIPS saved dishes on the next run,
    so if it stops on a rate limit you just rerun it later and it resumes

Setup
  pip install trendspyg pandas        (Google Chrome must be installed)

Run
  python ingest_google_trends.py --test   # one dish; check Korean provinces come back
  python ingest_google_trends.py          # every dish (resumable)

Output
  raw/google_json/<dish_id>.json     untouched responses
  raw/google_region_raw.csv          dish_id, keyword, geo_code, geo_name, value
"""

import argparse
import inspect
import json
import random
import sys
import time
from pathlib import Path

import pandas as pd
from trendspyg import download_google_trends_explore

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
OUT_DIR = RAW / "google_json"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MENU_CSV = ROOT / "momuk-data.csv"
GEO = "KR"
TIMEFRAME = "today 5-y"
WAIT_SECONDS = (60, 120)   # random pause between dishes, to stay under Google's limit


def call_supported(fn, *args, **kwargs):
    """Pass only the keyword arguments this version of trendspyg accepts."""
    params = inspect.signature(fn).parameters
    if any(p.kind == p.VAR_KEYWORD for p in params.values()):
        return fn(*args, **kwargs)
    return fn(*args, **{k: v for k, v in kwargs.items() if k in params})


def is_rate_limit(err: Exception) -> bool:
    return "ratelimit" in type(err).__name__.lower() or "429" in str(err)


def fetch_dish(keyword: str) -> dict:
    return call_supported(
        download_google_trends_explore, keyword,
        geo=GEO, timeframe=TIMEFRAME,
        engine="auto", cache="disk", cookies="disk",
    )


def load_menu() -> pd.DataFrame:
    """Google takes one term per lookup, so use each dish's TOP keyword: the first
    entry of search_keyword ('돈까스|돈카츠|돈가스' -> '돈까스'), which
    validate_keywords.py orders most-searched first. Falls back to the dish name."""
    menu = pd.read_csv(MENU_CSV)
    if "search_keyword" in menu.columns:
        kw = menu["search_keyword"].fillna(menu["ko"])
    else:
        kw = menu["ko"]
    menu["kw"] = kw.astype(str).str.split("|").str[0].str.strip()
    return menu


def saved_keyword(dish_id: str):
    path = OUT_DIR / f"{dish_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("keyword")


def to_rows(dish_id: str, keyword: str, env: dict) -> list[dict]:
    return [{
        "dish_id": dish_id,
        "keyword": keyword,
        "geo_code": r.get("geo_code"),
        "geo_name": r.get("geo_name"),
        "value": r.get("value"),
    } for r in env.get("interest_by_region", []) or []]


def run_test() -> None:
    print("Test lookup: 냉면 by Korean province ...")
    env = fetch_dish("냉면")
    rows = to_rows("mul-naengmyeon", "냉면", env)
    if not rows:
        sys.exit("No regional rows came back. Tell Claude — the library may not support KR provinces.")
    for r in sorted(rows, key=lambda r: -(r["value"] or 0)):
        print(f"  {r['geo_code']:<8} {r['geo_name']:<25} {r['value']}")
    if not all(str(r["geo_code"]).startswith("KR-") for r in rows):
        print("\nWarning: some codes aren't Korean provinces (KR-xx). Tell Claude what you see.")
    else:
        print(f"\nLooks good: {len(rows)} Korean regions. Run without --test for all dishes.")


def run_all() -> None:
    menu = load_menu()
    # Fetch dishes never saved, plus dishes saved under a different keyword
    # (e.g. 돈카츠 before keyword validation picked 돈까스) so Google matches Naver.
    todo = [(d, k) for d, k in zip(menu["id"], menu["kw"]) if saved_keyword(d) != k]
    changed = sum(1 for d, _ in todo if saved_keyword(d) is not None)
    print(f"{len(menu) - len(todo)} dishes up to date, {len(todo)} to go "
          f"({changed} re-fetched because their keyword changed).")

    for i, (dish_id, kw) in enumerate(todo, 1):
        try:
            env = fetch_dish(kw)
        except Exception as err:  # noqa: BLE001 — we decide below whether to stop
            if is_rate_limit(err):
                print(f"\nGoogle rate limit hit after {i - 1} new dishes. "
                      "Wait ~40 minutes, then rerun — it resumes where it stopped.")
                break
            print(f"  ! {dish_id} ({kw}) failed: {err} — skipping for now")
            continue

        (OUT_DIR / f"{dish_id}.json").write_text(
            json.dumps({"dish_id": dish_id, "keyword": kw, "geo": GEO,
                        "timeframe": TIMEFRAME, "response": env},
                       ensure_ascii=False, indent=1, default=str),
            encoding="utf-8")
        print(f"[{i}/{len(todo)}] saved {dish_id} ({kw}): "
              f"{len(env.get('interest_by_region', []) or [])} regions")
        if i < len(todo):
            time.sleep(random.uniform(*WAIT_SECONDS))

    # Rebuild the combined CSV from dishes saved under their CURRENT keyword
    rows, done = [], 0
    for d, k in zip(menu["id"], menu["kw"]):
        if saved_keyword(d) != k:
            continue
        saved = json.loads((OUT_DIR / f"{d}.json").read_text(encoding="utf-8"))
        rows += to_rows(saved["dish_id"], saved["keyword"], saved["response"])
        done += 1
    pd.DataFrame(rows).to_csv(RAW / "google_region_raw.csv", index=False, encoding="utf-8")
    print(f"\nWrote raw/google_region_raw.csv — {done}/{len(menu)} dishes up to date.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="look up one dish only")
    args = parser.parse_args()
    run_test() if args.test else run_all()
