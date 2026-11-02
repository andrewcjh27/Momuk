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
 .write.mode("overwrite").saveAsTable("bronze_google_region"))

print("rows:", spark.table("bronze_google_region").count(),
      "| dishes:", spark.table("bronze_google_region").select("dish_id").distinct().count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver — regional lean, with shrinkage
# MAGIC - **Zeros and missing provinces = unknown**, not "nobody eats it": Google hides provinces with too few
# MAGIC   searches. Treating them as 0 would invent strong negative leans for small provinces.
# MAGIC - **Shrinkage:** a dish seen in only a few provinces gets its lean pulled toward 1 (no adjustment),
# MAGIC   because its numbers are noisy. Same idea as trusting the crowd until you know the individual.
# MAGIC - **Clipping** to 0.5–2.0 so one province can never more than halve or double a recommendation.

# COMMAND ----------

reg = (spark.table("bronze_google_region")
       .withColumn("value", F.col("value").cast("double"))
       .filter(F.col("geo_code").startswith("KR-") & (F.col("value") > 0)))

by_dish = W.partitionBy("dish_id")
lean = (reg
    .withColumn("n_regions", F.count("*").over(by_dish))
    .withColumn("dish_mean", F.avg("value").over(by_dish))
    .withColumn("lean", F.col("value") / F.col("dish_mean"))
    .withColumn("reliability", F.least(F.lit(1.0), F.col("n_regions") / F.lit(16.0)))
    .withColumn("lean_shrunk", F.lit(1.0) + F.col("reliability") * (F.col("lean") - 1))
    .withColumn("lean_shrunk", F.greatest(F.lit(0.5), F.least(F.lit(2.0), F.col("lean_shrunk")))))

lean.write.mode("overwrite").saveAsTable("silver_region_lean")

# Data quality: dishes Google only sees in a few provinces (their leans are mostly shrunk away)
display(lean.select("dish_id", "keyword", "n_regions").distinct().orderBy("n_regions"))

# COMMAND ----------

# MAGIC %md ## Gold — lean + menu attributes

# COMMAND ----------

menu = spark.table("bronze_menu").withColumnRenamed("id", "dish_id")
gold_lean = (spark.table("silver_region_lean")
             .join(menu.select("dish_id", "ko", "cuisine", "tags", "solo", "share", "speed"), "dish_id"))
gold_lean.write.mode("overwrite").saveAsTable("gold_region_lean")

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
# MAGIC ## Recommender v0 — putting the pieces together
# MAGIC ```
# MAGIC score = popularity^0.5 × weather boost × regional lean
# MAGIC ```
# MAGIC - **popularity** — national interest over the last 2 years (Naver). The square root dampens it so
# MAGIC   치킨-level dishes don't win every time.
# MAGIC - **weather boost** — each dish's rain lift (from notebook 01's method) when it's rainy, else 1.
# MAGIC - **regional lean** — the shrunk, clipped lean for the user's province (Google).
# MAGIC - **the 3 questions** filter the menu first: party size, hunger, budget.
# MAGIC
# MAGIC Change the inputs in the next cell and rerun it to see recommendations shift.

# COMMAND ----------

# ---- user inputs (try changing these) ----
GEO = "KR-26"      # province code: KR-11 Seoul, KR-26 Busan, KR-42 Gangwon, ...
IS_RAINY = True
PEOPLE = 1         # 1 = solo; 2+ = sharing dishes
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

hunger_ok = {1: F.col("heavy") <= 1, 2: F.col("heavy").between(1, 2), 3: F.col("heavy") >= 2}[HUNGER]
party_ok = (F.col("solo") == 1) if PEOPLE == 1 else (F.col("share") == 1)

recs = (menu.filter(party_ok & hunger_ok & (F.col("price") <= MAX_PRICE))
        .join(popularity, "dish_id")
        .join(rain_lift, "dish_id", "left")
        .join(region, "dish_id", "left")
        .fillna({"rain_lift": 1.0, "regional_lean": 1.0})
        .withColumn("weather_boost", F.col("rain_lift") if IS_RAINY else F.lit(1.0))
        .withColumn("score", F.sqrt("popularity") * F.col("weather_boost") * F.col("regional_lean"))
        .select("ko", "en", "score", "popularity", "weather_boost", "regional_lean", "tags")
        .orderBy(F.desc("score"))
        .limit(TOP_N))

display(recs)
