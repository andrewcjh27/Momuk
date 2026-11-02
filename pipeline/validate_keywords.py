"""
momuk — keyword entity resolution (run on your laptop)

Problem
  One dish is searched under several names: 돈카츠 / 돈까스 / 돈가스, 짜장면 / 자장면,
  어묵 / 오뎅. If we only search one spelling we under-count the dish (후라이드치킨 looked
  tiny because people type "치킨" or "후라이드"). Naver sums every keyword inside one
  group, so the fix is to give each dish a validated SET of keywords.

Method — two independent signals per candidate keyword
  1. String similarity (jamo-level Levenshtein): is it SPELLED like the dish name?
     Hangul syllables are split into jamo first (쭈 -> ㅉ+ㅜ), so 쭈꾸미 vs 주꾸미 is a
     one-consonant change, not a whole-syllable change.
  2. Behavioural similarity (trend correlation): do people SEARCH it the same way?
     Seasonal foods all rise in summer, so raw correlation would match 냉면 with
     콩국수. We correlate WEEK-TO-WEEK CHANGES of log interest instead, which keeps
     shared spikes (a TV episode, a viral trend) and removes shared seasons.

  The most-searched SPECIFIC name becomes the dish's reference (generic terms like
  냉면 and ambiguous ones like 회 are never the reference). Others are kept if they
  behave like it (correlation), with a looser bar for spelling variants that are
  clearly the same word (high string similarity), and a stricter bar for generic or
  ambiguous terms (냉면, 치킨, 회, 라면, 브런치 …) because they also cover other things.

Inputs   momuk-data.csv, keyword_candidates.csv  (dish_id, candidate, kind, ambiguous)
Outputs  raw/keyword_json/<dish>.json        untouched API responses (resumable)
         raw/keyword_validation.csv          every candidate with its scores + decision
         momuk-data.csv                      gains/updates a search_keyword column
         momuk-data.backup.csv               your previous momuk-data.csv

Run      python3 validate_keywords.py           (~126 small requests, a few minutes)
Then     python3 ingest_local.py --naver-only   (re-pull trends with the new keywords)
"""

import json
import shutil
import time

import numpy as np
import pandas as pd

from ingest_local import RAW, ROOT, naver_request

MENU_CSV = ROOT / "momuk-data.csv"
CANDIDATES_CSV = ROOT / "keyword_candidates.csv"
JSON_DIR = RAW / "keyword_json"
JSON_DIR.mkdir(parents=True, exist_ok=True)

MIN_SHARE = 0.02          # ignore candidates with <2% of the reference's searches
CORR_OK = 0.5             # behaves like the reference
CORR_OK_AMBIGUOUS = 0.7   # stricter for terms that can mean something else
CORR_OK_SPELLING = 0.3    # looser when the spelling is clearly the same word
STRING_SIM_SPELLING = 0.6


# ---------------------------------------------------------------- string similarity
def to_jamo(text: str) -> list[str]:
    """Split Hangul syllables into jamo; drop spaces so spacing variants match."""
    out = []
    for ch in text.replace(" ", ""):
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:                       # a precomposed Hangul syllable
            lead, vowel, tail = code // 588, (code % 588) // 28, code % 28
            out += [chr(0x1100 + lead), chr(0x1161 + vowel)]
            if tail:
                out.append(chr(0x11A7 + tail))
        else:
            out.append(ch)
    return out


