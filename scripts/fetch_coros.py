"""
COROS Training Hub Data Fetcher
Logs in to the unofficial COROS Training Hub API, fetches activities
and training analytics (resting HR, training load, fatigue, fitness).

No external dependencies -- uses only Python standard library.

Usage (local):
    export COROS_EMAIL=your_email
    export COROS_PASSWORD_MD5=your_md5_hashed_password
    python scripts/fetch_coros.py

Usage (GitHub Actions):
    Secrets are passed as environment variables by the workflow.
"""

import json
import os
import ssl
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta


COROS_LOGIN_URL = "https://teamapi.coros.com/account/login"
COROS_ACTIVITIES_URL = "https://teamapi.coros.com/activity/query"
COROS_ANALYSE_URL = "https://teamapi.coros.com/analyse/query"

OUTPUT_JSON = "data/coros_data.json"
PER_PAGE = 200

# SSL context -- use default verification in CI, allow unverified locally
# (Proxyman or other dev proxies can cause SSL cert issues)
SSL_CTX = None
if os.environ.get("CI"):
    SSL_CTX = None  # Use default SSL verification in GitHub Actions
else:
    SSL_CTX = ssl.create_default_context()
    SSL_CTX.check_hostname = False
    SSL_CTX.verify_mode = ssl.CERT_NONE


# Sport type mapping from COROS numeric codes
SPORT_TYPES = {
    100: "Run",
    101: "Indoor Run",
    102: "Trail Run",
    104: "Track Run",
    200: "Bike",
    201: "Indoor Bike",
    300: "Pool Swim",
    301: "Open Water Swim",
    400: "Strength",
    401: "Gym Cardio",
    402: "Yoga",
    500: "Ski",
    501: "Snowboard",
    700: "Hike",
    800: "Multisport",
    900: "Walk",
    10000: "GPS Cardio",
    10001: "Rowing",
    10002: "Flatwater",
    10003: "Outdoor Climb",
    10004: "Windsport",
    10100: "Jump Rope",
}


