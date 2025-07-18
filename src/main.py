import requests
from datetime import datetime, timedelta
import json
import logging
import os
from apscheduler.schedulers.blocking import BlockingScheduler

# --------------------------------------------------
#  KONFIGURACJA
# --------------------------------------------------
EVERHOUR_API_KEY       = os.getenv("EVERHOUR_API_KEY")
BASE_URL               = "https://api.everhour.com"
EMPLOYEES_WITH_MULTIPLIER = os.getenv("EMPLOYEES_IDS", "").split(",")

TIME_MULTIPLIER        = float(os.getenv("TIME_MULTIPLIER", "1.5"))
RUN_HOUR               = int(os.getenv("RUN_HOUR", "1"))
RUN_MINUTE             = int(os.getenv("RUN_MINUTE", "0"))

DRY_RUN                = os.getenv("DRY_RUN", "false").lower() == "true"
DEBUG                  = os.getenv("DEBUG", "false").lower() == "true"

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# --------------------------------------------------
#  KLASA ROBOCZA
# --------------------------------------------------
class EverhourTimeMultiplier:
    def __init__(self, api_key):
        self.headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
        }
        self.processed_dates = set()

    # --- drobna pomocnicza konwersja ---
    @staticmethod
    def seconds_to_hms(sec: int) -> str:             #  ← NOWA UNIWERSALNA FUNKCJA
        h, m = divmod(sec, 3600)
        m, s = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    # --- pobieranie wpisów czasu ---
    def get_user_time_records(self, user_id: str, date: datetime.date):
        url = f"{BASE_URL}/users/{user_id}/time"
        params = {"from": str(date), "to": str(date)}
        try:
            r = requests.get(url, headers=self.headers, params=params)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            logging.error(f"Błąd GET {url}: {e}")
            return []

    # --- kluczowa poprawka: PATCH + pole `task`, opcjonalnie `user` ---
    def update_time_record(
        self,
        record_id: str,
        new_seconds: int,
        task_id: str | None = None,
        user_id: str | None = None,
    ):
        url = f"{BASE_URL}/time/{record_id}"

        payload = {"time": self.seconds_to_hms(new_seconds)}
        if task_id:
            payload["task"] = task_id          #  ← BYŁO taskId, MUSI BYĆ task
        if user_id:
            payload["user"] = user_id          #  ← zabezpiecza przed „przejęciem” wpisu

        if DRY_RUN:
            logging.info(f"[DRY RUN] PATCH {url}  {payload}")
            return True

        try:
            r = requests.patch(url, headers=self.headers, json=payload)  # ← PATCH zamiast PUT
            r.raise_for_status()
            return True
        except requests.RequestException as e:
            logging.error(f"Błąd PATCH {url}: {e} | payload={payload}")
            return False

    # --- główne przeliczenie jednego użytkownika ---
    def process_user_time(self, user_id: str, date: datetime.date):
        records = self.get_user_time_records(user_id, date)
        if not records:
            logging.info(f"Brak wpisów dla {user_id} {date}")
            return

        for rec in records:
            if "[AUTO-MULTIPLIED]" in rec.get("comment", ""):
                continue

            rec_id   = rec["id"]
            orig_sec = rec.get("time", 0)
            task_dat = rec.get("task")
            task_id  = task_dat["id"] if isinstance(task_dat, dict) else task_dat
            new_sec  = int(orig_sec * TIME_MULTIPLIER)

            ok = self.update_time_record(rec_id, new_sec, task_id, user_id)
            if ok:
                logging.info(f"✓ {rec_id}  {orig_sec//3600:.2f}h → {new_sec//3600:.2f}h")

    # --- wsadowy przebieg po wszystkich ---
    def run_daily_update(self, date_to_process: datetime.date | None = None):
        if date_to_process is None:
            date_to_process = datetime.now().date() - timedelta(days=1)
        key = str(date_to_process)
        if key in self.processed_dates and not DRY_RUN:
            logging.warning(f"{key} już obrobione")
            return

        logging.info(f"=== START {date_to_process} ===")
        for uid in filter(None, EMPLOYEES_WITH_MULTIPLIER):
            self.process_user_time(uid.strip(), date_to_process)
        if not DRY_RUN:
            self.processed_dates.add(key)
        logging.info("=== KONIEC ===")

# --------------------------------------------------
#  SCHEDULER / ENTRYPOINT
# --------------------------------------------------
def scheduled_job():
    if not EVERHOUR_API_KEY:
        logging.error("Brak EVERHOUR_API_KEY")
        return
    if not any(EMPLOYEES_WITH_MULTIPLIER):
        logging.error("EMPLOYEES_IDS puste")
        return
    EverhourTimeMultiplier(EVERHOUR_API_KEY).run_daily_update()

if __name__ == "__main__":
    if os.getenv("RUN_ON_START", "false").lower() == "true":
        scheduled_job()

    sched = BlockingScheduler(timezone="Europe/Warsaw")
    sched.add_job(scheduled_job, "cron", hour=RUN_HOUR, minute=RUN_MINUTE)
    logging.info(f"Scheduler aktywny → następny run {RUN_HOUR:02d}:{RUN_MINUTE:02d}")
    sched.start()
