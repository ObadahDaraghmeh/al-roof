"""
parcels.py — pull residential parcels from one or more county GIS services.

This is public county property data. We use it only to build a list of
addresses to offer free inspections to. We deliberately do NOT pull or use any
market-value / income proxy for prioritization.

Each county (see SOURCES in config.py) names its fields differently, so we
normalize every county's raw attributes onto the canonical keys the rest of the
tool expects: PIN, OWNER, YRBLT, ADRNO, ADRSTR, ADRSUF, LOCATION, AuditorLink.
"""

import time
import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import SOURCES, OUTPUT_SR_LATLON, MIN_PROPERTY_VALUE

PAGE_SIZE = 2000

CANONICAL_FIELDS = (
    "PIN", "OWNER", "YRBLT", "ADRNO", "ADRSTR", "ADRSUF", "LOCATION",
    "AuditorLink", "VALUE",
)


def _value_of(feature: dict):
    v = (feature.get("attributes") or {}).get("VALUE")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _query_params(source: dict, offset: int) -> dict:
    b = source["bbox"]
    return {
        "where": source.get("where", "1=1"),
        "geometry": f"{b['xmin']},{b['ymin']},{b['xmax']},{b['ymax']}",
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": source.get("in_sr", OUTPUT_SR_LATLON),
        "outFields": source.get("out_fields", "*"),
        "returnGeometry": "true",
        "outSR": OUTPUT_SR_LATLON,   # rings come back as lon/lat for storm matching
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "f": "json",
    }


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30))
def _fetch_page(source: dict, offset: int) -> dict:
    resp = requests.get(source["url"], params=_query_params(source, offset), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"ArcGIS error from {source['name']}: {data['error']}")
    return data


def _normalize(feature: dict, fieldmap: dict) -> dict:
    """Rewrite a feature's attributes to the canonical keys using the county map."""
    raw = feature.get("attributes", {}) or {}
    attrs = {}
    for canonical in CANONICAL_FIELDS:
        county_field = fieldmap.get(canonical) or ""
        attrs[canonical] = raw.get(county_field) if county_field else None
    feature["attributes"] = attrs
    return feature


def _fetch_source(source: dict) -> list[dict]:
    feats, offset = [], 0
    while True:
        logger.info(f"  fetching {source['name']} (offset={offset})")
        data = _fetch_page(source, offset)
        page = data.get("features", [])
        if not page:
            break
        feats.extend(_normalize(f, source["map"]) for f in page)
        logger.info(f"    +{len(page)} ({source['name']} total {len(feats)})")
        if not data.get("exceededTransferLimit"):
            break
        offset += PAGE_SIZE
        time.sleep(0.3)

    # Optional property-value floor (opt-in; see MIN_PROPERTY_VALUE in config).
    if MIN_PROPERTY_VALUE is not None and source["map"].get("VALUE"):
        before = len(feats)
        feats = [f for f in feats
                 if (_value_of(f) is not None and _value_of(f) >= MIN_PROPERTY_VALUE)]
        logger.info(
            f"  {source['name']}: value floor ${MIN_PROPERTY_VALUE:,.0f} "
            f"kept {len(feats)}, dropped {before - len(feats)} "
            f"(below floor or no value on record)"
        )

    logger.success(f"  {source['name']}: {len(feats)} parcels")
    return feats


def fetch_residential_parcels() -> list[dict]:
    """Pull residential parcels from every ENABLED source and combine them."""
    all_feats: list[dict] = []
    enabled = [s for s in SOURCES if s.get("enabled")]
    if not enabled:
        logger.warning("No enabled parcel sources in config.SOURCES")
    for source in enabled:
        if not source.get("url"):
            logger.warning(f"Source '{source['name']}' is enabled but has no url; skipping")
            continue
        all_feats.extend(_fetch_source(source))
    logger.success(f"Total residential parcels (all sources): {len(all_feats)}")
    return all_feats


def parcel_centroid_latlon(feature: dict):
    """
    Return (lat, lon) centroid of a parcel, or None.
    Geometry is EPSG:4326 (we requested outSR=4326), so ring points are
    [lon, lat]. A vertex-average centroid is plenty accurate for a "within N
    miles of a storm" test.
    """
    geom = feature.get("geometry") or {}
    rings = geom.get("rings")
    if not rings:
        return None
    xs = [pt[0] for ring in rings for pt in ring]  # lon
    ys = [pt[1] for ring in rings for pt in ring]  # lat
    if not xs or not ys:
        return None
    return (sum(ys) / len(ys), sum(xs) / len(xs))


def format_address(attrs: dict) -> str:
    parts = [
        str(attrs.get("ADRNO") or "").strip(),
        str(attrs.get("ADRSTR") or "").strip(),
        str(attrs.get("ADRSUF") or "").strip(),
    ]
    addr = " ".join(p for p in parts if p)
    return addr or (attrs.get("LOCATION") or "").strip()
