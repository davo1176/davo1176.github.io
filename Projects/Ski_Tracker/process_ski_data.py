"""
Epic Pass Ski Data Processor
Reads raw JSON from the Vail Resorts API and outputs a clean CSV.
No external dependencies -- uses only Python standard library.

Usage:
    cd Projects/Ski_Tracker
    python process_ski_data.py
"""

import json
import csv
from datetime import datetime

# Resort ID mapping (confirmed by user)
RESORT_MAP = {
    (1, 15): "Vail",
    (2, 3): "Breckenridge",
    (3, 4): "Keystone",
    (4, 8): "Beaver Creek",
}

INPUT_FILE = "ski_day_data.json"
OUTPUT_FILE = "ski_data.csv"


def get_resort_name(record):
    key = (record["resortId"], record["myEpicResortId"])
    return RESORT_MAP.get(key, f"Unknown ({key})")


def get_season(dt):
    """Derive ski season label. Season runs Nov-Apr.
    A date in Jan-Apr belongs to the season that started the prior Nov."""
    if dt.month >= 11:
        return f"{dt.year}-{str(dt.year + 1)[-2:]}"
    else:
        return f"{dt.year - 1}-{str(dt.year)[-2:]}"


def process():
    with open(INPUT_FILE, "r") as f:
        records = json.load(f)

    rows = []
    for r in records:
        date_str = r["createdTimestampUtc"]
        dt = datetime.fromisoformat(date_str.replace("Z", ""))

        gps = r.get("gpsStats") or {}

        rows.append({
            "date": dt.strftime("%Y-%m-%d"),
            "year": dt.year,
            "month": dt.month,
            "day_of_week": dt.strftime("%A"),
            "season": get_season(dt),
            "resort": get_resort_name(r),
            "resort_id": r["resortId"],
            "vertical_feet": r["verticalInFeet"],
            "vertical_meters": r["verticalInMeters"],
            "lift_rides": r["liftRides"],
            "has_gps": bool(r.get("gpsStats")),
            "gps_distance_km": gps.get("distanceKilometers", ""),
            "gps_max_altitude_m": gps.get("altitudeMaxMeters", ""),
            "gps_duration_seconds": gps.get("durationSeconds", ""),
            "gps_max_speed_kph": gps.get("maxSpeedKph", ""),
        })

    rows.sort(key=lambda x: x["date"])

    fieldnames = list(rows[0].keys())
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Print summary
    total_days = len(rows)
    total_vert = sum(r["vertical_feet"] for r in rows)
    total_lifts = sum(r["lift_rides"] for r in rows)
    best = max(rows, key=lambda r: r["vertical_feet"])
    seasons = sorted(set(r["season"] for r in rows))

    print(f"Processed {total_days} ski days across {len(seasons)} seasons")
    print(f"Seasons: {', '.join(seasons)}")
    print(f"Total vertical: {total_vert:,.0f} feet")
    print(f"Total lift rides: {total_lifts:,}")
    print()

    # Resort breakdown
    resort_counts = {}
    for r in rows:
        resort_counts[r["resort"]] = resort_counts.get(r["resort"], 0) + 1
    for resort, count in sorted(resort_counts.items(), key=lambda x: -x[1]):
        print(f"  {resort}: {count} days")

    print()
    print(f"Best day: {best['date']} at {best['resort']} — "
          f"{best['vertical_feet']:,} vertical feet, {best['lift_rides']} lift rides")
    print(f"\nOutput written to {OUTPUT_FILE}")


if __name__ == "__main__":
    process()
