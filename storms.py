"""
storms.py — pull recent severe-storm reports from NOAA's Storm Prediction Center.

These are public Local Storm Reports (hail size, wind speed, lat/lon, date).
Recent damaging hail or wind over a property is the single most defensible
reason to knock on a door and offer a free inspection: the storm is a real,
dated, public event — not a guess about the roof.

CSV endpoints (confirmed live), one file per day:
    https://www.spc.noaa.gov/climo/reports/{YYMMDD}_rpts_hail.csv
    https://www.spc.noaa.gov/climo/reports/{YYMMDD}_rpts_wind.csv

Hail Size is in 1/100 inch (100 = 1.00"). Wind Speed is in knots ("UNK" when a
report is damage-only with no measured speed).
"""

from __future__ import annotations

import csv
import io
import math
from datetime import date, timedelta
from dataclasses import dataclass

import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import (
    SPC_REPORTS_BASE, STORM_LOOKBACK_DAYS,
    HAIL_DAMAGE_MIN_INCHES, WIND_DAMAGE_MIN_KNOTS, STORM_MATCH_RADIUS_MI,
    SERVICE_AREA_CENTER_LATLON, STORM_REGION_RADIUS_MI,
)

EARTH_RADIUS_MI = 3958.8


@dataclass
class StormReport:
    kind: str          # "hail" or "wind"
    magnitude: float   # inches (hail) or knots (wind)
    lat: float
    lon: float
    day: date
    location: str


def haversine_mi(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _fetch_csv(url: str):
    resp = requests.get(url, timeout=20)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.text


def _parse_hail(text: str, day: date) -> list[StormReport]:
    out = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 7 or row[0].strip().lower() == "time":
            continue
        try:
            size_in = float(row[1]) / 100.0
            lat, lon = float(row[5]), float(row[6])
        except (ValueError, IndexError):
            continue
        if size_in >= HAIL_DAMAGE_MIN_INCHES:
            out.append(StormReport("hail", size_in, lat, lon, day, row[2].strip()))
    return out


def _parse_wind(text: str, day: date) -> list[StormReport]:
    out = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 7 or row[0].strip().lower() == "time":
            continue
        spd_raw = row[1].strip().upper()
        if spd_raw in ("", "UNK"):
            continue
        try:
            spd = float(spd_raw)
            lat, lon = float(row[5]), float(row[6])
        except (ValueError, IndexError):
            continue
        if spd >= WIND_DAMAGE_MIN_KNOTS:
            out.append(StormReport("wind", spd, lat, lon, day, row[2].strip()))
    return out


def fetch_recent_storms() -> list[StormReport]:
    """Pull hail + wind reports over the lookback window, kept to your region."""
    reports: list[StormReport] = []
    today = date.today()
    for d in range(STORM_LOOKBACK_DAYS):
        day = today - timedelta(days=d)
        ymd = day.strftime("%y%m%d")
        for kind, parser in (("hail", _parse_hail), ("wind", _parse_wind)):
            url = f"{SPC_REPORTS_BASE}/{ymd}_rpts_{kind}.csv"
            try:
                text = _fetch_csv(url)
            except Exception as e:
                logger.warning(f"  {url} failed: {e}")
                continue
            if text:
                reports.extend(parser(text, day))

    # Discard reports outside the service-area region (SPC files are nationwide).
    clat, clon = SERVICE_AREA_CENTER_LATLON
    local = [
        r for r in reports
        if haversine_mi(clat, clon, r.lat, r.lon) <= STORM_REGION_RADIUS_MI
    ]
    logger.success(
        f"Damaging storm reports near service area in last "
        f"{STORM_LOOKBACK_DAYS} days: {len(local)} (of {len(reports)} nationwide)"
    )
    return local


@dataclass
class StormMatch:
    exposed: bool
    nearest_mi: float | None
    worst_hail_in: float
    worst_wind_kt: float
    last_storm_day: date | None


def match_parcel(lat: float, lon: float, storms: list[StormReport]) -> StormMatch:
    nearest, worst_hail, worst_wind, last_day = None, 0.0, 0.0, None
    for s in storms:
        if haversine_mi(lat, lon, s.lat, s.lon) <= STORM_MATCH_RADIUS_MI:
            d = haversine_mi(lat, lon, s.lat, s.lon)
            nearest = d if nearest is None else min(nearest, d)
            if s.kind == "hail":
                worst_hail = max(worst_hail, s.magnitude)
            else:
                worst_wind = max(worst_wind, s.magnitude)
            last_day = s.day if last_day is None else max(last_day, s.day)
    return StormMatch(
        exposed=nearest is not None,
        nearest_mi=round(nearest, 2) if nearest is not None else None,
        worst_hail_in=worst_hail,
        worst_wind_kt=worst_wind,
        last_storm_day=last_day,
    )
