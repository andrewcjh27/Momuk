# Databricks notebook source
# MAGIC %md
# MAGIC # momuk — 00: weekly data update
# MAGIC
# MAGIC Downloads only what's new since the last run and appends it to two bronze tables. Nothing already
# MAGIC stored is changed, so a bad download can't damage the history. Notebook 01 then rebuilds everything.
# MAGIC
# MAGIC | Source | What this notebook downloads | Stored in |
# MAGIC |---|---|---|
# MAGIC | Naver search trends | Every dish for the last ~4 weeks (overlapping what's already stored) up to 2 days ago. Dishes new to the catalog get their full history from 2016 | `bronze_naver_updates` |
# MAGIC | Open-Meteo archive | All 17 provinces from a week before the latest stored day up to yesterday | `bronze_weather_updates` |
# MAGIC
# MAGIC **Putting new Naver data on the existing scale.** Naver scales every request so its own peak is 100,
# MAGIC so a new 4-week request can't be compared with the 10-year history as it comes. Each request still
# MAGIC contains the anchor dish (김치찌개). On the days where the new request overlaps the stored data, the
# MAGIC anchor's stored values are known, so the request is multiplied by
# MAGIC `factor = stored anchor total on the overlap ÷ new anchor total on the overlap`.
# MAGIC That factor is saved with every row; notebook 01 uses it, and the newest download wins for any day.
# MAGIC
# MAGIC **Needs:** the Databricks secret scope `momuk` (`naver_client_id`, `naver_client_secret`), the
# MAGIC catalog file `momuk-data.csv` in the volume, and at least one earlier run of notebook 01.

# COMMAND ----------

import datetime as dt
import json
import time

import pandas as pd
import requests
from pyspark.sql import functions as F

CATALOG, SCHEMA = "workspace", "momuk"
spark.sql(f"USE {CATALOG}.{SCHEMA}")
VOL = f"/Volumes/{CATALOG}/{SCHEMA}/raw"

ANCHOR_ID = "kimchi-jjigae"   # must match ingest_local.py and notebook 01
BATCH_SIZE = 4                # 4 dishes + the anchor = 5 groups, the API maximum
OVERLAP_DAYS = 28             # days re-downloaded that are already stored, used to find the scale factor
MIN_OVERLAP_DAYS = 14         # refuse to scale a request on fewer overlapping days than this
SETTLE_DAYS = 3               # the newest stored days may still change on Naver's side; don't scale on them
NAVER_LAG_DAYS = 2            # download Naver up to 2 days ago (yesterday can be incomplete)
WEATHER_REFRESH_DAYS = 7      # re-download the last week of weather (the archive fills in late)
HISTORY_START = dt.date(2016, 1, 1)

TODAY = dt.date.today()
PULL_ID = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")   # sorts by time; newest wins

NAVER_URL = "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
NAVER_HEADERS = {
    "X-NCP-APIGW-API-KEY-ID": dbutils.secrets.get("momuk", "naver_client_id"),
    "X-NCP-APIGW-API-KEY": dbutils.secrets.get("momuk", "naver_client_secret"),
    "Content-Type": "application/json",
}
print("pull id:", PULL_ID)

# COMMAND ----------

# MAGIC %md ## What's already stored

# COMMAND ----------

def table_exists(name):
    return spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.{name}")

menu = (spark.read.option("header", True).option("encoding", "UTF-8").csv(f"{VOL}/momuk-data.csv")
        .toPandas())
menu["kw"] = menu["search_keyword"].fillna(menu["ko"]).map(
    lambda cell: [k.strip() for k in str(cell).split("|") if k.strip()])
kw_of = dict(zip(menu["id"], menu["kw"]))
assert ANCHOR_ID in kw_of, f"anchor {ANCHOR_ID} missing from momuk-data.csv"

silver = spark.table("silver_dish_interest")
last_naver = silver.agg(F.max("date")).first()[0]
anchor_scaled = (silver.filter((F.col("dish_id") == ANCHOR_ID) &
                               (F.col("date") <= F.lit(last_naver - dt.timedelta(days=SETTLE_DAYS))))
                 .select("date", "interest").toPandas())
