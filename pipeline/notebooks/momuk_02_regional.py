# Databricks notebook source
# MAGIC %md
# MAGIC # momuk — 02: regional lean + first recommender
# MAGIC
# MAGIC **Run `momuk_01_bronze_silver_gold` first** (this notebook reads its tables), and upload
# MAGIC `google_region_raw.csv` to the same `raw` volume.
# MAGIC
# MAGIC | Layer | Table | What it is |
# MAGIC |---|---|---|
# MAGIC | Bronze | `bronze_google_region` | Google Trends interest by province, as downloaded |
# MAGIC | Silver | `silver_region_lean` | How much each province over/under-indexes on each dish |
# MAGIC | Gold | `gold_region_lean` | Lean + menu attributes, ready for the recommender |
# MAGIC
# MAGIC **What Google's numbers mean.** For one dish, Google divides each province's searches for it by that
# MAGIC province's total searches, then scales so the top province = 100. So values compare provinces *for the
# MAGIC same dish* — Busan's 68 for 냉면 says nothing about Busan's 68 for 피자.
# MAGIC
# MAGIC **Regional lean** = province value ÷ that dish's average across provinces.
# MAGIC `lean = 1.3` → people there search this dish 30% more than the typical province does.

# COMMAND ----------

from pyspark.sql import functions as F, Window as W

CATALOG, SCHEMA = "workspace", "momuk"
spark.sql(f"USE {CATALOG}.{SCHEMA}")
VOL = f"/Volumes/{CATALOG}/{SCHEMA}/raw"

(spark.read.option("header", True).option("inferSchema", True).option("encoding", "UTF-8")
 .csv(f"{VOL}/google_region_raw.csv")
 .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("bronze_google_region"))

