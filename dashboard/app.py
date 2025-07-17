import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

EVERHOUR_API_KEY = os.environ["EVERHOUR_API_KEY"]
EMPLOYEES_IDS = os.environ.get("EMPLOYEES_IDS", "").split(",")
TIME_MULTIPLIER = float(os.environ.get("TIME_MULTIPLIER", "1.5"))
RUN_HOUR = int(os.environ.get("RUN_HOUR", "1"))
RUN_MINUTE = int(os.environ.get("RUN_MINUTE", "0"))

HEADERS = {"X-Api-Key": EVERHOUR_API_KEY, "Content-Type": "application/json"}
BASE_URL = "https://api.everhour.com"

@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        multiplier=TIME_MULTIPLIER,
        employees=EMPLOYEES_IDS,
        run_hour=RUN_HOUR,
        run_minute=RUN_MINUTE,
        yesterday=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    )

@app.route("/api/run-now", methods=["POST"])
def run_now():
    date = request.json.get("date") or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    results = []
    for user_id in EMPLOYEES_IDS:
        if not user_id.strip():
            continue
        try:
            url = f"{BASE_URL}/users/{user_id.strip()}/time"
            params = {"from": date, "to": date}
            r = requests.get(url, headers=HEADERS, params=params)
            r.raise_for_status()
            records = r.json()
            total_orig = 0
            total_new = 0
            for rec in records:
                if "[AUTO-MULTIPLIED]" in (rec.get("comment") or ""):
                    continue
                orig = rec["time"]
                new = int(orig * TIME_MULTIPLIER)
                patch_url = f"{BASE_URL}/time-records/{rec['id']}"
                h, m, s = int(new // 3600), int((new % 3600) // 60), int(new % 60)
                requests.patch(patch_url, headers=HEADERS, json={"time": f"{h:02d}:{m:02d}:{s:02d}"})
                requests.patch(patch_url, headers=HEADERS, json={"comment": (rec.get("comment") or "") + " [AUTO-MULTIPLIED]"})
                total_orig += orig
                total_new += new
            results.append({
                "user_id": user_id,
                "original_hours": round(total_orig / 3600, 2),
                "new_hours": round(total_new / 3600, 2),
                "status": "ok"
            })
        except Exception as e:
            results.append({"user_id": user_id, "status": "error", "error": str(e)})
    return jsonify({"date": date, "results": results})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