anchor_scaled["date"] = pd.to_datetime(anchor_scaled["date"]).dt.date
anchor_scaled = anchor_scaled.set_index("date")["interest"]

known = spark.table("bronze_naver_trends").select("dish_id")
if table_exists("bronze_naver_updates"):
    known = known.union(spark.table("bronze_naver_updates").select("dish_id"))
known = {r.dish_id for r in known.distinct().collect()}
new_dishes = [d for d in menu["id"] if d not in known]

naver_end = TODAY - dt.timedelta(days=NAVER_LAG_DAYS)
naver_start = last_naver - dt.timedelta(days=OVERLAP_DAYS - 1)
print(f"Naver: stored through {last_naver}; downloading {naver_start} → {naver_end}")
print(f"New dishes (full history from {HISTORY_START}):", new_dishes or "none")

# COMMAND ----------

# MAGIC %md ## Naver

# COMMAND ----------

def naver_request(groups, start, end):
    body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "timeUnit": "date",
            "keywordGroups": [{"groupName": g, "keywords": kws} for g, kws in groups]}
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    for attempt in range(6):
        resp = requests.post(NAVER_URL, headers=NAVER_HEADERS, data=payload, timeout=60)
        if resp.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        if resp.status_code != 200:
            raise RuntimeError(f"Naver API {resp.status_code}: {resp.text[:300]}")
        return resp.json()
    raise RuntimeError("Naver kept rate-limiting; rerun later")


def scale_factor(rows, batch_name):
    """Stored anchor total ÷ new anchor total, over the days both have."""
    a = rows[rows["dish_id"] == ANCHOR_ID].set_index("date")["ratio"]
    both = a.index.intersection(anchor_scaled.index)
    if len(both) < MIN_OVERLAP_DAYS:
        raise RuntimeError(f"{batch_name}: only {len(both)} overlapping days with stored data")
    new_total = a.loc[both].sum()
    if new_total <= 0:
        raise RuntimeError(f"{batch_name}: anchor has no searches on the overlap")
    return anchor_scaled.loc[both].sum() / new_total


def pull(dish_ids, start, end, label):
    out = []
    batches = [dish_ids[i:i + BATCH_SIZE] for i in range(0, len(dish_ids), BATCH_SIZE)]
    for b, chunk in enumerate(batches):
        groups = [(ANCHOR_ID, kw_of[ANCHOR_ID])] + [(d, kw_of[d]) for d in chunk]
        result = naver_request(groups, start, end)
        rows = pd.DataFrame([{"dish_id": grp["title"], "keyword": "|".join(kw_of[grp["title"]]),
                              "date": dt.date.fromisoformat(p["period"]), "ratio": float(p["ratio"])}
                             for grp in result.get("results", []) for p in grp.get("data", [])])
        batch = f"{label}-{b:03d}"
        rows["factor"] = scale_factor(rows, batch)
        rows["batch"] = batch
        out.append(rows)
        time.sleep(0.3)
    print(f"{label}: {len(batches)} requests, {start} → {end}")
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


others = [d for d in menu["id"] if d != ANCHOR_ID]
parts = [pull([d for d in others if d not in new_dishes], naver_start, naver_end, "weekly")]
if new_dishes:
    parts.append(pull([d for d in new_dishes if d != ANCHOR_ID], HISTORY_START, naver_end, "backfill"))
naver_new = pd.concat(parts, ignore_index=True)
naver_new.insert(0, "pull_id", PULL_ID)

(spark.createDataFrame(naver_new[["pull_id", "batch", "dish_id", "keyword", "date", "ratio", "factor"]])
 .write.mode("append").saveAsTable("bronze_naver_updates"))
print(f"bronze_naver_updates: +{len(naver_new):,} rows; scale factors "
      f"{naver_new['factor'].min():.3f}–{naver_new['factor'].max():.3f}")

