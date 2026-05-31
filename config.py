"""
config.py — settings for the roof-replacement OUTREACH tool.

What this tool is:
    It builds a CANVASSING LIST for offering FREE, NO-OBLIGATION roof
    inspections. It prioritizes addresses using two honest, defensible signals:
        1. Building age   (a proxy for roof age, from the county YRBLT field)
        2. Recent severe-storm exposure (public NOAA / SPC hail & wind reports)

What this tool is NOT:
    It does not look at roofs and it does not decide a roof is damaged. A
    human inspects the roof before anyone says anything about its condition.
    There is deliberately no property-value / income input anywhere.
"""

# ── Butler County parcels (public county auditor data, served via ArcGIS) ─────
# Inherited from your existing setup. Confirm the layer is still live before a run.
BUTLER_PARCEL_URL = (
    "https://services5.arcgis.com/ZpzXpUOckwsAhLFh/arcgis/rest/services"
    "/Monroe_Parcels_in_Butler_County/FeatureServer/2/query"
)

# Parcel polygons are stored in EPSG:3735 (Ohio State Plane South, US feet).
# We send the service-area box in 3735 but ask the server to RETURN geometry
# in lat/lon (EPSG:4326) so parcel centroids compare directly to storm coords.
PARCEL_SR_FEET   = 3735
OUTPUT_SR_LATLON = 4326

# ── Service area (EPSG:3735 feet) ─────────────────────────────────────────────
# Default box ~ West Chester / Liberty Twp. Edit to match where you actually work.
SERVICE_AREA_BBOX = {
    "xmin": 1390000,
    "ymin": 465000,
    "xmax": 1470000,
    "ymax": 540000,
}

# Approximate center of your service area in (lat, lon). Used only to discard
# storm reports from the rest of the country before matching. Cincinnati, OH:
SERVICE_AREA_CENTER_LATLON = (39.10, -84.51)
STORM_REGION_RADIUS_MI     = 50

# Residential land-use codes: 510 single-family, 511 two-family, 512 three-family
RESIDENTIAL_LUC = ("510", "511", "512")

# ── Roof-age proxy ────────────────────────────────────────────────────────────
# Asphalt shingle roofs typically last ~20-30 yrs. Building age is only a PROXY
# for roof age — a re-roof resets the real clock, and county data won't show it.
CURRENT_YEAR                  = 2026
ROOF_AGE_LIKELY_PAST_LIFESPAN = 25   # yrs: original roof likely at/past end of life
ROOF_AGE_APPROACHING          = 15   # yrs: worth a courtesy inspection offer

# ── Storm exposure (public NOAA Storm Prediction Center reports) ──────────────
# SPC daily filtered reports, one file per day. Confirmed live. Columns:
#   hail: Time,Size,Location,County,State,Lat,Lon,Comments   (Size = 1/100 inch)
#   wind: Time,Speed,Location,County,State,Lat,Lon,Comments  (Speed = knots, or UNK)
SPC_REPORTS_BASE = "https://www.spc.noaa.gov/climo/reports"

STORM_LOOKBACK_DAYS    = 120    # how far back to pull reports
HAIL_DAMAGE_MIN_INCHES = 1.0    # 1.0"+ is the usual roof-damage threshold
WIND_DAMAGE_MIN_KNOTS  = 52     # ~60 mph; severe wind that can lift shingles
STORM_MATCH_RADIUS_MI  = 3.0    # flag a parcel within this distance of a report

# ── Output ────────────────────────────────────────────────────────────────────
DB_PATH        = "inspection_candidates.db"
TOP_N_PRINTED  = 25
