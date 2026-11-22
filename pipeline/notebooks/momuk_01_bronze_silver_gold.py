# Databricks notebook source
# MAGIC %md
# MAGIC # momuk — 01: bronze → silver → gold
# MAGIC
# MAGIC **Before running:** run `ingest_local.py` on your laptop, then upload these three files into the
# MAGIC volume this notebook creates (Catalog → `workspace` → `momuk` → `raw` → *Upload to this volume*):
# MAGIC - `momuk-data.csv`
# MAGIC - `naver_trends_raw.csv`
# MAGIC - `weather_raw.csv`
# MAGIC
# MAGIC | Layer | Table | What it is |
# MAGIC |---|---|---|
# MAGIC | Bronze | `bronze_menu`, `bronze_naver_trends`, `bronze_weather` | Files as they arrived |
# MAGIC | Silver | `silver_dish_interest` | Naver batches rescaled onto one scale, missing days filled |
# MAGIC | Silver | `silver_weather_province` | Each province's own daily weather + flags (KR-xx codes) |
# MAGIC | Silver | `silver_weather_daily` | Population-weighted national weather + flags |
# MAGIC | Silver | `silver_dish_interest_clean` | Cleaned interest: days before each dish existed removed, viral spikes capped |
# MAGIC | Silver | `silver_dish_quality` | One row per dish: start date, usual level, spike count, coarse flag |
# MAGIC | Gold | `gold_dish_day` | One row per dish per day: cleaned interest + weather + calendar + menu attributes |
# MAGIC
# MAGIC Also needs `calendar_kr.csv` in the volume (the spike rule leaves food days alone).

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG = "workspace"   # Free Edition's default catalog; change if yours differs
SCHEMA = "momuk"
ANCHOR_ID = "kimchi-jjigae"   # must match ingest_local.py

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.raw")
spark.sql(f"USE {CATALOG}.{SCHEMA}")
VOL = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
display(dbutils.fs.ls(VOL))

# COMMAND ----------

# MAGIC %md ## Bronze — load the raw files untouched

# COMMAND ----------

def read_csv(name):
    return (spark.read.option("header", True).option("inferSchema", True)
            .option("encoding", "UTF-8").csv(f"{VOL}/{name}"))

read_csv("momuk-data.csv").write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("bronze_menu")
read_csv("naver_trends_raw.csv").write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("bronze_naver_trends")
read_csv("weather_raw.csv").write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("bronze_weather")

