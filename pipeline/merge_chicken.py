"""
momuk — merge the three chicken flavours into one dish, 치킨 (decision of 2026-11-18)

Why
  Koreans search 치킨 about 36x more than 후라이드치킨: people decide "치킨" first and
  pick the flavour when ordering. Tracking 후라이드치킨 / 양념치킨 / 간장치킨 separately
  measured only a sliver of real chicken demand, so chicken almost never appeared in
  recommendations (and 크리스마스 → 치킨 came out at only ×1.18).
  A dish should match how people choose, so the three become one.

What it changes (both files are backed up first; running it twice is harmless)
  momuk-data.csv          3 chicken rows -> 1 row "chicken" (치킨), searched as
                          치킨|후라이드치킨|양념치킨|간장치킨. Attributes were identical
                          except spice (0, 2, 0); the merged dish gets spice 1.
  keyword_candidates.csv  chicken candidates regrouped under the new dish, 치킨 as main

The app's own catalog (the 14-column momuk-data.csv in the repo root) is not touched.

Run      python3 merge_chicken.py
Then     python3 ingest_local.py --naver-only
         caffeinate -i python3 ingest_google_trends.py      (fetches 치킨 only)
         upload momuk-data.csv, raw/naver_trends_raw.csv, raw/google_region_raw.csv
         to Databricks and Run all on both notebooks
"""

import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
MENU = ROOT / "momuk-data.csv"
CANDS = ROOT / "keyword_candidates.csv"
OLD = ["fried-chicken", "yangnyeom-chicken", "ganjang-chicken"]
KEYWORDS = "치킨|후라이드치킨|양념치킨|간장치킨"


def merge_menu() -> None:
    menu = pd.read_csv(MENU)
    if "chicken" in set(menu["id"]):
        print("momuk-data.csv: already merged")
        return
    shutil.copy(MENU, ROOT / "momuk-data.before-chicken.csv")
    old = menu[menu["id"].isin(OLD)]
    assert len(old) == 3, f"expected 3 chicken rows, found {len(old)}"

    row = old.iloc[0].copy()
    row["id"], row["ko"], row["en"] = "chicken", "치킨", "Korean fried chicken"
    row["spice"] = 1
    for col in [c for c in menu.columns if c.startswith("meal_")]:
        row[col] = int(old[col].max())          # fits a meal if any flavour did
    if "search_keyword" in menu.columns:
        row["search_keyword"] = KEYWORDS

    first = old.index[0]
    menu = pd.concat([menu.loc[:first - 1], row.to_frame().T, menu.loc[first:]])
    menu = menu[~menu["id"].isin(OLD)].reset_index(drop=True)
    menu.to_csv(MENU, index=False, encoding="utf-8")
    print(f"momuk-data.csv: 3 chicken rows -> 1 ({len(menu)} dishes)")


def merge_candidates() -> None:
    cands = pd.read_csv(CANDS)
    if "chicken" in set(cands["dish_id"]):
        print("keyword_candidates.csv: already merged")
        return
    shutil.copy(CANDS, ROOT / "keyword_candidates.before-chicken.csv")
    new = pd.DataFrame([
        ("chicken", "치킨", "main", 0),
        ("chicken", "후라이드치킨", "synonym", 0),
        ("chicken", "양념치킨", "synonym", 0),
        ("chicken", "간장치킨", "synonym", 0),
        ("chicken", "후라이드", "synonym", 0),
    ], columns=["dish_id", "candidate", "kind", "ambiguous"])
    first = cands.index[cands["dish_id"].isin(OLD)][0]
    cands = pd.concat([cands.loc[:first - 1], new, cands.loc[first:]])
    cands = cands[~cands["dish_id"].isin(OLD)].reset_index(drop=True)
    assert cands.groupby("dish_id").size().max() <= 5, "Naver allows at most 5 keyword groups per request"
    cands.to_csv(CANDS, index=False, encoding="utf-8")
    print("keyword_candidates.csv: chicken candidates regrouped under 치킨")


if __name__ == "__main__":
    merge_menu()
    merge_candidates()
