"""
parcels.py — pull residential parcels from the county auditor's ArcGIS service.

This is public county property data. We use it only to build a list of
addresses to offer free inspections to. We deliberately do NOT pull or use any
market-value / income proxy for prioritization.
"""

import time
import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import (
    BUTLER_PARCEL_URL, PARCEL_SR_FEET, OUTPUT_SR_LATLON,
    SERVICE_AREA_BBOX, RESIDENTIAL_LUC,
)

PAGE_SIZE = 2000

# Fields pulled. Note: no value field — prioritization is by roof age and storm
# exposure only, never by ability to pay.
OUT_FIELDS = "PIN,OWNER,ADRNO,ADRSTR,ADRSUF,LOCATION,YRBLT,LUC,AuditorLink"


def _query_params(offset: int) -> dict:
    luc_list = ",".join(f"'{code}'" for code in RESIDENTIAL_LUC)
    b = SERVICE_AREA_BBOX
    return {
        "where": f"LUC IN ({luc_list})",
        "geometry": f"{b['xmin']},{b['ymin']},{b['xmax']},{b['ymax']}",
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": PARCEL_SR_FEET,
        "outFields": OUT_FIELDS,
        "returnGeometry": "true",
        "outSR": OUTPUT_SR_LATLON,   # ask the server to return rings as lon/lat
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "f": "json",
    }


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30))
def _fetch_page(offset: int) -> dict:
    resp = requests.get(BUTLER_PARCEL_URL, params=_query_params(offset), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"ArcGIS error: {data['error']}")
    return data


def fetch_residential_parcels() -> list[dict]:
    """Paginate the FeatureServer (max 2000/page) and return parcel features."""
    parcels, offset = [], 0
    while True:
        logger.info(f"Fetching parcels (offset={offset})")
        data = _fetch_page(offset)
        feats = data.get("features", [])
        if not feats:
            break
        parcels.extend(feats)
        logger.info(f"  +{len(feats)} (total {len(parcels)})")
        if not data.get("exceededTransferLimit"):
            break
        offset += PAGE_SIZE
        time.sleep(0.3)
    logger.success(f"Total residential parcels: {len(parcels)}")
    return parcels


def parcel_centroid_latlon(feature: dict):
    """
    Return (lat, lon) centroid of a parcel, or None.
    Geometry is already EPSG:4326 (we requested outSR=4326), so ring points are
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
