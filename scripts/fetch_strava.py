"""
Strava Activity Fetcher
Refreshes OAuth token, fetches all activities from the Strava API,
processes them into analysis-ready JSON for the dashboard.

No external dependencies -- uses only Python standard library.

Usage (local):
    export STRAVA_CLIENT_ID=201170
    export STRAVA_CLIENT_SECRET=your_secret
    export STRAVA_REFRESH_TOKEN=your_refresh_token
    python scripts/fetch_strava.py

Usage (GitHub Actions):
    Secrets are passed as environment variables by the workflow.
    The script also updates the STRAVA_REFRESH_TOKEN secret via gh CLI.
"""

import csv
import json
import os
import subprocess
import time
import urllib.request
import urllib.parse
from datetime import datetime


STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
OUTPUT_JSON = "data/strava_activities.json"
OUTPUT_CSV = "data/strava_activities.csv"
PER_PAGE = 200


def refresh_token():
    """Exchange the refresh token for a new access token."""
    client_id = os.environ["STRAVA_CLIENT_ID"]
    client_secret = os.environ["STRAVA_CLIENT_SECRET"]
    refresh_tok = os.environ["STRAVA_REFRESH_TOKEN"]

    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_tok,
    }).encode("utf-8")

    req = urllib.request.Request(STRAVA_TOKEN_URL, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    access_token = result["access_token"]
    new_refresh_token = result["refresh_token"]
    expires_at = result["expires_at"]

    print(f"Token refreshed. Expires at: {datetime.fromtimestamp(expires_at, tz=None).isoformat()}Z")

    # Update the GitHub Actions secret if running in CI
    if os.environ.get("GH_PAT") and os.environ.get("GH_REPO"):
        update_secret(new_refresh_token)
    else:
        print(f"Not in CI -- new refresh token: {new_refresh_token[:8]}...")

    return access_token


def update_secret(new_refresh_token):
    """Update the STRAVA_REFRESH_TOKEN GitHub Actions secret using gh CLI."""
    print("Updating STRAVA_REFRESH_TOKEN secret via gh CLI...")
    env = {**os.environ, "GH_TOKEN": os.environ["GH_PAT"]}
    result = subprocess.run(
        ["gh", "secret", "set", "STRAVA_REFRESH_TOKEN",
         "--repo", os.environ["GH_REPO"],
         "--body", new_refresh_token],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to update secret: {result.stderr}")
    print("Secret updated successfully.")


def fetch_activities(access_token):
    """Fetch all activities from Strava, paginating through results."""
    all_activities = []
    page = 1

    while True:
        url = f"{STRAVA_ACTIVITIES_URL}?per_page={PER_PAGE}&page={page}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {access_token}")

        with urllib.request.urlopen(req) as resp:
            batch = json.loads(resp.read().decode("utf-8"))

        if not batch:
            break

        all_activities.extend(batch)
        print(f"  Page {page}: {len(batch)} activities")
        page += 1

        # Courtesy sleep between requests
        time.sleep(0.5)

    print(f"Total activities fetched: {len(all_activities)}")
    return all_activities


def meters_to_miles(m):
    return round(m * 0.000621371, 2)


def meters_to_feet(m):
    return round(m * 3.28084)


def mps_to_mph(mps):
    return round(mps * 2.23694, 1)


def seconds_to_display(seconds):
    """Convert seconds to human-readable display string."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def pace_from_mps(speed_mps):
    """Convert m/s to min/mile pace string (e.g., '8:30')."""
    if not speed_mps or speed_mps <= 0:
        return None
    mph = speed_mps * 2.23694
    if mph <= 0:
        return None
    min_per_mile = 60.0 / mph
    mins = int(min_per_mile)
    secs = int((min_per_mile - mins) * 60)
    return f"{mins}:{secs:02d}"


def get_day_of_week(date_str):
    """Get day of week name from ISO date string."""
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00").split("T")[0])
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[dt.weekday()]


def process_activity(raw):
    """Transform a raw Strava activity into our schema."""
    date_str = raw.get("start_date_local", raw.get("start_date", ""))
    date_only = date_str.split("T")[0] if "T" in date_str else date_str
    dt = datetime.fromisoformat(date_only) if date_only else None

    distance_miles = meters_to_miles(raw.get("distance", 0))
    distance_km = round(raw.get("distance", 0) / 1000, 2)
    elevation_feet = meters_to_feet(raw.get("total_elevation_gain", 0))
    elevation_meters = round(raw.get("total_elevation_gain", 0), 1)
    moving_time = raw.get("moving_time", 0)
    avg_speed = raw.get("average_speed", 0)
    max_speed = raw.get("max_speed", 0)
    activity_type = raw.get("type", "Unknown")

    # Only compute pace for running activities
    avg_pace = None
    if activity_type in ("Run", "VirtualRun", "TrailRun"):
        avg_pace = pace_from_mps(avg_speed)

    return {
        "id": raw.get("id"),
        "name": raw.get("name", ""),
        "type": activity_type,
        "sport_type": raw.get("sport_type", activity_type),
        "date": date_only,
        "year": dt.year if dt else None,
        "month": dt.month if dt else None,
        "day_of_week": get_day_of_week(date_only) if date_only else None,
        "distance_miles": distance_miles,
        "distance_km": distance_km,
        "moving_time_seconds": moving_time,
        "moving_time_display": seconds_to_display(moving_time),
        "elevation_feet": elevation_feet,
        "elevation_meters": elevation_meters,
        "average_speed_mph": mps_to_mph(avg_speed),
        "average_pace_min_mile": avg_pace,
        "max_speed_mph": mps_to_mph(max_speed),
        "has_heartrate": raw.get("has_heartrate", False),
        "average_heartrate": raw.get("average_heartrate"),
        "max_heartrate": raw.get("max_heartrate"),
        "kudos_count": raw.get("kudos_count", 0),
    }


def compute_stats(activities):
    """Compute aggregate statistics from processed activities."""
    total_distance = sum(a["distance_miles"] for a in activities)
    total_elevation = sum(a["elevation_feet"] for a in activities)
    total_time = sum(a["moving_time_seconds"] for a in activities)

    return {
        "total_activities": len(activities),
        "total_distance_miles": round(total_distance, 1),
        "total_elevation_feet": total_elevation,
        "total_moving_time_seconds": total_time,
        "total_moving_time_display": seconds_to_display(total_time),
    }


def find_best_activity(activities):
    """Find the activity with the longest distance."""
    if not activities:
        return None
    best = max(activities, key=lambda a: a["distance_miles"])
    return {
        "name": best["name"],
        "type": best["type"],
        "date": best["date"],
        "distance_miles": best["distance_miles"],
        "elevation_feet": best["elevation_feet"],
        "moving_time_display": best["moving_time_display"],
    }


def write_csv(activities):
    """Write all activities to a CSV file for data archival."""
    if not activities:
        return

    fieldnames = [
        "id", "date", "name", "type", "sport_type", "day_of_week",
        "distance_miles", "distance_km", "moving_time_seconds",
        "moving_time_display", "elevation_feet", "elevation_meters",
        "average_speed_mph", "average_pace_min_mile", "max_speed_mph",
        "has_heartrate", "average_heartrate", "max_heartrate", "kudos_count",
    ]

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(activities)

    print(f"CSV written: {len(activities)} rows to {OUTPUT_CSV}")


def main():
    print("=== Strava Activity Fetcher ===\n")

    # Step 1: Refresh token
    print("Refreshing access token...")
    access_token = refresh_token()

    # Step 2: Fetch all activities
    print("\nFetching activities...")
    raw_activities = fetch_activities(access_token)

    # Step 3: Process activities
    print("\nProcessing activities...")
    activities = [process_activity(r) for r in raw_activities]
    activities.sort(key=lambda a: a["date"] or "")

    # Step 4: Compute stats
    stats = compute_stats(activities)
    best = find_best_activity(activities)

    # Step 5: Write JSON output (for the dashboard)
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "athlete_stats": stats,
        "best_activity": best,
        "activities": activities,
    }

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)

    # Step 6: Write CSV output (for data archival)
    write_csv(activities)

    # Print summary
    print(f"\nProcessed {stats['total_activities']} activities")
    print(f"Total distance: {stats['total_distance_miles']} miles")
    print(f"Total elevation: {formatnum(stats['total_elevation_feet'])} feet")
    print(f"Total moving time: {stats['total_moving_time_display']}")

    if best:
        print(f"\nBest activity: {best['name']} ({best['type']})")
        print(f"  {best['distance_miles']} miles, {best['elevation_feet']} ft, {best['moving_time_display']}")

    # Type breakdown
    type_counts = {}
    for a in activities:
        type_counts[a["type"]] = type_counts.get(a["type"], 0) + 1
    print("\nActivity types:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")

    print(f"\nOutput written to {OUTPUT_JSON} and {OUTPUT_CSV}")


def formatnum(n):
    return f"{n:,}"


if __name__ == "__main__":
    main()
