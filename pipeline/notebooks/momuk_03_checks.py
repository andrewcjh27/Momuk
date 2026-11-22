# Databricks notebook source
# MAGIC %md
# MAGIC # momuk — 03: data checks
# MAGIC
# MAGIC Runs after notebooks 01 and 02. Every check is written as "this must be true". Results are appended
# MAGIC to `ops_run_log`, so every run leaves a record of what passed. If any **error**-level check fails,
# MAGIC the last cell raises an exception, which marks the scheduled job as failed instead of letting wrong
# MAGIC numbers reach the recommender. **Warnings** are logged but don't stop the run.
# MAGIC
# MAGIC | Level | Meaning |
# MAGIC |---|---|
# MAGIC | error | The data is wrong — stop |
# MAGIC | warn | Worth a look, but results are still usable |

# COMMAND ----------

import datetime as dt
from pyspark.sql import functions as F

spark.sql("USE workspace.momuk")

# Freshness becomes an error once the weekly job is running; until then the data is a one-off pull.
AUTOMATED = False
MAX_DATA_AGE_DAYS = 10     # Naver lags ~1 day; a weekly job should never be more than ~10 days behind
MAX_SPIKE_SHARE = 0.02     # if more than 2% of days are "spikes", the rule is too aggressive
N_PROVINCES = 17
REGION_CAP = 1.5           # must match notebook 02

results = []

def check(name, ok, detail="", level="error"):
    results.append((name, level, bool(ok), str(detail)))
    print(f"{'PASS' if ok else level.upper():5}  {name}  {detail}")

menu = spark.table("bronze_menu")
clean = spark.table("silver_dish_interest_clean")
gold = spark.table("gold_dish_day")

# COMMAND ----------

# MAGIC %md ## Catalog

# COMMAND ----------

n_menu = menu.count()
check("catalog: dish ids are unique", menu.select("id").distinct().count() == n_menu, f"{n_menu} dishes")

meal_cols = [c for c in menu.columns if c.startswith("meal_")]
bad_meal = menu.filter(" OR ".join(f"{c} IS NULL OR {c} < 0 OR {c} > 1" for c in meal_cols)).count()
check("catalog: meal values are between 0 and 1", bad_meal == 0, f"{bad_meal} bad rows")

no_meal = menu.filter(" AND ".join(f"{c} = 0" for c in meal_cols)).count()
check("catalog: every dish fits at least one meal", no_meal == 0, f"{no_meal} dishes fit no meal")

no_kw = menu.filter(F.col("search_keyword").isNull() | (F.trim("search_keyword") == "")).count()
check("catalog: every dish has a search keyword", no_kw == 0, f"{no_kw} missing")

# COMMAND ----------

# MAGIC %md ## Search interest

# COMMAND ----------

missing = menu.select(F.col("id").alias("dish_id")).join(clean.select("dish_id").distinct(), "dish_id", "left_anti")
n_missing = missing.count()
check("interest: every catalog dish has data", n_missing == 0,
      [r.dish_id for r in missing.limit(10).collect()] if n_missing else "")

dupes = clean.groupBy("dish_id", "date").count().filter("count > 1").count()
check("interest: one row per dish per day", dupes == 0, f"{dupes} duplicates")

gaps = (clean.groupBy("dish_id")
        .agg(F.count("*").alias("n"), F.datediff(F.max("date"), F.min("date")).alias("span"))
        .filter(F.col("n") != F.col("span") + 1).count())
check("interest: no missing days after each dish's start", gaps == 0, f"{gaps} dishes with gaps")

bad_vals = clean.filter(F.col("interest").isNull() | (F.col("interest") < 0)).count()
check("interest: no negative or empty values", bad_vals == 0, f"{bad_vals} rows")

n_rows = clean.count()
spike_share = clean.filter("is_spike").count() / max(n_rows, 1)
check("interest: spikes are rare", spike_share <= MAX_SPIKE_SHARE, f"{spike_share:.2%} of days", level="warn")

last = clean.agg(F.max("date")).first()[0]
age = (dt.date.today() - last).days
check("interest: data is recent", age <= MAX_DATA_AGE_DAYS, f"latest day {last} ({age} days old)",
      level="error" if AUTOMATED else "warn")

# COMMAND ----------

# MAGIC %md ## Weather

# COMMAND ----------

wp = spark.table("silver_weather_province")
short_days = wp.groupBy("date").agg(F.countDistinct("geo_code").alias("n")).filter(F.col("n") != N_PROVINCES).count()
check(f"weather: all {N_PROVINCES} provinces every day", short_days == 0, f"{short_days} incomplete days")

odd = wp.filter((F.col("temperature_2m_mean") < -30) | (F.col("temperature_2m_mean") > 40) |
                (F.col("precipitation_sum") < 0)).count()
check("weather: temperatures and rain in a sensible range", odd == 0, f"{odd} rows")

wd = spark.table("silver_weather_daily")
bad_share = wd.filter(F.col("rain_share").isNull() | (F.col("rain_share") < 0) | (F.col("rain_share") > 1)).count()
check("weather: rain_share is between 0 and 1", bad_share == 0, f"{bad_share} rows")

check("gold: every cleaned row found its weather", gold.count() == n_rows, f"gold {gold.count():,} vs clean {n_rows:,}")

# COMMAND ----------

# MAGIC %md ## Lifts used by the recommender

# COMMAND ----------

def out_of_range(table, col, lo, hi):
    return spark.table(table).filter(F.col(col).isNull() | (F.col(col) < lo) | (F.col(col) > hi)).count()

n = out_of_range("silver_region_lean", "lean_shrunk", 1 / REGION_CAP - 1e-9, REGION_CAP + 1e-9)
check(f"region: leans within 1/{REGION_CAP}–{REGION_CAP}", n == 0, f"{n} rows")

n = out_of_range("gold_event_lift", "event_lift", 0.5, 3.0)
check("food days: event lift within 0.5–3.0", n == 0, f"{n} rows")

n = spark.table("gold_event_lift").filter((F.col("event") == "dongji") & (F.col("dish_id") != "patjuk")).count()
check("food days: 동지 boosts only 팥죽", n == 0, f"{n} other dishes")

n = out_of_range("gold_weekend_lift", "weekend_lift", 0.5, 2.0)
check("weekend: lift within 0.5–2.0", n == 0, f"{n} rows")

n = spark.table("gold_temp_boost").select("dish_id").distinct().count()
check("temperature: boost exists for most dishes", n >= 0.9 * n_menu, f"{n} of {n_menu} dishes", level="warn")

# COMMAND ----------

# MAGIC %md ## Log the run and stop if anything is wrong

# COMMAND ----------

run_ts = dt.datetime.now(dt.timezone.utc)
log = spark.createDataFrame([(run_ts, *r) for r in results],
                            "run_ts timestamp, check string, level string, passed boolean, detail string")
log.write.mode("append").saveAsTable("ops_run_log")

failed = [r for r in results if not r[2] and r[1] == "error"]
warned = [r for r in results if not r[2] and r[1] == "warn"]
print(f"\n{len(results)} checks: {len(results) - len(failed) - len(warned)} passed, "
      f"{len(warned)} warnings, {len(failed)} errors")
if failed:
    raise Exception("Data checks failed: " + "; ".join(f"{r[0]} ({r[3]})" for r in failed))
