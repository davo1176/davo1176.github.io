"""
Hevy Workout Data Fetcher
Fetches workout data from the Hevy app's private API.

No external dependencies -- uses only Python standard library.

Usage (local):
    export HEVY_AUTH_TOKEN=your_auth_token
    python scripts/fetch_hevy.py

Usage (GitHub Actions):
    Secrets are passed as environment variables by the workflow.

Note: The auth token is a session token from the Hevy app.
      If it expires, log in to Hevy and capture a fresh token
      via Postman/browser dev tools, then update the GitHub secret.
"""

import json
import os
import ssl
import time
import urllib.request
from datetime import datetime

HEVY_API_URL = "https://api.hevyapp.com/user_workouts_paged"
HEVY_API_KEY = "klean_kanteen_insulated"
HEVY_USERNAME = "daboi420"

OUTPUT_JSON = "data/hevy_data.json"
PER_PAGE = 5  # Hevy API rejects limit > 5

# SSL context -- use default verification in CI, allow unverified locally
SSL_CTX = None
if os.environ.get("CI"):
    SSL_CTX = None
else:
    SSL_CTX = ssl.create_default_context()
    SSL_CTX.check_hostname = False
    SSL_CTX.verify_mode = ssl.CERT_NONE


def api_get(url, auth_token):
    """Make an authenticated GET request to the Hevy API."""
    req = urllib.request.Request(url)
    req.add_header("auth-token", auth_token)
    req.add_header("x-api-key", HEVY_API_KEY)
    req.add_header("Accept", "application/json")

    with urllib.request.urlopen(req, context=SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_workouts(auth_token):
    """Fetch all workouts from Hevy, paginating through results."""
    all_workouts = []
    offset = 0

    while True:
        url = f"{HEVY_API_URL}?username={HEVY_USERNAME}&limit={PER_PAGE}&offset={offset}"
        result = api_get(url, auth_token)

        batch = result.get("workouts", [])
        if not batch:
            break

        all_workouts.extend(batch)
        print(f"  Offset {offset}: {len(batch)} workouts")
        offset += len(batch)
        time.sleep(0.5)

    print(f"Total workouts fetched: {len(all_workouts)}")
    return all_workouts


def kg_to_lbs(kg):
    return round(kg * 2.20462, 1)


def process_set(raw_set):
    """Transform a raw Hevy set into our schema."""
    weight_kg = raw_set.get("weight_kg") or 0
    return {
        "indicator": raw_set.get("indicator", "normal"),
        "weight_kg": weight_kg,
        "weight_lbs": kg_to_lbs(weight_kg),
        "reps": raw_set.get("reps"),
        "rpe": raw_set.get("rpe"),
        "duration_seconds": raw_set.get("duration_seconds"),
        "distance_meters": raw_set.get("distance_meters"),
        "prs": raw_set.get("prs", []),
    }


def process_exercise(raw_exercise):
    """Transform a raw Hevy exercise into our schema."""
    sets = [process_set(s) for s in raw_exercise.get("sets", [])]
    working_sets = [s for s in sets if s["indicator"] == "normal"]

    # Compute exercise-level aggregates from working sets only
    total_volume_kg = sum(s["weight_kg"] * (s["reps"] or 0) for s in working_sets)
    max_weight_kg = max((s["weight_kg"] for s in working_sets), default=0)
    total_reps = sum(s["reps"] or 0 for s in working_sets)

    return {
        "title": raw_exercise.get("title", ""),
        "muscle_group": raw_exercise.get("muscle_group", ""),
        "other_muscles": raw_exercise.get("other_muscles", []),
        "equipment_category": raw_exercise.get("equipment_category", ""),
        "exercise_type": raw_exercise.get("exercise_type", ""),
        "sets": sets,
        "working_set_count": len(working_sets),
        "total_reps": total_reps,
        "total_volume_kg": round(total_volume_kg, 1),
        "total_volume_lbs": round(kg_to_lbs(total_volume_kg), 1),
        "max_weight_kg": max_weight_kg,
        "max_weight_lbs": kg_to_lbs(max_weight_kg),
    }


def process_workout(raw):
    """Transform a raw Hevy workout into our schema."""
    start_ts = raw.get("start_time")
    end_ts = raw.get("end_time")

    start_dt = datetime.fromtimestamp(start_ts) if start_ts else None
    end_dt = datetime.fromtimestamp(end_ts) if end_ts else None

    duration_seconds = int(end_ts - start_ts) if start_ts and end_ts else 0
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    exercises = [process_exercise(e) for e in raw.get("exercises", [])]

    # Aggregate muscle groups hit in this workout
    muscle_groups = {}
    for ex in exercises:
        mg = ex["muscle_group"]
        if mg:
            muscle_groups[mg] = muscle_groups.get(mg, 0) + ex["working_set_count"]
        for om in ex["other_muscles"]:
            if om:
                muscle_groups[om] = muscle_groups.get(om, 0) + ex["working_set_count"]

    total_volume_kg = sum(ex["total_volume_kg"] for ex in exercises)
    total_sets = sum(ex["working_set_count"] for ex in exercises)
    total_reps = sum(ex["total_reps"] for ex in exercises)

    # Count personal records
    pr_count = sum(
        len(s["prs"])
        for ex in exercises
        for s in ex["sets"]
    )

    return {
        "id": raw.get("id", ""),
        "name": raw.get("name", ""),
        "date": start_dt.strftime("%Y-%m-%d") if start_dt else None,
        "year": start_dt.year if start_dt else None,
        "month": start_dt.month if start_dt else None,
        "day_of_week": days[start_dt.weekday()] if start_dt else None,
        "start_time": start_dt.isoformat() if start_dt else None,
        "end_time": end_dt.isoformat() if end_dt else None,
        "duration_seconds": duration_seconds,
        "duration_display": seconds_to_display(duration_seconds),
        "exercise_count": len(exercises),
        "total_sets": total_sets,
        "total_reps": total_reps,
        "total_volume_kg": round(total_volume_kg, 1),
        "total_volume_lbs": round(kg_to_lbs(total_volume_kg), 1),
        "pr_count": pr_count,
        "muscle_groups_hit": muscle_groups,
        "exercises": exercises,
    }


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


def compute_stats(workouts):
    """Compute aggregate statistics from processed workouts."""
    total_volume_kg = sum(w["total_volume_kg"] for w in workouts)
    total_sets = sum(w["total_sets"] for w in workouts)
    total_reps = sum(w["total_reps"] for w in workouts)
    total_duration = sum(w["duration_seconds"] for w in workouts)
    total_prs = sum(w["pr_count"] for w in workouts)

    # Aggregate muscle group frequency across all workouts
    muscle_group_sets = {}
    for w in workouts:
        for mg, count in w["muscle_groups_hit"].items():
            muscle_group_sets[mg] = muscle_group_sets.get(mg, 0) + count

    # Most common workout names
    workout_names = {}
    for w in workouts:
        name = w["name"]
        workout_names[name] = workout_names.get(name, 0) + 1

    return {
        "total_workouts": len(workouts),
        "total_volume_kg": round(total_volume_kg, 1),
        "total_volume_lbs": round(kg_to_lbs(total_volume_kg), 1),
        "total_sets": total_sets,
        "total_reps": total_reps,
        "total_duration_seconds": total_duration,
        "total_duration_display": seconds_to_display(total_duration),
        "total_prs": total_prs,
        "muscle_group_sets": muscle_group_sets,
        "workout_name_counts": workout_names,
    }


def main():
    print("=== Hevy Workout Data Fetcher ===\n")

    auth_token = os.environ.get("HEVY_AUTH_TOKEN")
    if not auth_token:
        print("Error: HEVY_AUTH_TOKEN environment variable not set.")
        print("Log in to Hevy and capture the auth-token header from the app's API calls.")
        raise SystemExit(1)

    # Fetch workouts
    print("Fetching workouts...")
    raw_workouts = fetch_workouts(auth_token)

    # Process data
    print("\nProcessing data...")
    workouts = [process_workout(w) for w in raw_workouts]
    workouts.sort(key=lambda w: w["date"] or "")

    # Compute stats
    stats = compute_stats(workouts)

    # Write JSON output
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "hevy",
        "athlete_stats": stats,
        "workouts": workouts,
    }

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)

    # Print summary
    print(f"\nProcessed {stats['total_workouts']} workouts")
    print(f"Total volume: {stats['total_volume_lbs']:,.0f} lbs ({stats['total_volume_kg']:,.0f} kg)")
    print(f"Total sets: {stats['total_sets']:,}")
    print(f"Total reps: {stats['total_reps']:,}")
    print(f"Total gym time: {stats['total_duration_display']}")
    print(f"Personal records: {stats['total_prs']}")

    # Workout name breakdown
    print("\nWorkout types:")
    for name, count in sorted(stats["workout_name_counts"].items(), key=lambda x: -x[1]):
        print(f"  {name}: {count}")

    # Muscle group breakdown
    print("\nMuscle groups (by sets):")
    for mg, count in sorted(stats["muscle_group_sets"].items(), key=lambda x: -x[1]):
        print(f"  {mg}: {count} sets")

    print(f"\nOutput written to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