# COMMAND ----------

# MAGIC %md ## Weather

# COMMAND ----------

CITIES = [   # same points and populations as ingest_local.py
    ("Seoul", "KR-11", 37.5665, 126.9780, 9.4), ("Busan", "KR-26", 35.1796, 129.0756, 3.3),
    ("Daegu", "KR-27", 35.8714, 128.6014, 2.4), ("Incheon", "KR-28", 37.4563, 126.7052, 3.0),
    ("Gwangju", "KR-29", 35.1595, 126.8526, 1.4), ("Daejeon", "KR-30", 36.3504, 127.3845, 1.4),
    ("Ulsan", "KR-31", 35.5384, 129.3114, 1.1), ("Sejong", "KR-50", 36.4800, 127.2890, 0.4),
    ("Gyeonggi-do (Suwon)", "KR-41", 37.2636, 127.0286, 13.7),
    ("Gangwon-do (Wonju)", "KR-42", 37.3422, 127.9202, 1.5),
    ("Chungcheongbuk-do (Cheongju)", "KR-43", 36.6424, 127.4890, 1.6),
    ("Chungcheongnam-do (Cheonan)", "KR-44", 36.8151, 127.1139, 2.1),
    ("Jeollabuk-do (Jeonju)", "KR-45", 35.8242, 127.1480, 1.75),
    ("Jeollanam-do (Suncheon)", "KR-46", 34.9507, 127.4872, 1.8),
    ("Gyeongsangbuk-do (Pohang)", "KR-47", 36.0190, 129.3435, 2.55),
    ("Gyeongsangnam-do (Changwon)", "KR-48", 35.2280, 128.6811, 3.25),
    ("Jeju-do (Jeju City)", "KR-49", 33.4996, 126.5312, 0.67),
]
DAILY_VARS = ["temperature_2m_mean", "temperature_2m_max", "temperature_2m_min", "apparent_temperature_mean",
              "precipitation_sum", "rain_sum", "snowfall_sum", "precipitation_hours", "wind_speed_10m_max"]

stored_w = spark.table("bronze_weather").select(F.to_date("date").alias("date"))
if table_exists("bronze_weather_updates"):
    stored_w = stored_w.union(spark.table("bronze_weather_updates").select(F.to_date("date").alias("date")))
last_weather = stored_w.agg(F.max("date")).first()[0]
w_start = last_weather - dt.timedelta(days=WEATHER_REFRESH_DAYS - 1)
w_end = TODAY - dt.timedelta(days=1)
print(f"Weather: stored through {last_weather}; downloading {w_start} → {w_end}")

frames = []
for name, geo, lat, lon, pop in CITIES:
    resp = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=60, params={
        "latitude": lat, "longitude": lon, "start_date": w_start.isoformat(), "end_date": w_end.isoformat(),
        "daily": ",".join(DAILY_VARS), "timezone": "Asia/Seoul"})
    if resp.status_code != 200:
        raise RuntimeError(f"Open-Meteo {resp.status_code} for {name}: {resp.text[:300]}")
    df = pd.DataFrame(resp.json()["daily"]).rename(columns={"time": "date"})
    df = df.dropna(subset=["temperature_2m_mean"])          # days the archive hasn't filled in yet
    df.insert(0, "city", name); df.insert(1, "geo_code", geo); df.insert(2, "population_m", pop)
    frames.append(df)
    time.sleep(1)

weather_new = pd.concat(frames, ignore_index=True)
weather_new["date"] = pd.to_datetime(weather_new["date"]).dt.date
weather_new[DAILY_VARS + ["population_m"]] = weather_new[DAILY_VARS + ["population_m"]].astype(float)  # same types every week
weather_new.insert(0, "pull_id", PULL_ID)
spark.createDataFrame(weather_new).write.mode("append").saveAsTable("bronze_weather_updates")
print(f"bronze_weather_updates: +{len(weather_new):,} rows, through {weather_new['date'].max()}")
