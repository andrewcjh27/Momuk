"""
momuk — data ingestion (run this on your laptop, NOT in Databricks)

Why local? Databricks Free Edition restricts outbound internet to a short list
of trusted domains, so calling Naver / Open-Meteo from a notebook may be blocked.
Pull the data here, then upload the files in ./raw/ to a Databricks volume.

What it does
  1. Naver search-trend interest (daily, 2016 → ~1 week ago) for every dish in
     momuk-data.csv, in batches of 4 dishes + 1 fixed anchor dish per request.
     The anchor lets the Databricks notebook rescale every batch onto ONE scale.
  2. Daily weather for all 17 Korean provinces from Open-Meteo (no key needed):
     temperature, "feels like" temperature, rain, snow, rain hours and wind,
     tagged with Google Trends province codes (KR-11 …) and approximate
     populations, so the notebook can build both province-level weather and a
     population-weighted "national" series.

Setup (once)
  pip install requests pandas
  Create a file called .env next to this script containing:
      NAVER_CLIENT_ID=your_client_id
      NAVER_CLIENT_SECRET=your_client_secret
  Add .env to .gitignore — never commit your keys.

Run
  python ingest_local.py
Output
  raw/naver_trends_raw.csv   (batch, dish_id, keyword, date, ratio)
  raw/naver_json/*.json      (untouched API responses, for reproducibility)
  raw/weather_raw.csv        (city, geo_code, population_m, date, weather columns)
"""

import datetime as dt
import json
import os
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
(RAW / "naver_json").mkdir(parents=True, exist_ok=True)

START = "2016-01-01"
# Open-Meteo's historical archive lags a few days; stop a week back for both sources.
END = (dt.date.today() - dt.timedelta(days=7)).isoformat()

MENU_CSV = ROOT / "momuk-data.csv"
ANCHOR_ID = "kimchi-jjigae"   # stable, mid-popularity dish present in every request
BATCH_SIZE = 4                # 4 dishes + 1 anchor = 5 groups (API max per request)


