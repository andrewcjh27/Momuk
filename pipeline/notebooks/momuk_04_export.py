# Databricks notebook source
# MAGIC %md
# MAGIC # momuk — 04: export the model for the website
# MAGIC
# MAGIC Runs last in the weekly job, after the checks pass. Collects everything the website's recommender
# MAGIC needs into one small JSON file, `data/momuk-model.json`:
# MAGIC
# MAGIC | Per dish | From |
# MAGIC |---|---|
# MAGIC | catalog: names, price, heaviness, spice, soup, speed, how common (ubiq), novel, late-night delivery, base (rice/noodle/bread/meat/other), solo/share, tags, meal-time fit | `bronze_menu` |
# MAGIC | popularity — mean interest over the last 2 years of data | `silver_dish_interest` |
# MAGIC | rain lift (clipped 0.5–2) | `gold_dish_day`, same method as notebook 01 |
# MAGIC | temperature boost per 5 °C bin | `gold_temp_boost` |
# MAGIC | weekend lift | `gold_weekend_lift` |
# MAGIC | food-day lifts (clipped for scoring, raw for display) | `gold_event_lift` |
# MAGIC | regional lean per province | `silver_region_lean` |
# MAGIC
# MAGIC plus the food-day calendar for the next two years and the 17 province points.
# MAGIC
# MAGIC The file is saved to the volume and, if the secret `momuk/github_token` exists, committed to
# MAGIC GitHub, where GitHub Pages serves it to the website. The website never talks to Databricks.

# COMMAND ----------

import base64
import datetime as dt
import json
import math
import os

import requests
from pyspark.sql import functions as F

CATALOG, SCHEMA = "workspace", "momuk"
spark.sql(f"USE {CATALOG}.{SCHEMA}")
VOL = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
OUT = f"{VOL}/export/momuk-model.json"

REPO, BRANCH, REPO_PATH = "andrewcjh27/Momuk", "main", "data/momuk-model.json"
POPULARITY_DAYS = 730
TEMP_BIN = 5                     # must match notebook 02
RAIN_CLIP = (0.5, 2.0)

PROVINCES = [   # same points as the weather download; ko/en names for the website
    ("KR-11", "서울", "Seoul", 37.5665, 126.9780), ("KR-26", "부산", "Busan", 35.1796, 129.0756),
    ("KR-27", "대구", "Daegu", 35.8714, 128.6014), ("KR-28", "인천", "Incheon", 37.4563, 126.7052),
    ("KR-29", "광주", "Gwangju", 35.1595, 126.8526), ("KR-30", "대전", "Daejeon", 36.3504, 127.3845),
    ("KR-31", "울산", "Ulsan", 35.5384, 129.3114), ("KR-50", "세종", "Sejong", 36.4800, 127.2890),
    ("KR-41", "경기", "Gyeonggi", 37.2636, 127.0286), ("KR-42", "강원", "Gangwon", 37.3422, 127.9202),
    ("KR-43", "충북", "Chungbuk", 36.6424, 127.4890), ("KR-44", "충남", "Chungnam", 36.8151, 127.1139),
    ("KR-45", "전북", "Jeonbuk", 35.8242, 127.1480), ("KR-46", "전남", "Jeonnam", 34.9507, 127.4872),
    ("KR-47", "경북", "Gyeongbuk", 36.0190, 129.3435), ("KR-48", "경남", "Gyeongnam", 35.2280, 128.6811),
    ("KR-49", "제주", "Jeju", 33.4996, 126.5312),
]
EVENT_EN = {
    "seollal": "Seollal", "chuseok": "Chuseok", "boknal": "Boknal", "dongji": "Winter solstice",
    "christmas": "Christmas", "suneung": "Suneung exam day", "samgyeopsal_day": "Samgyeopsal Day",
    "black_day": "Black Day",
}

def r3(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 3)

# COMMAND ----------

# MAGIC %md ## Gather

# COMMAND ----------

menu = spark.table("bronze_menu").toPandas()
last = spark.table("silver_dish_interest").agg(F.max("date")).first()[0]

popularity = {r.dish_id: r.p for r in spark.table("silver_dish_interest")
              .filter(F.col("date") > F.lit(last - dt.timedelta(days=POPULARITY_DAYS)))
              .groupBy("dish_id").agg(F.avg("interest").alias("p")).collect()}

# rain lift: rainy vs dry days within the same month x weekday (notebook 01's method), saved for reuse
g = spark.table("gold_dish_day")
cell = g.groupBy("dish_id", "month", "dow", "is_rainy").agg(F.avg("interest").alias("m"))
rain_lift = (cell.groupBy("dish_id", "month", "dow").pivot("is_rainy", [0, 1]).agg(F.first("m"))
             .withColumnRenamed("0", "dry").withColumnRenamed("1", "rainy")
             .filter((F.col("dry") > 0) & F.col("rainy").isNotNull())
             .withColumn("ratio", F.col("rainy") / F.col("dry"))
             .groupBy("dish_id").agg(F.expr("percentile_approx(ratio, 0.5)").alias("rain_lift"))
             .withColumn("rain_lift", F.greatest(F.lit(RAIN_CLIP[0]), F.least(F.lit(RAIN_CLIP[1]), "rain_lift"))))
rain_lift.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("gold_rain_lift")
rain = {r.dish_id: r.rain_lift for r in spark.table("gold_rain_lift").collect()}

