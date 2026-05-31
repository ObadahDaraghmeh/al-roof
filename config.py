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

# ── Parcel data sources (one per county; public auditor/GIS ArcGIS services) ──
# Every county GIS service names its fields differently, so each source maps the
# county's OWN field names onto the canonical keys this tool expects downstream:
#     PIN, OWNER, YRBLT, ADRNO, ADRSTR, ADRSUF, LOCATION, AuditorLink
#
# To add or verify a county, on a machine WITH internet run:
#     python3 inspect_service.py <FeatureServer-or-layer-URL>
# It prints the layer's field names + a sample record. Copy the real field names
# into that county's "map" below, set a residential "where" filter, enabled=True.

OUTPUT_SR_LATLON = 4326   # ask every service to RETURN geometry as lon/lat

# Service-area envelope in lon/lat (EPSG:4326), ~Cincinnati metro. Sent to every
# service with inSR=4326 so we don't need each county's native projection.
SERVICE_AREA_BBOX_LATLON = {
    "xmin": -84.85,   # west longitude
    "ymin":  39.05,   # south latitude
    "xmax": -84.15,   # east longitude
    "ymax":  39.65,   # north latitude
}

# ── Property-value floor (OPT-IN; reverses the original age/storm-only design) ─
# If this is a number AND a source maps a "VALUE" field, homes whose market
# value is below it are dropped from the list. Value is used ONLY to filter —
# never spoken to a homeowner; the honest pitch stays roof age + storm exposure.
# Set to None to restore the pure age/storm behavior.
MIN_PROPERTY_VALUE = 200000

SOURCES = [
    {
        "name": "Butler (Monroe)",
        "enabled": True,
        "url": (
            "https://services5.arcgis.com/ZpzXpUOckwsAhLFh/arcgis/rest/services"
            "/Monroe_Parcels_in_Butler_County/FeatureServer/2/query"
        ),
        # Confirmed working. This service is set up in EPSG:3735 (Ohio State
        # Plane South, US feet), so it keeps its original feet bbox.
        "in_sr": 3735,
        "bbox": {"xmin": 1390000, "ymin": 465000, "xmax": 1470000, "ymax": 540000},
        "where": "LUC IN ('510','511','512')",   # 510/511/512 = 1-3 family homes
        "out_fields": "PIN,OWNER,ADRNO,ADRSTR,ADRSUF,LOCATION,YRBLT,LUC,MKTVCurYr,AuditorLink",
        "map": {
            "PIN": "PIN", "OWNER": "OWNER", "YRBLT": "YRBLT",
            "ADRNO": "ADRNO", "ADRSTR": "ADRSTR", "ADRSUF": "ADRSUF",
            "LOCATION": "LOCATION", "AuditorLink": "AuditorLink",
            "VALUE": "MKTVCurYr",   # market value, current year (auditor)
        },
    },

    # ── Neighboring counties: SCAFFOLDED but DISABLED until verified. ──────────
    # Fill url + map (and a residential `where`) from inspect_service.py output,
    # then flip enabled=True. They share the lat/lon metro box with inSR=4326.
    {
        "name": "Warren (Mason/Lebanon)",
        "enabled": False,
        # Candidate (mirrored on Butler's auditor host) — confirm the layer id:
        #   https://maps.butlercountyauditor.org/arcgis/rest/services/WarrenCounty/MapServer
        "url": "",                       # e.g. ".../WarrenCounty/MapServer/<id>/query"
        "in_sr": 4326,
        "bbox": SERVICE_AREA_BBOX_LATLON,
        "where": "1=1",                  # refine to residential once you see the codes
        "out_fields": "*",
        "map": {                         # ← fill the right side with real field names
            "PIN": "", "OWNER": "", "YRBLT": "",
            "ADRNO": "", "ADRSTR": "", "ADRSUF": "",
            "LOCATION": "", "AuditorLink": "",
        },
    },
    {
        "name": "Hamilton (Cincinnati)",
        "enabled": True,
        # Primary layer: parcel polygons joined to the auditor real-estate view
        # (market value, owner, address, land-use class). Year built is NOT in
        # this layer — it comes from the building-info layer via yrblt_join.
        "url": (
            "https://cagisonline.hamilton-co.org/arcgis/rest/services"
            "/COUNTYWIDE/HCE_Parcels_With_Auditor_Data/MapServer/0/query"
        ),
        "in_sr": 4326,
        "bbox": SERVICE_AREA_BBOX_LATLON,
        # Ohio residential land-use classes are the 500s; the value floor trims
        # vacant land and anything under $200k.
        "where": "CAGIS.AUDREAL_VW.CLASS >= 500 AND CAGIS.AUDREAL_VW.CLASS < 600",
        "out_fields": "*",
        "map": {
            "PIN": "HCE.ParcelFabric_Parcels.NAME",
            "OWNER": "CAGIS.AUDREAL_VW.OWNNM1",
            "YRBLT": "",                       # filled from yrblt_join below
            "ADRNO": "CAGIS.AUDREAL_VW.ADDRNO",
            "ADRSTR": "CAGIS.AUDREAL_VW.ADDRST",
            "ADRSUF": "CAGIS.AUDREAL_VW.ADDRSF",
            "LOCATION": "",
            "AuditorLink": "",
            "VALUE": "CAGIS.AUDREAL_VW.MKT_TOTAL_VAL",
        },
        # Year built lives in a separate building-info layer; look it up by
        # parcel id and attach it to each parcel.
        "yrblt_join": {
            "url": (
                "https://cagisonline.hamilton-co.org/arcgis/rest/services"
                "/COUNTYWIDE/AuditorParcelInformation/MapServer/17/query"
            ),
            "yrblt_field": "YEARBUILT",
            "secondary_keys": ["PID", "PARCELID", "PROPTYID", "AUDPTYID"],
            "primary_keys": [
                "HCE.ParcelFabric_Parcels.NAME",
                "CAGIS.AUDREAL_VW.PROPTYID",
                "CAGIS.AUDREAL_VW.AUDPTYID",
            ],
        },
    },
    {
        "name": "Montgomery (Dayton)",
        "enabled": False,
        "url": "",
        "in_sr": 4326,
        "bbox": SERVICE_AREA_BBOX_LATLON,
        "where": "1=1",
        "out_fields": "*",
        "map": {
            "PIN": "", "OWNER": "", "YRBLT": "",
            "ADRNO": "", "ADRSTR": "", "ADRSUF": "",
            "LOCATION": "", "AuditorLink": "",
        },
    },
]

# Approximate center of your service area in (lat, lon). Used only to discard
# storm reports from the rest of the country before matching. Cincinnati, OH:
SERVICE_AREA_CENTER_LATLON = (39.10, -84.51)
STORM_REGION_RADIUS_MI     = 50

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

STORM_LOOKBACK_DAYS    = 365    # how far back to pull reports (full year = catches the hail season)
HAIL_DAMAGE_MIN_INCHES = 1.0    # 1.0"+ is the usual roof-damage threshold
WIND_DAMAGE_MIN_KNOTS  = 50     # official NWS severe-wind threshold (~58 mph)
STORM_MATCH_RADIUS_MI  = 3.0    # flag a parcel within this distance of a report

# ── Output ────────────────────────────────────────────────────────────────────
DB_PATH        = "inspection_candidates.db"
TOP_N_PRINTED  = 25
