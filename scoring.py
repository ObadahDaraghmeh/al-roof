"""
scoring.py — turn parcel facts + storm exposure into an OUTREACH priority.

Framing that matters: the output is a priority for OFFERING A FREE INSPECTION,
not a statement that the roof is damaged. Both inputs are honest:
    • roof-age tier  (building-age proxy from county data)
    • recent severe-storm exposure (dated public NOAA reports)
Nothing here claims to have looked at the roof itself, so nothing here should
ever be repeated to a homeowner as if it were a finding about their roof.
"""

from dataclasses import dataclass, field
from datetime import date

from config import (
    CURRENT_YEAR, ROOF_AGE_LIKELY_PAST_LIFESPAN, ROOF_AGE_APPROACHING,
)
from parcels import format_address, parcel_centroid_latlon
from storms import StormMatch


@dataclass
class Candidate:
    pin: str
    owner: str
    address: str
    lat: float | None
    lon: float | None
    year_built: int | None
    building_age: int | None
    age_tier: str            # past_lifespan | approaching | newer | unknown
    storm_exposed: bool
    nearest_storm_mi: float | None
    worst_hail_in: float
    worst_wind_kt: float
    last_storm_day: date | None
    priority: str            # HIGH | MEDIUM | LOW
    reasons: list = field(default_factory=list)
    recommended_action: str = "Offer a free, no-obligation roof inspection."
    auditor_link: str = ""


def _age_tier(building_age):
    if building_age is None:
        return "unknown"
    if building_age >= ROOF_AGE_LIKELY_PAST_LIFESPAN:
        return "past_lifespan"
    if building_age >= ROOF_AGE_APPROACHING:
        return "approaching"
    return "newer"


def score(feature: dict, storm: StormMatch) -> Candidate:
    attrs = feature.get("attributes", {})
    yr = attrs.get("YRBLT")
    yr = int(yr) if yr else None
    age = (CURRENT_YEAR - yr) if yr else None
    tier = _age_tier(age)
    centroid = parcel_centroid_latlon(feature)
    lat, lon = centroid if centroid else (None, None)

    reasons = []
    if tier == "past_lifespan":
        reasons.append(f"Building ~{age} yrs old; original roof likely past typical lifespan")
    elif tier == "approaching":
        reasons.append(f"Building ~{age} yrs old; roof may be approaching end of life")
    if storm.exposed:
        bits = []
        if storm.worst_hail_in:
            bits.append(f'{storm.worst_hail_in:.2f}" hail')
        if storm.worst_wind_kt:
            bits.append(f"{storm.worst_wind_kt:.0f} kt wind")
        when = storm.last_storm_day.isoformat() if storm.last_storm_day else "recently"
        reasons.append(
            f"Severe storm within {storm.nearest_mi} mi "
            f"({', '.join(bits) or 'severe report'}; last {when})"
        )

    # Priority: storm exposure is the strongest reason to knock; age stacks with it.
    if storm.exposed and tier in ("past_lifespan", "approaching"):
        priority = "HIGH"
    elif storm.exposed or tier == "past_lifespan":
        priority = "MEDIUM"
    else:
        priority = "LOW"   # newer/unknown and no recent storm = no current reason

    return Candidate(
        pin=attrs.get("PIN", ""),
        owner=attrs.get("OWNER", ""),
        address=format_address(attrs),
        lat=lat, lon=lon,
        year_built=yr,
        building_age=age,
        age_tier=tier,
        storm_exposed=storm.exposed,
        nearest_storm_mi=storm.nearest_mi,
        worst_hail_in=storm.worst_hail_in,
        worst_wind_kt=storm.worst_wind_kt,
        last_storm_day=storm.last_storm_day,
        priority=priority,
        reasons=reasons,
        auditor_link=attrs.get("AuditorLink", "") or "",
    )