for t in ["bronze_menu", "bronze_naver_trends", "bronze_weather"]:
    print(t, spark.table(t).count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver 1 — put every Naver batch on one scale
# MAGIC
# MAGIC Naver scales each request so its own peak = 100, so batch 3's "50" ≠ batch 7's "50".
# MAGIC The anchor dish is in every batch, so its total in each batch tells us that batch's scale factor:
# MAGIC
# MAGIC `interest = ratio × (reference anchor total ÷ this batch's anchor total)`

# COMMAND ----------

raw = (spark.table("bronze_naver_trends")
       .withColumn("date", F.to_date("date"))
       .withColumn("ratio", F.col("ratio").cast("double")))

anchor_tot = (raw.filter(F.col("dish_id") == ANCHOR_ID)
              .groupBy("batch").agg(F.sum("ratio").alias("anchor_sum")))

bad = anchor_tot.filter(F.col("anchor_sum") <= 0).count()
assert bad == 0, f"{bad} batches have zero anchor interest — pick a different anchor dish"

ref = anchor_tot.agg(F.avg("anchor_sum")).first()[0]

scaled = (raw.join(anchor_tot, "batch")
          .withColumn("interest", F.col("ratio") * F.lit(ref) / F.col("anchor_sum"))
          # the anchor appears in every batch; average its (near-identical) rescaled copies
          .groupBy("dish_id", "date").agg(F.avg("interest").alias("interest")))

# Naver can omit days with no measurable searches -> fill the full dish x date grid with 0
bounds = raw.agg(F.min("date").alias("lo"), F.max("date").alias("hi")).first()
dates = spark.sql(
    f"SELECT explode(sequence(to_date('{bounds.lo}'), to_date('{bounds.hi}'), interval 1 day)) AS date")
dishes = spark.table("bronze_menu").select(F.col("id").alias("dish_id"))

silver_interest = (dishes.crossJoin(dates)
                   .join(scaled, ["dish_id", "date"], "left")
                   .withColumn("was_missing", F.col("interest").isNull())
                   .fillna({"interest": 0.0}))

silver_interest.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("silver_dish_interest")

# Data-quality check: dishes that are mostly zeros are too rare (or badly named) to model yet
quality = (silver_interest.groupBy("dish_id")
           .agg(F.avg(F.col("interest").cast("double")).alias("mean_interest"),
                F.avg((F.col("interest") == 0).cast("int")).alias("share_zero_days"))
           .orderBy(F.desc("share_zero_days")))
display(quality)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver 2 — weather at two levels
# MAGIC - `silver_weather_province`: each of the 17 provinces' own daily weather, keyed by the same
# MAGIC   `geo_code` Google Trends uses (KR-11 = Seoul …), so it joins straight onto regional search data later.
# MAGIC - `silver_weather_daily`: one population-weighted "national" series to pair with Naver's national data,
# MAGIC   so Seoul + Gyeonggi count most (that's where most searches come from).
# MAGIC - **A national day is rainy when at least half the population's provinces got ≥1 mm of rain**
# MAGIC   (`rain_share` ≥ 0.5), not when the national *average* reaches 1 mm: an average lets one heavy local
# MAGIC   storm label the whole country rainy while most people had a dry day.

# COMMAND ----------

w = spark.table("bronze_weather").withColumn("date", F.to_date("date"))
num_cols = [c for c in w.columns if c not in ("city", "geo_code", "population_m", "date")]

# Rain and snow are flagged separately (rain_sum excludes snow), so 전-on-rainy-days
# and snowy-day foods can be tested on their own.
def add_flags(df):
    return (df
        .withColumn("is_rainy", (F.col("rain_sum") >= 1.0).cast("int"))           # ≥1 mm rain
        .withColumn("is_heavy_rain", (F.col("rain_sum") >= 10.0).cast("int"))     # ≥10 mm rain
        .withColumn("is_all_day_rain", (F.col("precipitation_hours") >= 8).cast("int"))
        .withColumn("is_snowy", (F.col("snowfall_sum") > 0.0).cast("int"))
        .withColumn("is_hot", (F.col("temperature_2m_max") >= 30.0).cast("int"))  # high ≥30°C
        .withColumn("feels_hot", (F.col("apparent_temperature_mean") >= 28.0).cast("int"))
        .withColumn("is_cold", (F.col("temperature_2m_max") <= 0.0).cast("int"))  # high ≤0°C
        .withColumn("is_windy", (F.col("wind_speed_10m_max") >= 30.0).cast("int")))

# Province level
silver_weather_province = add_flags(w)
silver_weather_province.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("silver_weather_province")

# National level (population-weighted)
RAIN_SHARE_MIN = 0.5   # a day is rainy nationally when ≥50% of people's provinces got ≥1 mm

weighted = w.groupBy("date").agg(
    *[(F.sum(F.col(c) * F.col("population_m")) / F.sum("population_m")).alias(c) for c in num_cols])
rain_share = silver_weather_province.groupBy("date").agg(
    (F.sum(F.col("is_rainy") * F.col("population_m")) / F.sum("population_m")).alias("rain_share"))
silver_weather = (add_flags(weighted)
                  .join(rain_share, "date")
                  .withColumn("is_rainy", (F.col("rain_share") >= RAIN_SHARE_MIN).cast("int")))
silver_weather.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("silver_weather_daily")

print("provinces:", silver_weather_province.select("geo_code").distinct().count())
display(silver_weather.orderBy(F.desc("date")).limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver 3 — cleaning (decided 2026-11-22, see DECISIONS.md)
# MAGIC
# MAGIC 1. **Start dates.** A newer dish (마라탕, 로제떡볶이…) shows near-zero interest before it took off. Those days
# MAGIC    mean "didn't exist yet", not "nobody wanted it", so they are **removed** rather than kept as zeros.
# MAGIC    A dish starts in the first week from which its weekly interest stays at or above `START_SHARE` (25%)
# MAGIC    of its usual level (median week over the last 52 weeks) for `START_RUN_WEEKS` (4) weeks in a row.
# MAGIC 2. **Viral spikes.** A day above `SPIKE_X` (3×) the median of the surrounding month (±14 days) is flagged
# MAGIC    `is_spike` and capped at 3× for every lift. The raw value stays in `interest_raw`. Food days in
# MAGIC    `calendar_kr.csv` are never capped — 동지 → 팥죽 is a spike on purpose, and the event study measures it.
# MAGIC 3. **Coarse series.** Dishes with fewer than `COARSE_MIN_DISTINCT` distinct daily values move in visible steps
# MAGIC    (too few searches for Naver's rounding). They are flagged `is_coarse` and skipped by the spike rule (a jump
# MAGIC    from 1 to 4 is rounding, not a viral moment). How they're measured weekly is decided once this run shows
# MAGIC    how many there are.

# COMMAND ----------

from pyspark.sql import Window

START_SHARE = 0.25        # a dish exists once weekly interest stays ≥ 25% of its usual level… (was 10%: 마라탕 started in 2016)
START_RUN_WEEKS = 4       # …for 4 weeks in a row
SPIKE_X = 3.0             # a day > 3× the median of its surrounding month is a spike
COARSE_MIN_DISTINCT = 50  # fewer distinct daily values than this = coarse

si = spark.table("silver_dish_interest")
first_date, last_date = si.agg(F.min("date"), F.max("date")).first()

# 1. start dates
weekly = (si.withColumn("week", F.date_trunc("week", "date").cast("date"))
          .groupBy("dish_id", "week").agg(F.avg("interest").alias("wk")))
usual = (weekly.filter(F.col("week") >= F.date_sub(F.lit(last_date), 364))
         .groupBy("dish_id").agg(F.expr("percentile_approx(wk, 0.5)").alias("usual")))
by_week = Window.partitionBy("dish_id").orderBy("week").rowsBetween(0, START_RUN_WEEKS - 1)
start = (weekly.join(usual, "dish_id")
         .withColumn("above", (F.col("wk") >= START_SHARE * F.col("usual")).cast("int"))
         .withColumn("run", F.sum("above").over(by_week))
         .filter(F.col("run") == START_RUN_WEEKS)
         .groupBy("dish_id").agg(F.min("week").alias("start_week")))

# 2. spikes (food days exempt)
event_days = (spark.read.option("header", True).option("encoding", "UTF-8").csv(f"{VOL}/calendar_kr.csv")
              .select(F.to_date("date").alias("date")).distinct().withColumn("is_event_day", F.lit(True)))
month_around = Window.partitionBy("dish_id").orderBy("date").rowsBetween(-14, 14)

trimmed = (si.join(usual, "dish_id", "left").join(start, "dish_id", "left")
           .withColumn("start_date", F.greatest(F.coalesce("start_week", F.lit(first_date)), F.lit(first_date)))
           .filter(F.col("date") >= F.col("start_date")))

# 3. coarse series — found before spikes: in a coarse series a jump from 1 to 4 is rounding, not a spike
coarse = (trimmed.groupBy("dish_id")
          .agg(F.countDistinct(F.round("interest", 4)).alias("distinct_values"))
          .withColumn("is_coarse", F.col("distinct_values") < COARSE_MIN_DISTINCT))

clean = (trimmed.join(coarse, "dish_id")
         .withColumn("local_median", F.percentile_approx("interest", 0.5).over(month_around))
         # floor: a dish at its seasonal low (팥죽 in July) shouldn't call every small bump a spike
         .withColumn("spike_ceiling", F.lit(SPIKE_X) * F.greatest("local_median", F.lit(START_SHARE) * F.col("usual")))
         .join(event_days, "date", "left").fillna({"is_event_day": False})
         .withColumn("is_spike", (F.col("interest") > F.col("spike_ceiling")) & ~F.col("is_event_day") & ~F.col("is_coarse"))
         .withColumn("interest_raw", F.col("interest"))
         .withColumn("interest", F.when(F.col("is_spike"), F.col("spike_ceiling")).otherwise(F.col("interest")))
         .select("dish_id", "date", "interest", "interest_raw", "is_spike", "is_event_day", "was_missing"))
clean.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("silver_dish_interest_clean")

# one quality row per dish
c = spark.table("silver_dish_interest_clean")
quality = (c.groupBy("dish_id").agg(
               F.min("date").alias("start_date"),
               F.avg((F.col("interest_raw") == 0).cast("int")).alias("share_zero_days"),
               F.sum(F.col("is_spike").cast("int")).alias("spike_days"))
           .join(usual, "dish_id", "left")
           .join(coarse, "dish_id", "left"))
quality.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("silver_dish_quality")

q = spark.table("silver_dish_quality").join(
    spark.table("bronze_menu").select(F.col("id").alias("dish_id"), "ko"), "dish_id")
print(f"rows before cleaning: {si.count():,}  after: {c.count():,}")
print("spike days:", c.filter("is_spike").count(), "of", c.count())

# COMMAND ----------

# MAGIC %md
# MAGIC ### Review 1 — start dates
# MAGIC Dishes whose data now starts after the first day. Do these match when each dish took off?
# MAGIC If too many established dishes appear, lower `START_SHARE`; if booms start too early, raise it.

# COMMAND ----------

display(q.filter(F.col("start_date") > F.lit(first_date))
         .select("ko", "dish_id", "start_date", "usual").orderBy("start_date"))

# COMMAND ----------

# MAGIC %md ### Review 2 — the largest spikes that were capped

# COMMAND ----------

display(c.filter("is_spike").join(q.select("dish_id", "ko"), "dish_id")
         .withColumn("x_month_median", F.round(F.col("interest_raw") / F.col("interest") * SPIKE_X, 1))
         .select("ko", "date", "interest_raw", "interest", "x_month_median")
         .orderBy(F.desc("x_month_median")).limit(30))

# COMMAND ----------

# MAGIC %md ### Review 3 — coarse dishes

# COMMAND ----------

display(q.select("ko", "dish_id", "distinct_values", "share_zero_days", "is_coarse").orderBy("distinct_values").limit(30))

# COMMAND ----------

# MAGIC %md ## Gold — one row per dish per day

# COMMAND ----------

menu = spark.table("bronze_menu").withColumnRenamed("id", "dish_id")

gold = (spark.table("silver_dish_interest_clean")
        .join(spark.table("silver_weather_daily"), "date")
        .join(spark.table("silver_dish_quality").select("dish_id", "is_coarse"), "dish_id")
        .join(menu, "dish_id")
        .withColumn("year", F.year("date"))
        .withColumn("month", F.month("date"))
        .withColumn("dow", F.dayofweek("date"))             # 1 = Sunday … 7 = Saturday
        .withColumn("is_weekend", F.col("dow").isin(1, 7).cast("int")))

gold.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("gold_dish_day")
print("gold_dish_day rows:", spark.table("gold_dish_day").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## First look — does rain move cravings?
# MAGIC Quick (not yet causal) check: compare rainy vs dry days **within the same month and weekday**, so
# MAGIC "rainy season" and "weekends" don't masquerade as a rain effect. `rain_lift` = 1.5 means
# MAGIC 50% more interest on rainy days than comparable dry days.

# COMMAND ----------

g = spark.table("gold_dish_day")

cell = g.groupBy("dish_id", "month", "dow", "is_rainy").agg(F.avg("interest").alias("m"))
pv = (cell.groupBy("dish_id", "month", "dow").pivot("is_rainy", [0, 1]).agg(F.first("m"))
      .withColumnRenamed("0", "dry").withColumnRenamed("1", "rainy")
      .filter((F.col("dry") > 0) & F.col("rainy").isNotNull()))

rain_lift = (pv.withColumn("ratio", F.col("rainy") / F.col("dry"))
             .groupBy("dish_id").agg(F.expr("percentile_approx(ratio, 0.5)").alias("rain_lift"))
             .join(menu.select("dish_id", "ko", "tags"), "dish_id")
             .withColumn("tagged_rainy_day", F.col("tags").contains("비오는날"))
             .orderBy(F.desc("rain_lift")))

display(rain_lift)   # does your 비오는날 tag line up with the top of this list?

# COMMAND ----------

# MAGIC %md
# MAGIC ## Weekend vs weekday — which cravings belong to the weekend?
# MAGIC Same idea as rain lift: compare weekend vs weekday days **within the same month and the same rain
# MAGIC state**, so season and weather don't masquerade as a weekend effect. `weekend_lift` = 1.3 means
# MAGIC 30% more interest on weekends than comparable weekdays.
# MAGIC
# MAGIC Naver data is daily, so time of day (lunch / dinner / late night) can't be seen here — that comes from
# MAGIC the menu's `meal_*` columns now, and from your own users' order times later.

# COMMAND ----------

cellw = g.groupBy("dish_id", "month", "is_rainy", "is_weekend").agg(F.avg("interest").alias("m"))
pvw = (cellw.groupBy("dish_id", "month", "is_rainy").pivot("is_weekend", [0, 1]).agg(F.first("m"))
       .withColumnRenamed("0", "weekday").withColumnRenamed("1", "weekend")
       .filter((F.col("weekday") > 0) & F.col("weekend").isNotNull()))

weekend_lift = (pvw.withColumn("ratio", F.col("weekend") / F.col("weekday"))
                .groupBy("dish_id").agg(F.expr("percentile_approx(ratio, 0.5)").alias("weekend_lift"))
                .join(menu.select("dish_id", "ko", "tags", "meal_late_night"), "dish_id")
                .orderBy(F.desc("weekend_lift")))

display(weekend_lift)   # do 해장 / 술안주 / 야식 dishes rise on weekends?
