"""
Apple Health Data Receiver
Processes health data payloads from Health Auto Export iOS app,
merges with existing data, and writes to JSON for the dashboard.

Called by the health-data-receive GitHub Actions workflow when
a repository_dispatch event is triggered.

No external dependencies -- uses only Python standard library.

Usage:
    python scripts/receive_health_data.py '{"data": {"metrics": [...]}}'
"""

import json
import os
import sys
from datetime import datetime


OUTPUT_JSON = "data/apple_health.json"


def load_existing():
    """Load existing health data or return empty structure."""
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON) as f:
            return json.load(f)
    return {
        "last_updated": None,
        "source": "apple_health",
        "sleep": [],
        "heart_rate_variability": [],
        "resting_heart_rate": [],
        "blood_oxygen": [],
        "heart_rate": [],
    }


def extract_sleep(metrics):
    """Extract sleep data from Health Auto Export metrics."""
    records = []
    for metric in metrics:
        name = metric.get("name", "")
        if name not in ("sleep_analysis", "Sleep Analysis"):
            continue

        for entry in metric.get("data", []):
            # Aggregated sleep data
            record = {
                "date": entry.get("date", "")[:10],
                "sleep_start": entry.get("sleepStart"),
                "sleep_end": entry.get("sleepEnd"),
                "in_bed_minutes": entry.get("inBed"),
                "asleep_minutes": entry.get("asleep"),
                "core_minutes": entry.get("core"),
                "deep_minutes": entry.get("deep"),
                "rem_minutes": entry.get("rem"),
                "awake_minutes": entry.get("awake") if entry.get("awake") else None,
            }

            # Calculate total sleep from components if not directly available
            if record["asleep_minutes"] is None:
                components = [record["core_minutes"], record["deep_minutes"], record["rem_minutes"]]
                if all(c is not None for c in components):
                    record["asleep_minutes"] = sum(components)

            if record["date"]:
                records.append(record)

    return records


def extract_hrv(metrics):
    """Extract heart rate variability data."""
    records = []
    for metric in metrics:
        name = metric.get("name", "")
        if "heart_rate_variability" not in name.lower() and "Heart Rate Variability" not in name:
            continue

        for entry in metric.get("data", []):
            qty = entry.get("qty") or entry.get("Avg")
            if qty is not None:
                records.append({
                    "date": entry.get("date", "")[:10],
                    "hrv_ms": round(float(qty), 1),
                })

    return records


def extract_resting_hr(metrics):
    """Extract resting heart rate data."""
    records = []
    for metric in metrics:
        name = metric.get("name", "")
        if "resting_heart_rate" not in name.lower() and "Resting Heart Rate" not in name:
            continue

        for entry in metric.get("data", []):
            qty = entry.get("qty") or entry.get("Avg")
            if qty is not None:
                records.append({
                    "date": entry.get("date", "")[:10],
                    "resting_hr": round(float(qty)),
                })

    return records


def extract_blood_oxygen(metrics):
    """Extract blood oxygen (SpO2) data."""
    records = []
    for metric in metrics:
        name = metric.get("name", "")
        if "blood_oxygen" not in name.lower() and "Blood Oxygen" not in name:
            continue

        for entry in metric.get("data", []):
            qty = entry.get("qty") or entry.get("Avg")
            if qty is not None:
                val = float(qty)
                # Convert decimal (0.97) to percentage (97) if needed
                if val <= 1:
                    val = val * 100
                records.append({
                    "date": entry.get("date", "")[:10],
                    "spo2_pct": round(val, 1),
                })

    return records


def extract_heart_rate(metrics):
    """Extract heart rate data (daily summaries)."""
    records = []
    for metric in metrics:
        name = metric.get("name", "")
        if name.lower() not in ("heart_rate", "heart rate"):
            continue

        for entry in metric.get("data", []):
            record = {
                "date": entry.get("date", "")[:10],
                "hr_min": entry.get("Min"),
                "hr_avg": entry.get("Avg"),
                "hr_max": entry.get("Max"),
            }
            if any(v is not None for v in [record["hr_min"], record["hr_avg"], record["hr_max"]]):
                records.append(record)

    return records


def merge_records(existing, new_records, key="date"):
    """Merge new records into existing, deduplicating by date."""
    by_date = {r[key]: r for r in existing}
    for r in new_records:
        by_date[r[key]] = r  # New data overwrites old for same date
    merged = sorted(by_date.values(), key=lambda x: x[key])
    return merged


def main():
    if len(sys.argv) < 2:
        print("Usage: python receive_health_data.py '<json_payload>'")
        sys.exit(1)

    print("=== Apple Health Data Receiver ===\n")

    # Parse incoming payload
    payload = json.loads(sys.argv[1])
    metrics = payload.get("data", {}).get("metrics", [])

    if not metrics:
        print("No metrics found in payload.")
        sys.exit(0)

    print(f"Received {len(metrics)} metric types")
    for m in metrics:
        data_count = len(m.get("data", []))
        print(f"  {m.get('name', 'unknown')}: {data_count} entries")

    # Extract data from payload
    new_sleep = extract_sleep(metrics)
    new_hrv = extract_hrv(metrics)
    new_rhr = extract_resting_hr(metrics)
    new_spo2 = extract_blood_oxygen(metrics)
    new_hr = extract_heart_rate(metrics)

    print(f"\nExtracted:")
    print(f"  Sleep records: {len(new_sleep)}")
    print(f"  HRV records: {len(new_hrv)}")
    print(f"  Resting HR records: {len(new_rhr)}")
    print(f"  SpO2 records: {len(new_spo2)}")
    print(f"  Heart rate records: {len(new_hr)}")

    # Load existing and merge
    existing = load_existing()

    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "apple_health",
        "sleep": merge_records(existing.get("sleep", []), new_sleep),
        "heart_rate_variability": merge_records(existing.get("heart_rate_variability", []), new_hrv),
        "resting_heart_rate": merge_records(existing.get("resting_heart_rate", []), new_rhr),
        "blood_oxygen": merge_records(existing.get("blood_oxygen", []), new_spo2),
        "heart_rate": merge_records(existing.get("heart_rate", []), new_hr),
    }

    # Write output
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)

    total = sum(len(output[k]) for k in ["sleep", "heart_rate_variability", "resting_heart_rate", "blood_oxygen", "heart_rate"])
    print(f"\nTotal records in database: {total}")
    print(f"Output written to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
