
import os
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, jsonify
import requests

app = Flask(__name__)

HCP_BASE = os.getenv("HCP_API_BASE", "https://api.housecallpro.com")
API_KEY = os.getenv("HCP_API_KEY", "")

TECH_COLORS = {
    "dylan": "#2f80ed",
    "spencer": "#e53935",
    "dawson": "#2e9d50",
    "brian": "#222222",
}
DEFAULT_COLOR = "#6b7280"

def headers():
    # Housecall Pro public API uses the API key as a Bearer token.
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
    }

def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def extract_items(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("jobs", "data", "items", "results"):
        if isinstance(payload.get(key), list):
            return payload[key]
    return []

def get_name(job):
    customer = job.get("customer") or {}
    first = customer.get("first_name") or customer.get("firstName") or ""
    last = customer.get("last_name") or customer.get("lastName") or ""
    customer_name = customer.get("name") or f"{first} {last}".strip()
    return (
        job.get("name")
        or job.get("job_name")
        or job.get("jobName")
        or customer_name
        or "Scheduled Job"
    )

def get_description(job):
    return (
        job.get("job_type")
        or job.get("jobType")
        or job.get("description")
        or job.get("summary")
        or job.get("notes")
        or ""
    )

def get_start(job):
    schedule = job.get("schedule") or {}
    candidates = [
        schedule.get("scheduled_start"),
        schedule.get("start_at"),
        job.get("scheduled_start"),
        job.get("start_at"),
        job.get("start_time"),
    ]
    for value in candidates:
        if value:
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except Exception:
                pass
    return None

def assigned_names(job):
    possible = (
        job.get("assigned_employees")
        or job.get("assignedEmployees")
        or job.get("employees")
        or (job.get("schedule") or {}).get("assigned_employees")
        or []
    )
    names = []
    if isinstance(possible, dict):
        possible = [possible]
    for person in possible:
        if isinstance(person, str):
            names.append(person)
        elif isinstance(person, dict):
            name = person.get("name") or f"{person.get('first_name','')} {person.get('last_name','')}".strip()
            if name:
                names.append(name)
    return names

def color_for(job):
    for name in assigned_names(job):
        low = name.lower()
        for tech, color in TECH_COLORS.items():
            if tech in low:
                return color
    return DEFAULT_COLOR

def fetch_jobs():
    if not API_KEY:
        raise RuntimeError("HCP_API_KEY is not configured.")

    all_jobs = []
    page = 1
    page_size = 200

    while True:
        params = {
            "page": page,
            "page_size": page_size,
        }

        r = requests.get(
            HCP_BASE.rstrip("/") + "/jobs",
            headers=headers(),
            params=params,
            timeout=20,
        )

        r.raise_for_status()

        jobs = extract_items(r.json())

        if not jobs:
            break

        all_jobs.extend(jobs)

        print(
            f"HCP jobs page {page}: "
            f"{len(jobs)} jobs; total so far {len(all_jobs)}"
        )

        if len(jobs) < page_size:
            break

        page += 1

        # Safety limit
        if page > 50:
            print("Stopped after 50 pages of HCP jobs.")
            break

    print(f"HCP TOTAL JOBS RETRIEVED: {len(all_jobs)}")
    return all_jobs

def fetch_appointments(job_id):
    """Get all appointments scheduled for a Housecall Pro job."""
    try:
        r = requests.get(
            HCP_BASE.rstrip("/") + f"/jobs/{job_id}/appointments",
            headers=headers(),
            timeout=20,
        )

        if not r.ok:
            print(
                f"HCP appointment error for {job_id}: "
                f"STATUS={r.status_code} RESPONSE={r.text}"
            )
            return []

        return extract_items(r.json())

    except Exception as e:
        print(f"Could not load appointments for job {job_id}: {e}")
        return []

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/jobs")
def jobs():
    try:
        raw = fetch_jobs()
        result = []

        for job in raw:
            job_id = job.get("id")
            appointments = fetch_appointments(job_id) if job_id else []

            # If this job has appointments, create a calendar entry
            # for every appointment.
            if appointments:
                for appointment in appointments:
                    start = get_start(appointment)
                    if not start:
                        continue

                    # Combine job information with appointment information
                    # so technician assignment can come from either one.
                    combined = dict(job)
                    combined.update(appointment)

                    result.append({
                        "date": start.date().isoformat(),
                        "name": get_name(job),
                        "description": get_description(job),
                        "color": color_for(combined),
                    })

            # If HCP doesn't return appointments for this job,
            # fall back to the original job schedule.
            else:
                start = get_start(job)
                if not start:
                    continue

                result.append({
                    "date": start.date().isoformat(),
                    "name": get_name(job),
                    "description": get_description(job),
                    "color": color_for(job),
                })

        return jsonify({"ok": True, "jobs": result})

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "jobs": []
        }), 500

@app.get("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