def login():
    """Log in to COROS Training Hub and return access token + user ID."""
    email = os.environ["COROS_EMAIL"]
    password_md5 = os.environ["COROS_PASSWORD_MD5"]

    payload = json.dumps({
        "account": email,
        "accountType": 2,
        "pwd": password_md5,
    }).encode("utf-8")

    req = urllib.request.Request(
        COROS_LOGIN_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(req, context=SSL_CTX) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    access_token = result["data"]["accessToken"]
    user_id = str(result["data"]["userId"])
    print(f"Logged in. Token: {access_token[:8]}... User: {user_id}")
    return access_token, user_id


def api_get(url, access_token, user_id):
    """Make an authenticated GET request to the COROS API."""
    req = urllib.request.Request(url)
    req.add_header("accesstoken", access_token)
    req.add_header("Accept", "application/json")
    req.add_header("Origin", "https://t.coros.com")
    req.add_header("Referer", "https://t.coros.com/")
    req.add_header("yfheader", json.dumps({"userId": user_id}))

    with urllib.request.urlopen(req, context=SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_activities(access_token, user_id):
    """Fetch all activities from COROS, paginating through results."""
    all_activities = []
    page = 1

    while True:
        url = f"{COROS_ACTIVITIES_URL}?size={PER_PAGE}&pageNumber={page}&modeList="
        result = api_get(url, access_token, user_id)

        batch = result.get("data", {}).get("dataList", [])
        if not batch:
            break

        all_activities.extend(batch)
        print(f"  Page {page}: {len(batch)} activities")
        page += 1
        time.sleep(0.5)

    print(f"Total activities fetched: {len(all_activities)}")
    return all_activities


def fetch_training_data(access_token, user_id):
    """Fetch training analytics (resting HR, training load, fatigue, fitness)."""
    result = api_get(COROS_ANALYSE_URL, access_token, user_id)
    day_list = result.get("data", {}).get("dayList", [])
    print(f"Training data: {len(day_list)} days")
    return day_list


def format_date(coros_date):
    """Convert COROS date format (20260206) to ISO format (2026-02-06)."""
    s = str(coros_date)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def pace_from_seconds_per_km(pace_sec):
    """Convert COROS pace (seconds per km) to min/mile string."""
    if not pace_sec or pace_sec <= 0:
        return None
    # COROS stores pace as seconds per km
    sec_per_mile = pace_sec * 1.60934
    mins = int(sec_per_mile // 60)
    secs = int(sec_per_mile % 60)
    return f"{mins}:{secs:02d}"


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


def meters_to_miles(m):
    return round(m * 0.000621371, 2)


def meters_to_feet(m):
    return round(m * 3.28084)


def process_activity(raw):
    """Transform a raw COROS activity into our schema."""
    date_str = format_date(raw.get("date", 0))
    dt = datetime.fromisoformat(date_str) if date_str != "0000-00-00" else None
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    sport_code = raw.get("sportType", 0)
    sport_name = SPORT_TYPES.get(sport_code, f"Other ({sport_code})")
    distance_m = raw.get("distance", 0)
    distance_miles = meters_to_miles(distance_m)
    distance_km = round(distance_m / 1000, 2)
    moving_time = raw.get("workoutTime", raw.get("totalTime", 0))
    avg_pace_sec = raw.get("avgSpeed", 0)  # seconds per km in COROS

    # Only compute pace for running activities
    avg_pace = None
    if sport_code in (100, 101, 102, 104):
        avg_pace = pace_from_seconds_per_km(avg_pace_sec)

    return {
        "label_id": raw.get("labelId", ""),
        "name": raw.get("name", ""),
        "type": sport_name,
        "sport_code": sport_code,
        "date": date_str,
        "year": dt.year if dt else None,
        "month": dt.month if dt else None,
        "day_of_week": days[dt.weekday()] if dt else None,
        "distance_miles": distance_miles,
        "distance_km": distance_km,
        "moving_time_seconds": moving_time,
        "moving_time_display": seconds_to_display(moving_time),
        "elevation_feet": meters_to_feet(raw.get("ascent", 0)),
        "elevation_meters": round(raw.get("ascent", 0), 1),
        "average_heartrate": raw.get("avgHr", None),
        "average_pace_min_mile": avg_pace,
        "cadence": raw.get("avgCadence", None),
        "calories": round(raw.get("calorie", 0) / 1000) if raw.get("calorie") else 0,
        "training_load": raw.get("trainingLoad", 0),
        "device": raw.get("device", ""),
    }


def process_training_day(raw):
    """Transform a raw training analytics day into our schema."""
    date_str = format_date(raw.get("happenDay", 0))
    return {
        "date": date_str,
        "resting_hr": raw.get("rhr", None),
        "test_resting_hr": raw.get("testRhr", None),
        "training_load": raw.get("trainingLoad", 0),
        "fatigue_rate": raw.get("tiredRate", None),
        "fatigue_rate_new": raw.get("tiredRateNew", None),
        "base_fitness": raw.get("tib", None),
        "acute_load": raw.get("ati", None),
        "chronic_load": raw.get("cti", None),
        "training_load_ratio": raw.get("trainingLoadRatio", None),
    }


def compute_stats(activities):
    """Compute aggregate statistics from processed activities."""
    total_distance = sum(a["distance_miles"] for a in activities)
    total_elevation = sum(a["elevation_feet"] for a in activities)
    total_time = sum(a["moving_time_seconds"] for a in activities)
    total_calories = sum(a["calories"] for a in activities)

    return {
        "total_activities": len(activities),
        "total_distance_miles": round(total_distance, 1),
        "total_elevation_feet": total_elevation,
        "total_moving_time_seconds": total_time,
        "total_moving_time_display": seconds_to_display(total_time),
        "total_calories": total_calories,
    }


def main():
    print("=== COROS Training Hub Data Fetcher ===\n")

    # Step 1: Login
    print("Logging in...")
    access_token, user_id = login()

    # Step 2: Fetch activities
    print("\nFetching activities...")
    raw_activities = fetch_activities(access_token, user_id)

    # Step 3: Fetch training analytics
    print("\nFetching training analytics...")
    raw_training = fetch_training_data(access_token, user_id)

    # Step 4: Process data
    print("\nProcessing data...")
    activities = [process_activity(r) for r in raw_activities]
    activities.sort(key=lambda a: a["date"] or "")

    training_days = [process_training_day(r) for r in raw_training]
    training_days.sort(key=lambda d: d["date"])

    # Step 5: Compute stats
    stats = compute_stats(activities)

    # Step 6: Write JSON output
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "coros_training_hub",
        "athlete_stats": stats,
        "activities": activities,
        "training_days": training_days,
    }

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)

    # Print summary
    print(f"\nProcessed {stats['total_activities']} activities")
    print(f"Total distance: {stats['total_distance_miles']} miles")
    print(f"Total elevation: {stats['total_elevation_feet']:,} feet")
    print(f"Total moving time: {stats['total_moving_time_display']}")
    print(f"Training analytics: {len(training_days)} days")

    # Type breakdown
    type_counts = {}
    for a in activities:
        type_counts[a["type"]] = type_counts.get(a["type"], 0) + 1
    print("\nActivity types:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")

    print(f"\nOutput written to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