temp = {}
for r in spark.table("gold_temp_boost").collect():
    temp.setdefault(r.dish_id, {})[str(int(r.temp_bin))] = r3(r.temp_boost)

weekend = {r.dish_id: r.weekend_lift for r in spark.table("gold_weekend_lift").collect()}

events = {}
for r in spark.table("gold_event_lift").collect():
    events.setdefault(r.dish_id, {})[r.event] = {"lift": r3(r.event_lift), "raw": r3(r.event_lift_raw)}

region = {}
for r in spark.table("silver_region_lean").select("dish_id", "geo_code", "lean_shrunk").collect():
    region.setdefault(r.dish_id, {})[r.geo_code] = r3(r.lean_shrunk)

today = dt.date.today()
calendar = [{"date": r.date.isoformat(), "event": r.event, "label": r.label, "label_en": EVENT_EN.get(r.event, r.event)}
            for r in spark.table("bronze_calendar")
            .filter(F.col("date").between(F.lit(today - dt.timedelta(days=1)), F.lit(today + dt.timedelta(days=730))))
            .orderBy("date").collect()]

# COMMAND ----------

# MAGIC %md ## Build and check

# COMMAND ----------

def num(v, default=0):
    try:
        f = float(v)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default

dishes = []
for _, d in menu.iterrows():
    i = d["id"]
    dishes.append({
        "id": i, "ko": d["ko"], "en": d["en"], "cuisine": d["cuisine"],
        "price": int(num(d["price"], 2)), "heavy": int(num(d["heavy"], 1)),
        "price_cap": int(num(d["price_cap"])) if "price_cap" in d else None,
        "spice": int(num(d["spice"])), "ubiq": int(num(d["ubiq"], 2)), "base": d.get("base") or None,
        "soup": int(num(d["soup"])), "speed": d.get("speed") or None,
        "novel": int(num(d["novel"])) if "novel" in d else None,
        "delivery": int(num(d["delivery"])) if "delivery" in d else None,
        "solo": int(num(d["solo"])), "share": int(num(d["share"])),
        "tags": [t for t in str(d["tags"] or "").split("|") if t and t != "nan"],
        "meal": {k: r3(num(d[f"meal_{c}"])) for k, c in
                 [("morning", "morning"), ("lunch", "lunch"), ("dinner", "dinner"), ("late", "late_night")]},
        "popularity": r3(popularity.get(i)),
        "rain": r3(rain.get(i)), "weekend": r3(weekend.get(i)),
        "temp": temp.get(i, {}), "events": events.get(i, {}), "region": region.get(i, {}),
    })

model = {
    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    "data_through": last.isoformat(),
    "temp_bin": TEMP_BIN,
    "provinces": [{"geo": g_, "ko": ko, "en": en, "lat": la, "lon": lo} for g_, ko, en, la, lo in PROVINCES],
    "calendar": calendar,
    "dishes": dishes,
}

# The website trusts this file, so refuse to publish one that looks wrong.
problems = []
if len(dishes) != len(menu):
    problems.append(f"{len(dishes)} dishes exported, catalog has {len(menu)}")
missing_pop = [d["id"] for d in dishes if not d["popularity"]]
if len(missing_pop) > 0.05 * len(dishes):
    problems.append(f"{len(missing_pop)} dishes without popularity: {missing_pop[:5]}")
for d in dishes:
    vals = [d["rain"], d["weekend"]] + list(d["temp"].values()) + list(d["region"].values()) + \
           [e["lift"] for e in d["events"].values()]
    if any(v is not None and not (0.2 <= v <= 5) for v in vals):
        problems.append(f"{d['id']}: a multiplier outside 0.2–5")
if not calendar:
    problems.append("no food days in the next two years")
assert not problems, "Not exporting: " + "; ".join(problems)

text = json.dumps(model, ensure_ascii=False, separators=(",", ":"))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(text)
print(f"{len(dishes)} dishes, {len(calendar)} upcoming food days, data through {last}, {len(text)/1024:.0f} KB → {OUT}")

# COMMAND ----------

# MAGIC %md ## Publish to GitHub
# MAGIC Needs a fine-grained GitHub token with **Contents: read and write** on the Momuk repo, stored as
# MAGIC `databricks secrets put-secret momuk github_token`. Without it, this step is skipped and the file stays
# MAGIC in the volume.

# COMMAND ----------

try:
    token = dbutils.secrets.get("momuk", "github_token")
except Exception:
    token = None

if not token:
    print("No momuk/github_token secret — skipped publishing. The file is in the volume.")
else:
    api = f"https://api.github.com/repos/{REPO}/contents/{REPO_PATH}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    current = requests.get(api, headers=headers, params={"ref": BRANCH}, timeout=30)
    sha = current.json().get("sha") if current.status_code == 200 else None
    old = base64.b64decode(current.json()["content"]).decode("utf-8") if sha else None
    if old is not None and json.loads(old)["dishes"] == model["dishes"] and json.loads(old)["calendar"] == calendar:
        print("Model unchanged — nothing to publish.")
    else:
        body = {"message": f"Weekly model update: data through {last}",
                "content": base64.b64encode(text.encode("utf-8")).decode("ascii"), "branch": BRANCH}
        if sha:
            body["sha"] = sha
        resp = requests.put(api, headers=headers, json=body, timeout=30)
        assert resp.status_code in (200, 201), f"GitHub {resp.status_code}: {resp.text[:300]}"
        print("Published:", resp.json()["commit"]["html_url"])
