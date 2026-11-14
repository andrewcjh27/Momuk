"""
momuk — Korean food calendar, 2016 to two years ahead

Dates that Koreans tie to particular foods, so the notebook can measure each
dish's "holiday lift" the same way it measures rain lift.

  event            dates                              expected food link
  seollal          설날 전날 / 당일 / 다음날              떡국, 만둣국
  chuseok          추석 전날 / 당일 / 다음날              전, 송편 (not in catalog)
  boknal           초복 / 중복 / 말복                     삼계탕
  dongji           동지 (winter solstice, KST)            팥죽 (not in catalog)
  christmas        12/24 and 12/25                        치킨, 피자
  suneung          수능 day                               (exam-day meals, celebrations after)
  samgyeopsal_day  3/3 삼겹살데이                         삼겹살
  black_day        4/14 블랙데이                           짜장면

How the varying dates are found
  - 설날 / 추석: the `holidays` package (lunar calendar), only the three core days
    (substitute holidays are left out — they are days off, not festival days).
  - 복날: 초복 = 3rd 경일(庚日) on or after 하지, 중복 = 4th, 말복 = 1st 경일 on or after
    입추. Solar terms come from `ephem` (sun's longitude 90° and 135°, in KST);
    the day's heavenly stem from a fixed reference (2000-01-07 was a 甲子 day).
    Checked against published dates for 2023-2025.
  - 동지: winter solstice date in KST, from `ephem`.
  - 수능: published exam dates, added by hand (2017: postponed a week after the Pohang earthquake;
    2020: moved to December because of COVID-19).

Every date except 수능 is calculated, so rerunning this script extends the calendar
automatically. 수능 dates are added by hand to SUNEUNG when announced.

Run      pip3 install holidays ephem && python3 build_calendar.py
Output   calendar_kr.csv   (date, event, label) — upload to the Databricks volume
"""

import datetime as dt
import math
from pathlib import Path

import ephem
import holidays
import pandas as pd

# 2016 (start of the Naver data) through two years ahead, so future dates are always covered
YEARS = range(2016, dt.date.today().year + 3)
KST = dt.timedelta(hours=9)
OUT = Path(__file__).resolve().parent / "calendar_kr.csv"

# 수능 is the only date that can't be calculated: it is announced about a year ahead.
# Add each new year here when it is announced (usually a Thursday in mid-November).
SUNEUNG = {
    2016: "2016-11-17", 2017: "2017-11-23", 2018: "2018-11-15", 2019: "2019-11-14",
    2020: "2020-12-03", 2021: "2021-11-18", 2022: "2022-11-17", 2023: "2023-11-16",
    2024: "2024-11-14", 2025: "2025-11-13", 2026: "2026-11-19",
}

# published 복날 dates used to check the calculation
KNOWN_BOKNAL = {
    2023: ("2023-07-11", "2023-07-21", "2023-08-10"),
    2024: ("2024-07-15", "2024-07-25", "2024-08-14"),
    2025: ("2025-07-20", "2025-07-30", "2025-08-09"),
}


# ---------------------------------------------------------------- astronomy
def sun_longitude(t: ephem.Date) -> float:
    sun = ephem.Sun(t)
    return math.degrees(ephem.Ecliptic(sun, epoch=t).lon)


def solar_term_kst(year: int, longitude: float, start_month: int) -> dt.date:
    """KST date when the sun reaches `longitude` degrees, searching from start_month."""
    t0 = ephem.Date(dt.datetime(year, start_month, 1))
    lo, hi = float(t0), float(t0) + 40

    def diff(t):
        return ((sun_longitude(ephem.Date(t)) - longitude + 180) % 360) - 180

    for _ in range(60):                     # bisection to well under a minute
        mid = (lo + hi) / 2
        if diff(mid) < 0:
            lo = mid
        else:
            hi = mid
    utc = ephem.Date(hi).datetime()
    return (utc + KST).date()


def is_gyeong_day(day: dt.date) -> bool:
    """庚 is the 7th heavenly stem (index 6); 2000-01-07 was 甲子 (index 0)."""
    return (day - dt.date(2000, 1, 7)).days % 10 == 6


def nth_gyeong_on_or_after(start: dt.date, n: int) -> dt.date:
    day, count = start, 0
    while True:
        if is_gyeong_day(day):
            count += 1
            if count == n:
                return day
        day += dt.timedelta(days=1)


def boknal(year: int):
    haji = solar_term_kst(year, 90, 6)
    ipchu = solar_term_kst(year, 135, 7)
    return (nth_gyeong_on_or_after(haji, 3), nth_gyeong_on_or_after(haji, 4),
            nth_gyeong_on_or_after(ipchu, 1))


# ---------------------------------------------------------------- build
def build() -> pd.DataFrame:
    rows = []
    add = lambda d, event, label: rows.append({"date": pd.Timestamp(d).date(), "event": event, "label": label})

    for y in YEARS:
        for d, names in holidays.KR(years=y, language="ko").items():
            for name in names.split("; "):          # two holidays on one day are joined, e.g. "개천절; 추석 전날"
                if name in ("설날 전날", "설날", "설날 다음날"):
                    add(d, "seollal", name)
                elif name in ("추석 전날", "추석", "추석 다음날"):
                    add(d, "chuseok", name)

        for d, label in zip(boknal(y), ("초복", "중복", "말복")):
            add(d, "boknal", label)
        add(solar_term_kst(y, 270, 12), "dongji", "동지")
        add(f"{y}-12-24", "christmas", "크리스마스 이브")
        add(f"{y}-12-25", "christmas", "크리스마스")
        add(f"{y}-03-03", "samgyeopsal_day", "삼겹살데이")
        add(f"{y}-04-14", "black_day", "블랙데이")
        if y in SUNEUNG:
            add(SUNEUNG[y], "suneung", "수능")
        elif y <= dt.date.today().year + 1:
            print(f"Note: no 수능 date for {y} yet — add it to SUNEUNG once announced.")

    cal = pd.DataFrame(rows).drop_duplicates(["date", "event"]).sort_values(["date", "event"])
    return cal


def check(cal: pd.DataFrame) -> None:
    for y, expected in KNOWN_BOKNAL.items():
        got = tuple(str(d) for d in sorted(cal[(cal.event == "boknal") &
                                                (pd.to_datetime(cal.date).dt.year == y)].date))
        assert got == expected, f"복날 {y}: computed {got}, published {expected}"
    per_year = cal.groupby([pd.to_datetime(cal.date).dt.year, "event"]).size().unstack()
    assert (per_year["seollal"] == 3).all() and (per_year["chuseok"] == 3).all()
    assert (per_year["boknal"] == 3).all() and (per_year["dongji"] == 1).all()


if __name__ == "__main__":
    cal = build()
    check(cal)
    cal.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Wrote {OUT.name}: {len(cal)} rows")
    print(cal.assign(year=pd.to_datetime(cal.date).dt.year)
          .query("year in (2024, 2025)").to_string(index=False))