def levenshtein(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def string_similarity(a: str, b: str) -> float:
    ja, jb = to_jamo(a), to_jamo(b)
    if not ja and not jb:
        return 1.0
    return 1 - levenshtein(ja, jb) / max(len(ja), len(jb))


# ---------------------------------------------------------------- trend similarity
def change_correlation(x: pd.Series, y: pd.Series) -> float:
    """Correlation of week-to-week changes in log interest (season removed)."""
    dx, dy = np.log1p(x).diff().dropna(), np.log1p(y).diff().dropna()
    if dx.std() == 0 or dy.std() == 0:
        return 0.0
    return float(np.corrcoef(dx, dy)[0, 1])


# ---------------------------------------------------------------- per-dish lookup
def fetch(dish_id: str, terms: list[str]) -> dict:
    path = JSON_DIR / f"{dish_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["response"]
    # each candidate is its own group, so all are on ONE shared scale
    result = naver_request([(t, [t]) for t in terms], time_unit="week")
    path.write_text(json.dumps({"dish_id": dish_id, "terms": terms, "response": result},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    time.sleep(0.3)
    return result


def evaluate(dish_id: str, cands: pd.DataFrame) -> pd.DataFrame:
    terms = cands["candidate"].tolist()
    result = fetch(dish_id, terms)
    series = {}
    for g in result.get("results", []):
        s = pd.Series({p["period"]: p["ratio"] for p in g.get("data", [])}, dtype=float)
        series[g["title"]] = s
    weeks = sorted(set().union(*[s.index for s in series.values()])) if series else []
    frame = pd.DataFrame({t: series.get(t, pd.Series(dtype=float)) for t in terms},
                         index=weeks).fillna(0.0)

    totals = frame.sum()
    # The reference must be a SPECIFIC name for the dish. Generic terms (냉면 covers
    # three dishes) and ambiguous ones (회, 라면) are often the most searched, but
    # letting them lead would pull in searches about other things.
    strict = (cands["ambiguous"] == 1) | (cands["kind"] == "generic")
    specific = cands.loc[~strict, "candidate"].tolist() or terms
    ref = totals[specific].idxmax() if totals[specific].max() > 0 else specific[0]
    main = cands.loc[cands["kind"] == "main", "candidate"].iloc[0]

    rows = []
    for _, c in cands.iterrows():
        t = c["candidate"]
        share = float(totals[t] / totals[ref]) if totals[ref] > 0 else 0.0
        corr = 1.0 if t == ref else change_correlation(frame[t], frame[ref])
        sim = string_similarity(t, main)
        if t == ref:
            decision, why = "keep", "reference (most searched specific name)"
        elif share < MIN_SHARE:
            decision, why = "drop", "too few searches to matter"
        elif c["ambiguous"] or c["kind"] == "generic":
            ok = corr >= CORR_OK_AMBIGUOUS
            decision, why = ("keep" if ok else "drop"), "generic/ambiguous term: strict bar"
        elif corr >= CORR_OK:
            decision, why = "keep", "searched the same way"
        elif c["kind"] in ("spelling", "spacing") and sim >= STRING_SIM_SPELLING and corr >= CORR_OK_SPELLING:
            decision, why = "keep", "same word, different spelling"
        else:
            decision, why = "drop", "behaves differently"
        rows.append({"dish_id": dish_id, "candidate": t, "kind": c["kind"],
                     "ambiguous": c["ambiguous"], "volume_share": round(share, 3),
                     "change_corr": round(corr, 3), "string_sim": round(sim, 3),
                     "decision": decision, "reason": why})
    return pd.DataFrame(rows)


def main() -> None:
    menu = pd.read_csv(MENU_CSV)
    cands = pd.read_csv(CANDIDATES_CSV)
    missing = set(menu["id"]) - set(cands["dish_id"])
    if missing:
        raise SystemExit(f"No candidates for: {sorted(missing)}")

    results = []
    dishes = list(cands["dish_id"].drop_duplicates())
    for i, dish_id in enumerate(dishes, 1):
        results.append(evaluate(dish_id, cands[cands["dish_id"] == dish_id]))
        print(f"[{i}/{len(dishes)}] {dish_id}")

    report = pd.concat(results, ignore_index=True)
    report.to_csv(RAW / "keyword_validation.csv", index=False, encoding="utf-8")

    kept = (report[report["decision"] == "keep"]
            .sort_values(["dish_id", "volume_share"], ascending=[True, False])
            .groupby("dish_id")["candidate"].agg("|".join))

    shutil.copy(MENU_CSV, ROOT / "momuk-data.backup.csv")
    menu["search_keyword"] = menu["id"].map(kept).fillna(menu["ko"])
    menu.to_csv(MENU_CSV, index=False, encoding="utf-8")

    changed = menu[menu["search_keyword"] != menu["ko"]][["ko", "search_keyword"]]
    print(f"\n{len(changed)} dishes now use a different or larger keyword set:")
    print(changed.to_string(index=False))
    print(f"\nFull scores: {RAW / 'keyword_validation.csv'}")
    print("Next: python3 ingest_local.py --naver-only, then re-upload both CSVs to Databricks.")


if __name__ == "__main__":
    main()
