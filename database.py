"""
database.py — store outreach candidates in a local SQLite file + CSV export.
"""

import csv
import sqlite3
import json
from loguru import logger

from config import DB_PATH
from scoring import Candidate


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS inspection_candidates (
            pin                TEXT PRIMARY KEY,
            owner              TEXT,
            address            TEXT,
            lat                REAL,
            lon                REAL,
            year_built         INTEGER,
            building_age       INTEGER,
            age_tier           TEXT,
            storm_exposed      INTEGER,
            nearest_storm_mi   REAL,
            worst_hail_in      REAL,
            worst_wind_kt      REAL,
            last_storm_day     TEXT,
            priority           TEXT,
            reasons            TEXT,
            recommended_action TEXT,
            auditor_link       TEXT,
            updated_at         DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    con.close()
    logger.info(f"DB ready at {DB_PATH}")


def upsert(c: Candidate):
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT INTO inspection_candidates
            (pin, owner, address, lat, lon, year_built, building_age, age_tier,
             storm_exposed, nearest_storm_mi, worst_hail_in, worst_wind_kt,
             last_storm_day, priority, reasons, recommended_action, auditor_link,
             updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(pin) DO UPDATE SET
            priority         = excluded.priority,
            storm_exposed    = excluded.storm_exposed,
            nearest_storm_mi = excluded.nearest_storm_mi,
            worst_hail_in    = excluded.worst_hail_in,
            worst_wind_kt    = excluded.worst_wind_kt,
            last_storm_day   = excluded.last_storm_day,
            reasons          = excluded.reasons,
            updated_at       = CURRENT_TIMESTAMP
    """, (
        c.pin, c.owner, c.address, c.lat, c.lon, c.year_built, c.building_age,
        c.age_tier, int(c.storm_exposed), c.nearest_storm_mi, c.worst_hail_in,
        c.worst_wind_kt,
        c.last_storm_day.isoformat() if c.last_storm_day else None,
        c.priority, json.dumps(c.reasons), c.recommended_action, c.auditor_link,
    ))
    con.commit()
    con.close()


_ORDER = """
    ORDER BY
        CASE priority WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END,
        storm_exposed DESC,
        building_age DESC
"""


def top_candidates(n: int = 25) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.execute(f"SELECT * FROM inspection_candidates {_ORDER} LIMIT ?", (n,))
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows


def export_csv(path: str = "inspection_candidates.csv", actionable_only: bool = True):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    where = "WHERE priority IN ('HIGH','MEDIUM')" if actionable_only else ""
    cur = con.execute(f"""
        SELECT address, owner, priority, age_tier, building_age, year_built,
               storm_exposed, worst_hail_in, worst_wind_kt, nearest_storm_mi,
               last_storm_day, recommended_action, auditor_link, pin
        FROM inspection_candidates {where} {_ORDER}
    """)
    rows = cur.fetchall()
    cols = list(rows[0].keys()) if rows else []
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        if cols:
            w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])
    con.close()
    logger.success(f"Exported {len(rows)} rows to {path}")
    return path