print("rows:", spark.table("bronze_google_region").count(),
      "| dishes:", spark.table("bronze_google_region").select("dish_id").distinct().count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver — regional lean, with shrinkage
# MAGIC - **Zeros and missing provinces = unknown**, not "nobody eats it": Google hides provinces with too few
# MAGIC   searches. Treating them as 0 would invent strong negative leans for small provinces.
# MAGIC - **Shrinkage:** a dish seen in only a few provinces gets its lean pulled toward 1 (no adjustment),
# MAGIC   because its numbers are noisy. Same idea as trusting the crowd until you know the individual.
# MAGIC - **Clipping** to 0.67–1.5 (`REGION_CAP`), so region can change a dish's score by at most 50%.

# COMMAND ----------

reg = (spark.table("bronze_google_region")
       .withColumn("value", F.col("value").cast("double"))
       .filter(F.col("geo_code").startswith("KR-") & (F.col("value") > 0)))

by_dish = W.partitionBy("dish_id")
REGION_CAP = 1.5   # decided 2026-11-21; was 2.0, which let region outweigh popularity and weather

lean = (reg
    .withColumn("n_regions", F.count("*").over(by_dish))
    .withColumn("dish_mean", F.avg("value").over(by_dish))
    .withColumn("lean", F.col("value") / F.col("dish_mean"))
    .withColumn("reliability", F.least(F.lit(1.0), F.col("n_regions") / F.lit(16.0)))
    .withColumn("lean_shrunk", F.lit(1.0) + F.col("reliability") * (F.col("lean") - 1))
    .withColumn("lean_shrunk", F.greatest(F.lit(1 / REGION_CAP), F.least(F.lit(REGION_CAP), F.col("lean_shrunk")))))

lean.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("silver_region_lean")

# Data quality: dishes Google only sees in a few provinces (their leans are mostly shrunk away)
display(lean.select("dish_id", "keyword", "n_regions").distinct().orderBy("n_regions"))

# COMMAND ----------

# MAGIC %md ## Gold — lean + menu attributes

# COMMAND ----------

menu = spark.table("bronze_menu").withColumnRenamed("id", "dish_id")
gold_lean = (spark.table("silver_region_lean")
             .join(menu.select("dish_id", "ko", "cuisine", "tags", "solo", "share", "speed"), "dish_id"))
gold_lean.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("gold_region_lean")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Findings 1 — what does each province over-index on?
# MAGIC Top 5 dishes per province by lean (only dishes seen in ≥12 provinces, so the numbers are trustworthy).

# COMMAND ----------

rank = W.partitionBy("geo_code").orderBy(F.desc("lean"))
top_by_region = (spark.table("gold_region_lean")
                 .filter(F.col("n_regions") >= 12)
                 .withColumn("rank", F.row_number().over(rank))
                 .filter(F.col("rank") <= 5)
                 .groupBy("geo_code", "geo_name")
                 .agg(F.concat_ws(", ", F.collect_list(
                     F.concat(F.col("ko"), F.lit(" ("), F.format_number("lean", 2), F.lit(")")))).alias("top_5"))
                 .orderBy("geo_code"))
display(top_by_region)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Findings 2 — do regional food stories show up?
# MAGIC Each row is a hypothesis. A lean well above 1 in the expected province supports it.

# COMMAND ----------

hypotheses = spark.createDataFrame([
    ("milmyeon",              "KR-26", "밀면 is a Busan dish"),
    ("dwaeji-gukbap",         "KR-26", "돼지국밥 is a Busan dish"),
    ("dakgalbi",              "KR-42", "닭갈비 → Chuncheon (Gangwon)"),
    ("makguksu",              "KR-42", "막국수 → Chuncheon (Gangwon)"),
    ("pyeongyang-naengmyeon", "KR-11", "평양냉면 culture centres on Seoul"),
    ("chueotang",             "KR-45", "추어탕 → Namwon (Jeollabuk-do)"),
], ["dish_id", "geo_code", "hypothesis"])

display(hypotheses.join(spark.table("gold_region_lean"), ["dish_id", "geo_code"], "left")
        .select("hypothesis", "ko", "geo_name", "value", "lean", "n_regions")
        .orderBy(F.desc("lean")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Temperature boost — how each dish's interest changes with temperature
# MAGIC Days are grouped into 5 °C bins of national mean temperature (−10 … 30 °C). For each dish:
# MAGIC
# MAGIC `temp_boost = average interest on days in this bin ÷ the dish's overall average interest`
# MAGIC
# MAGIC So `temp_boost = 1.8` at 25–30 °C means the dish gets 80% more interest on such days than usual.
# MAGIC - Bins with fewer than 30 days are treated as unknown (boost 1), so rare extremes can't create noise.
# MAGIC - Clipped to 0.5–2.0.
# MAGIC - This is **predictive, not causal**: temperature and season move together, so the boost captures both
# MAGIC   ("hot days" are also summer). That's what a recommender needs; separating the two is a causal question
# MAGIC   for later. It doesn't double count rain: rain lift is measured within the same month.

# COMMAND ----------

TEMP_BIN = 5
MIN_DAYS = 30

t = (spark.table("gold_dish_day")
     .withColumn("temp_bin", F.greatest(F.lit(-10), F.least(F.lit(30),
                 F.floor(F.col("temperature_2m_mean") / TEMP_BIN) * TEMP_BIN))))
overall = t.groupBy("dish_id").agg(F.avg("interest").alias("overall_interest"))

temp_boost = (t.groupBy("dish_id", "temp_bin")
              .agg(F.avg("interest").alias("bin_interest"), F.count("*").alias("days"))
              .join(overall, "dish_id")
              .filter((F.col("overall_interest") > 0) & (F.col("days") >= MIN_DAYS))
              .withColumn("temp_boost", F.col("bin_interest") / F.col("overall_interest"))
              .withColumn("temp_boost", F.greatest(F.lit(0.5), F.least(F.lit(2.0), F.col("temp_boost")))))
temp_boost.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("gold_temp_boost")

# Sanity check: cold dishes should rise with temperature, hot soups should fall
check = ["mul-naengmyeon", "milmyeon", "kongguksu", "samgyetang", "seolleongtang", "eomuk", "tteokguk", "kalguksu"]
display(spark.table("gold_temp_boost").filter(F.col("dish_id").isin(check))
        .join(menu.select("dish_id", "ko"), "dish_id")
        .groupBy("ko").pivot("temp_bin").agg(F.round(F.first("temp_boost"), 2))
        .orderBy("ko"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Calendar — weekends and Korean food days
# MAGIC **Weekend lift** — same method as notebook 01: weekend vs weekday interest within the same month and
# MAGIC rain state, median across those comparisons.
# MAGIC
# MAGIC **Event lift** — for days like 복날 or 설날, an *event study*: each event day is compared with the
# MAGIC **same weekday 1, 2 and 3 weeks before and after** (skipping baseline days that are themselves events).
# MAGIC Same weekday removes the weekday effect; nearby weeks remove season and temperature. The lift is the
# MAGIC median ratio across all event days 2016-2026. Findings show the **true lift** (`event_lift_raw`);
# MAGIC the score uses a copy clipped to 0.5–3.0, so one food day can't take over a whole list.
# MAGIC
# MAGIC Needs `calendar_kr.csv` (from `build_calendar.py`) in the `raw` volume.

# COMMAND ----------

(spark.read.option("header", True).option("encoding", "UTF-8").csv(f"{VOL}/calendar_kr.csv")
 .withColumn("date", F.to_date("date"))
 .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("bronze_calendar"))
cal = spark.table("bronze_calendar")
g = spark.table("gold_dish_day")

# weekend lift
cw = g.groupBy("dish_id", "month", "is_rainy", "is_weekend").agg(F.avg("interest").alias("m"))
weekend_lift = (cw.groupBy("dish_id", "month", "is_rainy").pivot("is_weekend", [0, 1]).agg(F.first("m"))
                .withColumnRenamed("0", "weekday").withColumnRenamed("1", "weekend")
                .filter((F.col("weekday") > 0) & F.col("weekend").isNotNull())
                .withColumn("ratio", F.col("weekend") / F.col("weekday"))
                .groupBy("dish_id").agg(F.expr("percentile_approx(ratio, 0.5)").alias("weekend_lift"))
                .withColumn("weekend_lift", F.greatest(F.lit(0.5), F.least(F.lit(2.0), F.col("weekend_lift")))))
weekend_lift.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("gold_weekend_lift")

# event lift (event study against the same weekday in surrounding weeks)
occ = cal.select("event", "date").distinct()
special_days = cal.select(F.col("date").alias("base_date")).distinct()
offsets = spark.createDataFrame([(k,) for k in (-21, -14, -7, 7, 14, 21)], ["offset"])
base_days = (occ.crossJoin(offsets)
             .withColumn("base_date", F.expr("date_add(date, CAST(offset AS INT))"))
             .join(special_days, "base_date", "left_anti"))
values = g.select("dish_id", "date", "interest")
baseline = (base_days.join(values.withColumnRenamed("date", "base_date"), "base_date")
            .groupBy("event", "date", "dish_id").agg(F.avg("interest").alias("baseline")))
event_lift = (occ.join(values, "date")
              .join(baseline, ["event", "date", "dish_id"])
              .filter(F.col("baseline") > 0)
              .withColumn("ratio", F.col("interest") / F.col("baseline"))
              .groupBy("dish_id", "event")
              .agg(F.expr("percentile_approx(ratio, 0.5)").alias("event_lift_raw"), F.count("*").alias("event_days"))
              # raw = the true effect, for findings; event_lift = clipped, used only in the score
              .withColumn("event_lift", F.greatest(F.lit(0.5), F.least(F.lit(3.0), F.col("event_lift_raw")))))
# Some food days only make sense for their own dish. 동지 falls just before Christmas, so on that
# day many dishes rise from Christmas-dinner searches; its boost applies to 팥죽 alone.
EVENT_ONLY = {"dongji": ["patjuk"]}
for ev, allowed in EVENT_ONLY.items():
    event_lift = event_lift.filter((F.col("event") != ev) | F.col("dish_id").isin(allowed))
event_lift.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("gold_event_lift")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Findings 3 — do the food days show up?
# MAGIC Each row is a food–date link Koreans know. A lift well above 1 supports it.

# COMMAND ----------

food_days = spark.createDataFrame([
    ("boknal",          "samgyetang",   "복날 → 삼계탕"),
    ("seollal",         "tteokguk",     "설날 → 떡국"),
    ("seollal",         "manduguk",     "설날 → 만둣국"),
    ("dongji",          "patjuk",       "동지 → 팥죽"),
    ("chuseok",         "kimchijeon",   "추석 → 전"),
    ("christmas",       "chicken",      "크리스마스 → 치킨"),
    ("christmas",       "pizza",        "크리스마스 → 피자"),
    ("christmas",       "steak",        "크리스마스 → 스테이크"),
    ("christmas",       "carbonara",    "크리스마스 → 까르보나라"),
    ("christmas",       "rose-pasta",   "크리스마스 → 로제파스타"),
    ("christmas",       "tomato-pasta", "크리스마스 → 토마토파스타"),
    ("christmas",       "aglio-olio",   "크리스마스 → 알리오올리오"),
    ("christmas",       "vongole",      "크리스마스 → 봉골레"),
    ("samgyeopsal_day", "samgyeopsal",  "삼겹살데이 → 삼겹살"),
    ("black_day",       "jjajangmyeon", "블랙데이 → 짜장면"),
], ["event", "dish_id", "link"])
display(food_days.join(spark.table("gold_event_lift"), ["event", "dish_id"], "left")
        .select("link", F.round("event_lift_raw", 2).alias("true_lift"), "event_lift", "event_days")
        .orderBy(F.desc("event_lift_raw")))

# Top 5 dishes for every event — including ones nobody predicted
rank_e = W.partitionBy("event").orderBy(F.desc("event_lift_raw"))
display(spark.table("gold_event_lift").join(menu.select("dish_id", "ko"), "dish_id")
        .withColumn("rank", F.row_number().over(rank_e)).filter(F.col("rank") <= 5)
        .groupBy("event").agg(F.concat_ws(", ", F.collect_list(
            F.concat(F.col("ko"), F.lit(" ("), F.format_number("event_lift_raw", 2), F.lit(")")))).alias("top_5"))
        .orderBy("event"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Recommender v0 — putting the pieces together
# MAGIC ```
# MAGIC score = popularity^0.5 × weather boost × regional lean × time-of-day fit × calendar boost
# MAGIC weather boost  = rain lift (if rainy) × temperature boost
# MAGIC calendar boost = weekend lift (if Sat/Sun) × event lift for every food day on DATE
# MAGIC ```
# MAGIC - **popularity** — national interest over the last 2 years (Naver). The square root dampens it so
# MAGIC   치킨-level dishes don't win every time.
# MAGIC - **weather boost** — each dish's rain lift (from notebook 01's method) when it's rainy, times its
# MAGIC   temperature boost for today's temperature.
# MAGIC - **regional lean** — the shrunk, clipped lean for the user's province (Google).
# MAGIC - **time-of-day fit** — from the catalog's `meal_*` columns, which run from 0 (doesn't fit) to 1 (fits):
# MAGIC   `OFF_MEAL + (1 − OFF_MEAL) × value`, so 1 → 1.0, 0 → `OFF_MEAL` (0.3), and a partial fit such as
# MAGIC   부대찌개 at lunch (0.8) → 0.86. Soft, not a filter: 삼겹살 at lunch is possible, just much less likely.
# MAGIC   Naver data is daily, so this comes from the catalog, not from search data.
# MAGIC - **calendar boost** — weekend lift on Saturdays and Sundays, times the event lift of any food day
# MAGIC   on `DATE` (설날, 추석, 복날, 동지 — 팥죽 only, 크리스마스, 수능, 삼겹살데이, 블랙데이).
# MAGIC - **the 3 questions** filter the menu first: party size, hunger, budget.
# MAGIC
# MAGIC Change the inputs in the next cell and rerun it to see recommendations shift.

# COMMAND ----------

# ---- user inputs (try changing these) ----
GEO = "KR-26"      # province code: KR-11 Seoul, KR-26 Busan, KR-42 Gangwon, ...
DATE = "2026-11-14"  # try 2026-07-15 (초복), 2026-12-24 (크리스마스 이브), 2027-02-07 (설날)
IS_RAINY = True
TEMP_C = 8         # today's mean temperature in °C (8 ≈ a November day; try 28 for midsummer)
HOUR = 19          # local hour, 0-23 (try 12 for lunch, 23 for late night)
OFF_MEAL = 0.3     # score multiplier for dishes that don't fit the current meal
PEOPLE = 1        # 1 = solo; 2+ = sharing dishes
HUNGER = 2         # 1 light, 2 normal, 3 very hungry   (menu `heavy` is 0-3)
MAX_PRICE = 2      # 1 cheap, 2 mid, 3 any              (menu `price` is 1-3)
TOP_N = 10

# popularity: national mean interest over the last ~2 years
recent = spark.table("silver_dish_interest").filter(F.col("date") >= F.date_sub(F.current_date(), 730))
popularity = recent.groupBy("dish_id").agg(F.avg("interest").alias("popularity"))

# rain lift (same method as notebook 01: rainy vs dry within month x weekday)
g = spark.table("gold_dish_day")
cell = g.groupBy("dish_id", "month", "dow", "is_rainy").agg(F.avg("interest").alias("m"))
rain_lift = (cell.groupBy("dish_id", "month", "dow").pivot("is_rainy", [0, 1]).agg(F.first("m"))
             .withColumnRenamed("0", "dry").withColumnRenamed("1", "rainy")
             .filter((F.col("dry") > 0) & F.col("rainy").isNotNull())
             .withColumn("ratio", F.col("rainy") / F.col("dry"))
             .groupBy("dish_id").agg(F.expr("percentile_approx(ratio, 0.5)").alias("rain_lift")))

region = (spark.table("silver_region_lean").filter(F.col("geo_code") == GEO)
          .select("dish_id", F.col("lean_shrunk").alias("regional_lean")))

def meal_period(hour):
    if 5 <= hour <= 10:
        return "meal_morning"
    if 11 <= hour <= 15:
        return "meal_lunch"
    if 16 <= hour <= 20:
        return "meal_dinner"
    return "meal_late_night"     # 21:00-04:59

MEAL_COL = meal_period(HOUR)
print("meal period:", MEAL_COL)

today_bin = max(-10, min(30, (TEMP_C // TEMP_BIN) * TEMP_BIN))
temp_today = (spark.table("gold_temp_boost").filter(F.col("temp_bin") == today_bin)
              .select("dish_id", "temp_boost"))

import datetime as _dt
IS_WEEKEND = _dt.date.fromisoformat(DATE).weekday() >= 5
events_today = [r.event for r in spark.table("bronze_calendar")
                .filter(F.col("date") == F.lit(DATE).cast("date")).select("event").distinct().collect()]
print("weekend:", IS_WEEKEND, "| food days:", events_today or "none")

weekend_today = spark.table("gold_weekend_lift").select(
    "dish_id", (F.col("weekend_lift") if IS_WEEKEND else F.lit(1.0)).alias("weekend_boost"))
event_today = (spark.table("gold_event_lift").filter(F.col("event").isin(events_today or ["-"]))
               .groupBy("dish_id").agg(F.exp(F.sum(F.log("event_lift"))).alias("event_boost")))

hunger_ok = {1: F.col("heavy") <= 1, 2: F.col("heavy").between(1, 2), 3: F.col("heavy") >= 2}[HUNGER]
party_ok = (F.col("solo") == 1) if PEOPLE == 1 else (F.col("share") == 1)

recs = (menu.filter(party_ok & hunger_ok & (F.col("price") <= MAX_PRICE))
        .join(popularity, "dish_id")
        .join(rain_lift, "dish_id", "left")
        .join(region, "dish_id", "left")
        .join(temp_today, "dish_id", "left")
        .join(weekend_today, "dish_id", "left")
        .join(event_today, "dish_id", "left")
        .fillna({"rain_lift": 1.0, "regional_lean": 1.0, "temp_boost": 1.0,
                 "weekend_boost": 1.0, "event_boost": 1.0})
        .withColumn("rain_boost", F.col("rain_lift") if IS_RAINY else F.lit(1.0))
        .withColumn("weather_boost", F.col("rain_boost") * F.col("temp_boost"))
        .withColumn("meal_fit", F.lit(OFF_MEAL) + F.lit(1 - OFF_MEAL) * F.col(MEAL_COL).cast("double"))
        .withColumn("calendar_boost", F.col("weekend_boost") * F.col("event_boost"))
        .withColumn("score", F.sqrt("popularity") * F.col("weather_boost")
                    * F.col("regional_lean") * F.col("meal_fit") * F.col("calendar_boost"))
        .select("ko", "en", "score", "popularity", "rain_boost", "temp_boost", "regional_lean",
                "meal_fit", "weekend_boost", "event_boost", "tags")
        .orderBy(F.desc("score"))
        .limit(TOP_N))

display(recs)