# ---------------------------------------------------------------- credentials
def load_env(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


load_env()
try:
    CLIENT_ID = os.environ["NAVER_CLIENT_ID"]
    CLIENT_SECRET = os.environ["NAVER_CLIENT_SECRET"]
except KeyError:
    raise SystemExit("Missing NAVER_CLIENT_ID / NAVER_CLIENT_SECRET — see the .env setup at the top.")

NAVER_URL = "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
NAVER_HEADERS = {
    "X-NCP-APIGW-API-KEY-ID": CLIENT_ID,
    "X-NCP-APIGW-API-KEY": CLIENT_SECRET,
    "Content-Type": "application/json",
}


# ---------------------------------------------------------------- Naver trends
def keyword_list(cell) -> list[str]:
    """'돈카츠|돈까스|돈가스' -> ['돈카츠', '돈까스', '돈가스'] (Naver sums a group's keywords)."""
    return [k.strip() for k in str(cell).split("|") if k.strip()]


def naver_request(groups: list[tuple[str, list[str]]], time_unit: str = "date") -> dict:
    """groups = [(group_name, [keyword, ...]), ...] — max 5 groups per request."""
    body = {
        "startDate": START,
        "endDate": END,
        "timeUnit": time_unit,
        "keywordGroups": [{"groupName": g, "keywords": kws} for g, kws in groups],
    }
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    for attempt in range(6):
        resp = requests.post(NAVER_URL, headers=NAVER_HEADERS, data=payload, timeout=60)
        if resp.status_code == 429:          # rate limited — back off and retry
            time.sleep(2 ** attempt)
            continue
        if resp.status_code != 200:
            raise RuntimeError(f"Naver API {resp.status_code}: {resp.text[:500]}")
        return resp.json()
    raise RuntimeError("Naver API kept rate-limiting; try again later.")


def pull_naver() -> pd.DataFrame:
    menu = pd.read_csv(MENU_CSV)
    # search_keyword holds the validated keyword set ("돈카츠|돈까스|돈가스");
    # dishes without one fall back to the Korean dish name.
    if "search_keyword" in menu.columns:
        menu["kw"] = menu["search_keyword"].fillna(menu["ko"]).map(keyword_list)
    else:
        menu["kw"] = menu["ko"].map(keyword_list)

    if ANCHOR_ID not in set(menu["id"]):
        raise SystemExit(f"Anchor dish '{ANCHOR_ID}' not found in {MENU_CSV.name}")
    anchor_kw = menu.loc[menu["id"] == ANCHOR_ID, "kw"].item()
    others = menu[menu["id"] != ANCHOR_ID].reset_index(drop=True)

    rows = []
    n_batches = (len(others) + BATCH_SIZE - 1) // BATCH_SIZE
    for b in range(n_batches):
        chunk = others.iloc[b * BATCH_SIZE:(b + 1) * BATCH_SIZE]
        groups = [(ANCHOR_ID, anchor_kw)] + list(zip(chunk["id"], chunk["kw"]))
        result = naver_request(groups)

        (RAW / "naver_json" / f"batch_{b:03d}.json").write_text(
            json.dumps({"groups": groups, "response": result}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        kw_of = dict(groups)
        for group in result.get("results", []):
            for point in group.get("data", []):
                rows.append({
                    "batch": b,
                    "dish_id": group["title"],
                    "keyword": "|".join(kw_of.get(group["title"], [])),
                    "date": point["period"],
                    "ratio": point["ratio"],
                })
        print(f"Naver batch {b + 1}/{n_batches} done: {[g for g, _ in groups[1:]]}")
        time.sleep(0.3)

    df = pd.DataFrame(rows)
    df.to_csv(RAW / "naver_trends_raw.csv", index=False, encoding="utf-8")
    return df


# ---------------------------------------------------------------- weather
# One weather point per province, using the same codes Google Trends returns
# (KR-11 etc.) so province weather joins directly to province search interest.
# Each province is represented by its largest city. Populations are approximate
# (millions) and used only as weights for the national average.
CITIES = [
    # (name,                      geo_code, lat,     lon,      population_m)
    ("Seoul",                     "KR-11", 37.5665, 126.9780,  9.4),
    ("Busan",                     "KR-26", 35.1796, 129.0756,  3.3),
    ("Daegu",                     "KR-27", 35.8714, 128.6014,  2.4),
    ("Incheon",                   "KR-28", 37.4563, 126.7052,  3.0),
    ("Gwangju",                   "KR-29", 35.1595, 126.8526,  1.4),
    ("Daejeon",                   "KR-30", 36.3504, 127.3845,  1.4),
    ("Ulsan",                     "KR-31", 35.5384, 129.3114,  1.1),
    ("Sejong",                    "KR-50", 36.4800, 127.2890,  0.4),
    ("Gyeonggi-do (Suwon)",       "KR-41", 37.2636, 127.0286, 13.7),
    ("Gangwon-do (Wonju)",        "KR-42", 37.3422, 127.9202,  1.5),
    ("Chungcheongbuk-do (Cheongju)", "KR-43", 36.6424, 127.4890, 1.6),
    ("Chungcheongnam-do (Cheonan)",  "KR-44", 36.8151, 127.1139, 2.1),
    ("Jeollabuk-do (Jeonju)",     "KR-45", 35.8242, 127.1480,  1.75),
    ("Jeollanam-do (Suncheon)",   "KR-46", 34.9507, 127.4872,  1.8),
    ("Gyeongsangbuk-do (Pohang)", "KR-47", 36.0190, 129.3435,  2.55),
    ("Gyeongsangnam-do (Changwon)", "KR-48", 35.2280, 128.6811, 3.25),
    ("Jeju-do (Jeju City)",       "KR-49", 33.4996, 126.5312,  0.67),
]
WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARS = [
    "temperature_2m_mean", "temperature_2m_max", "temperature_2m_min",   # °C
    "apparent_temperature_mean",                                       # "feels like" °C
    "precipitation_sum", "rain_sum", "snowfall_sum",                   # mm / cm
    "precipitation_hours",                                             # hours
    "wind_speed_10m_max",                                              # km/h
]


def pull_weather() -> pd.DataFrame:
    """Downloads one province at a time and saves each immediately to
    raw/weather_cache/, so a rate-limit stop never loses finished provinces.
    Rerun the same command and it skips provinces already saved.
    Returns the combined table once all provinces are done, else None."""
    cache = RAW / "weather_cache"
    cache.mkdir(exist_ok=True)

    for name, geo_code, lat, lon, pop in CITIES:
        path = cache / f"{geo_code}.csv"
        if path.exists():
            print(f"Weather already saved: {name}")
            continue

        params = {
            "latitude": lat, "longitude": lon,
            "start_date": START, "end_date": END,
            "daily": ",".join(DAILY_VARS),
            "timezone": "Asia/Seoul",
        }
        for attempt in range(3):
            resp = requests.get(WEATHER_URL, params=params, timeout=120)
            if resp.status_code == 429 and "inute" in resp.text:   # per-minute limit: short wait
                print(f"  Open-Meteo per-minute limit on {name}; waiting 65 s (attempt {attempt + 1}/3)")
                time.sleep(65)
                continue
            break

        if resp.status_code == 429:
            print(f"\nOpen-Meteo limit reached at {name}: {resp.text[:200]}")
            print("Finished provinces are saved. Wait about an hour (hourly limit), then rerun:\n"
                  "  python3 ingest_local.py --weather-only")
            return None
        if resp.status_code != 200:
            raise RuntimeError(f"Open-Meteo {resp.status_code} for {name}: {resp.text[:300]}")

        df = pd.DataFrame(resp.json()["daily"]).rename(columns={"time": "date"})
        df.insert(0, "city", name)
        df.insert(1, "geo_code", geo_code)
        df.insert(2, "population_m", pop)
        df.to_csv(path, index=False, encoding="utf-8")
        print(f"Weather done: {name}")
        time.sleep(30)   # one 10-year request counts as ~280 calls; ~2 per minute is the ceiling

    out = pd.concat([pd.read_csv(cache / f"{g}.csv") for _, g, *_ in CITIES], ignore_index=True)
    out.to_csv(RAW / "weather_raw.csv", index=False, encoding="utf-8")
    return out


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--weather-only", action="store_true",
                        help="skip Naver (already downloaded) and only pull weather")
    parser.add_argument("--naver-only", action="store_true",
                        help="only re-pull Naver (e.g. after changing search keywords)")
    args = parser.parse_args()

    print(f"Date range: {START} → {END}")
    if args.weather_only:
        print("Skipping Naver (--weather-only).")
    else:
        trends = pull_naver()
        print(f"Naver rows: {len(trends):,}")
    if args.naver_only:
        print(f"\nDone (--naver-only). Re-upload {RAW / 'naver_trends_raw.csv'} to Databricks.")
        raise SystemExit
    weather = pull_weather()
    if weather is not None:
        print(f"Weather rows: {len(weather):,}")
        print(f"\nDone. Upload these to your Databricks volume:\n  {RAW / 'naver_trends_raw.csv'}\n"
              f"  {RAW / 'weather_raw.csv'}\n  {MENU_CSV}")
