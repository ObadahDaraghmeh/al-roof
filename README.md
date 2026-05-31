# Roof Inspection Outreach List

Builds a prioritized canvassing list for a roofing business to **offer free,
no-obligation roof inspections** in a service area. It ranks addresses by two
signals that actually predict roof need:

1. **Roof age** — building age from the county auditor's `YRBLT` field, used as
   a proxy for roof age. Asphalt shingle roofs typically last 20–30 years.
2. **Recent severe-storm exposure** — public NOAA Storm Prediction Center hail
   and wind reports near each parcel in the last few months.

## What it deliberately does NOT do

- **No "damage score."** It never looks at a roof and never asserts a roof is
  damaged. A human inspects the roof before anyone says anything about its
  condition. The priority column means "good candidate to *offer* an
  inspection," nothing more.
- **No income / property-value targeting.** Market value is never fetched and
  never used to prioritize. Doors are ranked by roof age and storm exposure
  only.
- **No aerial-imagery CV.** The previous version scored roofs off 2019 aerial
  imagery with classical CV that mostly detected algae streaks, shade, and
  shadows — not damage. That whole path is gone. (If you want imagery, it
  belongs in front of a *person* for manual review, never feeding an automated
  damage claim, and it must be current, not 7-year-old pictures.)

## How priority is assigned

| Roof age tier        | Recent severe storm nearby? | Priority |
|----------------------|-----------------------------|----------|
| past_lifespan (25+)  | yes                         | HIGH     |
| approaching (15–24)  | yes                         | HIGH     |
| any                  | yes                         | MEDIUM   |
| past_lifespan (25+)  | no                          | MEDIUM   |
| newer / unknown      | no                          | LOW      |

`LOW` just means there's no current reason to prioritize that address.

## Run

```bash
pip install -r requirements.txt
python main.py
```

Outputs:

- `inspection_candidates.db` — all scored parcels (SQLite)
- `inspection_candidates.csv` — the actionable list (HIGH + MEDIUM)
- a ranked summary printed to the console

## Configure

Everything is in `config.py`:

- `SERVICE_AREA_BBOX` and `SERVICE_AREA_CENTER_LATLON` — where you work
- `ROOF_AGE_*` — age thresholds
- `HAIL_DAMAGE_MIN_INCHES`, `WIND_DAMAGE_MIN_KNOTS`, `STORM_MATCH_RADIUS_MI`,
  `STORM_LOOKBACK_DAYS` — storm sensitivity

## Data sources

- **Parcels:** Butler County auditor parcels via ArcGIS FeatureServer (public).
  Confirm the layer is live before a run; if zero parcels return, check whether
  `LUC` is stored as text (quoted, as here) or numeric.
- **Storms:** SPC daily filtered reports,
  `https://www.spc.noaa.gov/climo/reports/{YYMMDD}_rpts_hail.csv` and
  `..._rpts_wind.csv`. For an authoritative historical archive instead of the
  recent-only daily files, swap in the NCEI Storm Events Database bulk CSVs.

## Using the list responsibly

This tool produces leads, not findings. When you contact someone, the honest
pitch is an *offer* ("we're inspecting roofs in your area after the recent
storm — want a free check?"), not a *claim* ("our analysis shows your roof is
damaged"). Asserting damage you haven't verified, to drive a sale, is exactly
what storm-chasing statutes, contractor-licensing rules, and insurance-fraud
laws target. Several states also require a written right-to-cancel window on
storm-restoration contracts. Check the rules for the states you operate in.
This is general information, not legal advice — confirm specifics with a lawyer
who knows your jurisdiction.
