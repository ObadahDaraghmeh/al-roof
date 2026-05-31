"""
main.py — build a free-inspection canvassing list for a roofing business.

Run:  python main.py

Pipeline:
    1. Pull residential parcels in your service area      (public county data)
    2. Pull recent severe-storm reports near your area    (public NOAA/SPC data)
    3. For each parcel: roof-age tier + storm exposure
    4. Assign an OUTREACH priority (HIGH/MEDIUM/LOW) and store it
    5. Print + export the ranked list

The result is a list of doors to knock with a FREE INSPECTION offer. It is not,
and is not meant to be, a claim that any given roof is damaged.
"""

from loguru import logger
from tqdm import tqdm

import parcels
import storms
import scoring
import database
from config import TOP_N_PRINTED


def run():
    logger.info("=== Roof inspection outreach list — build starting ===")
    database.init_db()

    logger.info("Step 1 - residential parcels in service area")
    feats = parcels.fetch_residential_parcels()

    logger.info("Step 2 - recent severe-storm reports near service area")
    storm_reports = storms.fetch_recent_storms()

    logger.info("Step 3 - scoring parcels (roof age + storm exposure)")
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for feat in tqdm(feats, desc="Parcels"):
        centroid = parcels.parcel_centroid_latlon(feat)
        if centroid:
            match = storms.match_parcel(centroid[0], centroid[1], storm_reports)
        else:
            match = storms.StormMatch(False, None, 0.0, 0.0, None)
        candidate = scoring.score(feat, match)
        database.upsert(candidate)
        counts[candidate.priority] += 1

    logger.success(
        f"Scored {len(feats)} parcels - "
        f"HIGH={counts['HIGH']} MEDIUM={counts['MEDIUM']} LOW={counts['LOW']}"
    )

    print("\n" + "=" * 78)
    print(" ROOF INSPECTION OUTREACH LIST  -  offer FREE inspections only")
    print(" Do not tell anyone their roof is damaged before a person inspects it.")
    print("=" * 78)
    for i, c in enumerate(database.top_candidates(TOP_N_PRINTED), 1):
        print(f"\n{i:>2}. [{c['priority']:<6}] {c['address']}   (PIN {c['pin']})")
        if c["owner"]:
            print(f"      Owner: {c['owner']}")
        if c["building_age"] is not None:
            print(f"      Built {c['year_built']} (~{c['building_age']} yrs)   tier={c['age_tier']}")
        if c["storm_exposed"]:
            sev = []
            if c["worst_hail_in"]:
                sev.append(f'{c["worst_hail_in"]:.2f}" hail')
            if c["worst_wind_kt"]:
                sev.append(f'{c["worst_wind_kt"]:.0f} kt wind')
            detail = ', '.join(sev) or 'wind damage reported (no measured speed)'
            print(f"      Storm: {detail} within {c['nearest_storm_mi']} mi (last {c['last_storm_day']})")
        print(f"      Action: {c['recommended_action']}")
        if c["auditor_link"]:
            print(f"      Auditor: {c['auditor_link']}")

    path = database.export_csv()
    print(f"\nActionable list (HIGH + MEDIUM) exported to: {path}")
    logger.success("Done.")


if __name__ == "__main__":
    run()
