import requests
from datetime import datetime, timedelta
import json
import logging
import os
import time
from apscheduler.schedulers.blocking import BlockingScheduler

# Konfiguracja z zmiennych środowiskowych
EVERHOUR_API_KEY = os.environ.get("EVERHOUR_API_KEY")
BASE_URL = "https://api.everhour.com"

# Lista ID pracowników z mnożnikiem (z env lub domyślna)
EMPLOYEES_WITH_MULTIPLIER = os.environ.get("EMPLOYEES_IDS", "").split(",")

# Mnożnik czasu
TIME_MULTIPLIER = float(os.environ.get("TIME_MULTIPLIER", "1.5"))

# Godzina uruchomienia (format 24h)
RUN_HOUR = int(os.environ.get("RUN_HOUR", "1"))
RUN_MINUTE = int(os.environ.get("RUN_MINUTE", "0"))

# TRYB TESTOWY
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

# TRYB DEBUG - dodatkowe logi
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

# SUPER DEBUG - jeszcze więcej logów
SUPER_DEBUG = os.environ.get("SUPER_DEBUG", "false").lower() == "true"

# Dashboard integration
DASHBOARD_API_URL = os.environ.get("DASHBOARD_API_URL")
DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN")

# Konfiguracja logowania
logging.basicConfig(
    level=logging.DEBUG if SUPER_DEBUG else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class EverhourTimeMultiplier:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }
        self.processed_dates = set()
        self.processed_records_file = "processed_records.json"
        self.processed_records = self.load_processed_records()

    def load_processed_records(self):
        try:
            with open(self.processed_records_file, 'r') as f:
                return set(json.load(f))
        except:
            return set()

    def save_processed_records(self):
        with open(self.processed_records_file, 'w') as f:
            json.dump(list(self.processed_records), f)

    def is_record_processed(self, date, user_id, task_id):
        record_key = f"{date}_{user_id}_{task_id}"
        return record_key in self.processed_records

    def mark_record_as_processed(self, date, user_id, task_id):
        record_key = f"{date}_{user_id}_{task_id}"
        self.processed_records.add(record_key)
        self.save_processed_records()

    def get_employees_from_dashboard(self):
        """Pobiera listę aktywnych pracowników z dashboard"""
        if not DASHBOARD_API_URL or not DASHBOARD_TOKEN:
            logging.info("Brak konfiguracji dashboard, używam lokalnej listy")
            return None
        
        try:
            response = requests.get(
                f"{DASHBOARD_API_URL}/api/employees",
                headers={"Authorization": f"Bearer {DASHBOARD_TOKEN}"}
            )
            response.raise_for_status()
            employees = response.json()
            
            # Zwróć tylko aktywnych z mnożnikiem
            active_employees = []
            self.employee_multipliers = {}
            
            for emp in employees:
                if emp.get('active', True):
                    emp_id = emp['id']
                    active_employees.append(emp_id)
                    # Zapisz indywidualny mnożnik jeśli istnieje
                    self.employee_multipliers[emp_id] = emp.get('multiplier', TIME_MULTIPLIER)
            
            logging.info(f"Pobrano {len(active_employees)} aktywnych pracowników z dashboard")
            return active_employees
        except Exception as e:
            logging.error(f"Błąd pobierania pracowników z dashboard: {e}")
            return None

    def get_config_from_dashboard(self):
        """Pobiera konfigurację z dashboard"""
        if not DASHBOARD_API_URL or not DASHBOARD_TOKEN:
            return None
        
        try:
            response = requests.get(
                f"{DASHBOARD_API_URL}/api/config",
                headers={"Authorization": f"Bearer {DASHBOARD_TOKEN}"}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Błąd pobierania konfiguracji z dashboard: {e}")
            return None

    def send_log_to_dashboard(self, employee_id, employee_name, date, original_hours, updated_hours, status):
        """Wysyła log operacji do dashboard"""
        if not DASHBOARD_API_URL or not DASHBOARD_TOKEN:
            return
        
        try:
            log_data = {
                "employee_id": employee_id,
                "employee_name": employee_name,
                "date": date,
                "original_hours": original_hours,
                "updated_hours": updated_hours,
                "status": status
            }
            
            response = requests.post(
                f"{DASHBOARD_API_URL}/api/logs/record",
                json=log_data,
                headers={"Authorization": f"Bearer {DASHBOARD_TOKEN}"}
            )
            response.raise_for_status()
            logging.debug("Log wysłany do dashboard")
        except Exception as e:
            logging.warning(f"Nie udało się wysłać logu do dashboard: {e}")

    def get_user_info(self, user_id):
        """Pobiera informacje o użytkowniku z Everhour"""
        try:
            response = requests.get(
                f"{BASE_URL}/users/{user_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except:
            return {"name": f"User {user_id}"}

    def backup_user_records(self, user_id, date):
        records = self.get_user_time_records(user_id, date)
        if records:
            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            backup_file = os.path.join(backup_dir, f"backup_{user_id}_{date.strftime('%Y%m%d')}_{int(time.time())}.json")
            with open(backup_file, 'w') as f:
                json.dump(records, f, indent=2)
            logging.info(f"📁 Utworzono backup: {backup_file}")
            return backup_file
        return None

    def get_user_time_records(self, user_id, date):
        date_str = date.strftime("%Y-%m-%d")
        url = f"{BASE_URL}/users/{user_id}/time"
        params = {"from": date_str, "to": date_str}
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            if (DEBUG or SUPER_DEBUG) and data:
                logging.debug("=" * 60)
                logging.debug("STRUKTURA PIERWSZEGO REKORDU:")
                logging.debug("=" * 60)
                logging.debug(json.dumps(data[0], indent=2))
                logging.debug("=" * 60)
            return data
        except requests.exceptions.RequestException as e:
            logging.error(f"Błąd podczas pobierania rekordów dla użytkownika {user_id}: {e}")
            return None

    def update_time_record(self, record_id, new_time_seconds, original_record, multiplier=None):
        if multiplier is None:
            multiplier = TIME_MULTIPLIER
            
        task_data = original_record.get('task')
        if not task_data:
            logging.error(f"Brak task dla rekordu {record_id}")
            return None
        task_id = task_data.get('id') if isinstance(task_data, dict) else task_data
        user_data = original_record.get('user')
        user_id = user_data.get('id') if isinstance(user_data, dict) else user_data
        hours = new_time_seconds / 3600

        if DRY_RUN:
            logging.info(f"     🧪 [DRY RUN] Usunąłbym rekord {record_id} i dodał nowy z czasem {hours:.2f}h")
            if SUPER_DEBUG:
                logging.debug(f"     Task ID: {task_id}")
                logging.debug(f"     User ID: {user_id}")
                logging.debug(f"     Date: {original_record.get('date')}")
            return {"success": True, "dry_run": True}

        delete_url = f"{BASE_URL}/time/{record_id}"
        try:
            if DEBUG:
                logging.debug(f"Usuwam rekord: DELETE {delete_url}")
            delete_response = requests.delete(delete_url, headers=self.headers)
            delete_response.raise_for_status()
            if SUPER_DEBUG:
                logging.debug(f"Usunięcie - status: {delete_response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Błąd podczas usuwania rekordu {record_id}: {e}")
            if hasattr(e, 'response') and e.response:
                logging.error(f"Status: {e.response.status_code}")
                logging.error(f"Odpowiedź: {e.response.text}")
            return None

        add_url = f"{BASE_URL}/tasks/{task_id}/time"
        new_data = {
            "time": int(new_time_seconds),
            "date": original_record.get('date'),
            "user": user_id
        }
        if original_record.get('comment'):
            new_data["comment"] = original_record.get('comment')

        try:
            if DEBUG:
                logging.debug(f"Dodaję nowy rekord: POST {add_url}")
                logging.debug(f"Payload: {json.dumps(new_data, indent=2)}")
            add_response = requests.post(add_url, headers=self.headers, json=new_data)
            add_response.raise_for_status()
            new_record = add_response.json()
            if SUPER_DEBUG:
                logging.debug(f"Nowy rekord utworzony: {json.dumps(new_record, indent=2)}")
            logging.info(f"     ✅ Zaktualizowano czas na {hours:.2f}h (mnożnik: {multiplier}x)")
            if 'task' not in new_record or not new_record['task']:
                logging.error(f"     ⚠️  UWAGA: Nowy rekord nie ma przypisanego taska!")
            return new_record
        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Błąd podczas dodawania nowego rekordu czasu: {e}")
            if hasattr(e, 'response') and e.response:
                logging.error(f"Status: {e.response.status_code}")
                logging.error(f"Odpowiedź: {e.response.text}")
                logging.error(f"⚠️  KRYTYCZNY BŁĄD: Usunięto rekord {record_id} ale nie udało się dodać nowego!")
                logging.error(f"⚠️  Utracone dane: {hours:.2f}h dla zadania {task_id} użytkownika {user_id} z dnia {original_record.get('date')}")
            return None

    def get_task_name(self, task_data):
        if task_data is None:
            return "Bez zadania"
        if isinstance(task_data, str):
            return f"Zadanie ID: {task_data}"
        if isinstance(task_data, dict):
            return task_data.get('name', f"Zadanie ID: {task_data.get('id', 'Nieznane')}")
        return "Nieznane zadanie"

    def get_project_name(self, task_data):
        if not isinstance(task_data, dict):
            return "Bez projektu"
        if 'project' in task_data and isinstance(task_data['project'], dict):
            return task_data['project'].get('name', 'Bez nazwy projektu')
        projects = task_data.get('projects', [])
        if projects and isinstance(projects, list) and len(projects) > 0:
            return f"Projekt ID: {projects[0]}"
        return "Bez projektu"

    def process_user_time(self, user_id, date, multiplier=None):
        if multiplier is None:
            multiplier = self.employee_multipliers.get(user_id, TIME_MULTIPLIER)
            
        if DRY_RUN:
            logging.info(f"🧪 [DRY RUN] Przetwarzanie czasu dla użytkownika {user_id} z dnia {date}")
        else:
            logging.info(f"Przetwarzanie czasu dla użytkownika {user_id} z dnia {date}")
            
        # Pobierz info o użytkowniku
        user_info = self.get_user_info(user_id)
        user_name = user_info.get('name', f'User {user_id}')
        
        if not DRY_RUN:
            backup_file = self.backup_user_records(user_id, date)
            if backup_file:
                logging.info(f"✅ Backup utworzony: {backup_file}")
                
        time_records = self.get_user_time_records(user_id, date)
        if not time_records:
            logging.warning(f"Brak rekordów czasu dla użytkownika {user_id}")
            return
            
        total_original_time = 0
        total_updated_time = 0
        successful_updates = 0
        skipped_no_task = 0
        skipped_zero_time = 0
        skipped_already_processed = 0
        
        logging.info(f"Znaleziono {len(time_records)} rekordów dla {user_name}:")
        
        for i, record in enumerate(time_records):
            try:
                record_id = record.get('id')
                original_time_seconds = record.get('time', 0)
                
                if SUPER_DEBUG:
                    logging.debug(f"\n--- REKORD {i+1} ---")
                    logging.debug(f"ID: {record_id}")
                    logging.debug(f"Time: {original_time_seconds}")
                    logging.debug(f"User: {record.get('user')}")
                    
                if original_time_seconds <= 0:
                    logging.warning(f"  ⚠️  Pomijam rekord {record_id} - czas = {original_time_seconds}")
                    skipped_zero_time += 1
                    continue
                    
                task_data = record.get('task')
                task_name = self.get_task_name(task_data)
                project_name = self.get_project_name(task_data)
                
                if not task_data:
                    logging.warning(f"  ⚠️  Pomijam rekord {record_id} - brak przypisanego zadania")
                    skipped_no_task += 1
                    continue
                    
                task_id = task_data.get('id') if isinstance(task_data, dict) else task_data
                user_id_from_record = record.get('user')
                if isinstance(user_id_from_record, dict):
                    user_id_from_record = user_id_from_record.get('id')
                    
                if self.is_record_processed(record.get('date'), user_id_from_record, task_id):
                    logging.info(f"  ⏭️  [{project_name}] {task_name} - już przetworzony, pomijam")
                    skipped_already_processed += 1
                    continue
                    
                new_time_seconds = int(original_time_seconds * multiplier)
                original_hours = original_time_seconds / 3600
                new_hours = new_time_seconds / 3600
                
                logging.info(f"  📋 [{project_name}] {task_name}:")
                logging.info(f"     ⏱️  {original_hours:.2f}h → {new_hours:.2f}h (+{new_hours - original_hours:.2f}h)")
                
                result = self.update_time_record(record_id, new_time_seconds, record, multiplier)
                
                if result:
                    total_original_time += original_time_seconds
                    total_updated_time += new_time_seconds
                    successful_updates += 1
                    
                    if not DRY_RUN:
                        self.mark_record_as_processed(record.get('date'), user_id_from_record, task_id)
                        # Wyślij log do dashboard
                        self.send_log_to_dashboard(
                            user_id,
                            user_name,
                            record.get('date'),
                            original_hours,
                            new_hours,
                            "success"
                        )
                else:
                    if not DRY_RUN:
                        logging.error(f"     ❌ Błąd aktualizacji")
                        self.send_log_to_dashboard(
                            user_id,
                            user_name,
                            record.get('date'),
                            original_hours,
                            0,
                            "error"
                        )
            except Exception as e:
                logging.error(f"Błąd podczas przetwarzania rekordu {i}: {e}")
                if SUPER_DEBUG:
                    import traceback
                    logging.debug(f"Traceback: {traceback.format_exc()}")
                    
        logging.info("")
        logging.info("📊 PODSUMOWANIE:")
        logging.info(f"   Użytkownik: {user_name}")
        logging.info(f"   Mnożnik: {multiplier}x")
        logging.info(f"   Znalezionych rekordów: {len(time_records)}")
        logging.info(f"   Przetworzonych rekordów: {successful_updates}")
        logging.info(f"   Pominiętych (brak zadania): {skipped_no_task}")
        logging.info(f"   Pominiętych (zero czasu): {skipped_zero_time}")
        logging.info(f"   Pominiętych (już przetworzone): {skipped_already_processed}")
        
        if total_original_time > 0:
            original_hours = total_original_time / 3600
            updated_hours = total_updated_time / 3600
            diff_hours = updated_hours - original_hours
            logging.info(f"   Czas oryginalny: {original_hours:.2f}h")
            logging.info(f"   Czas po aktualizacji: {updated_hours:.2f}h")
            logging.info(f"   Różnica: +{diff_hours:.2f}h")

    def run_daily_update(self, process_date=None):
        if process_date is None:
            process_date = datetime.now().date() - timedelta(days=1)
            
        date_key = process_date.strftime("%Y-%m-%d")
        if date_key in self.processed_dates and not DRY_RUN:
            logging.warning(f"Data {date_key} już była przetworzona!")
            return
            
        # Pobierz konfigurację z dashboard jeśli dostępna
        dashboard_config = self.get_config_from_dashboard()
        if dashboard_config and not DRY_RUN:
            # Zaktualizuj tryb DRY_RUN z dashboard
            global DRY_RUN
            DRY_RUN = dashboard_config.get('dry_run', DRY_RUN)
            
        if DRY_RUN:
            logging.info("=" * 60)
            logging.info("🧪 TRYB TESTOWY (DRY RUN) - ŻADNE DANE NIE ZOSTANĄ ZMIENIONE")
            logging.info("=" * 60)
            
        logging.info(f"=== Rozpoczynanie aktualizacji czasu za dzień {process_date} ===")
        
        # Pobierz pracowników z dashboard jeśli możliwe
        self.employee_multipliers = {}
        dashboard_employees = self.get_employees_from_dashboard()
        
        if dashboard_employees:
            employees_to_process = dashboard_employees
            logging.info("Używam listy pracowników z dashboard")
        else:
            employees_to_process = [e for e in EMPLOYEES_WITH_MULTIPLIER if e.strip()]
            logging.info("Używam listy pracowników z zmiennych środowiskowych")
            
        success_count = 0
        error_count = 0
        
        for user_id in employees_to_process:
            if not user_id or not str(user_id).strip():
                continue
                
            try:
                # Użyj indywidualnego mnożnika jeśli istnieje
                multiplier = self.employee_multipliers.get(user_id, TIME_MULTIPLIER)
                self.process_user_time(str(user_id).strip(), process_date, multiplier)
                success_count += 1
            except Exception as e:
                logging.error(f"Błąd podczas przetwarzania użytkownika {user_id}: {e}")
                error_count += 1
                
        if not DRY_RUN:
            self.processed_dates.add(date_key)
            
        logging.info(f"=== Aktualizacja zakończona. Sukces: {success_count}, Błędy: {error_count} ===")
        
        if DRY_RUN:
            logging.info("=" * 60)
            logging.info("🧪 KONIEC TRYBU TESTOWEGO - Aby naprawdę zaktualizować dane, ustaw DRY_RUN=false")
            logging.info("=" * 60)

def scheduled_job():
    logging.info("Uruchamiam zaplanowane zadanie...")
    if not EVERHOUR_API_KEY:
        logging.error("Brak klucza API Everhour!")
        return
        
    multiplier = EverhourTimeMultiplier(EVERHOUR_API_KEY)
    multiplier.run_daily_update()

# Funkcja do ręcznego uruchomienia (może być wywołana przez dashboard)
def manual_trigger(employee_id=None, date=None):
    """Ręczne uruchomienie dla konkretnego pracownika lub daty"""
    logging.info("Ręczne uruchomienie skryptu")
    
    if not EVERHOUR_API_KEY:
        logging.error("Brak klucza API Everhour!")
        return {"error": "Brak konfiguracji API"}
        
    multiplier = EverhourTimeMultiplier(EVERHOUR_API_KEY)
    
    if employee_id:
        # Przetwórz tylko jednego pracownika
        process_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date() - timedelta(days=1)
        try:
            multiplier.process_user_time(employee_id, process_date)
            return {"success": True, "message": f"Przetworzono pracownika {employee_id}"}
        except Exception as e:
            return {"error": str(e)}
    else:
        # Przetwórz wszystkich
        process_date = datetime.strptime(date, "%Y-%m-%d").date() if date else None
        multiplier.run_daily_update(process_date)
        return {"success": True, "message": "Przetworzono wszystkich pracowników"}

def main():
    logging.info("Everhour Time Multiplier - Start")
    logging.info(f"Mnożnik: {TIME_MULTIPLIER}x")
    logging.info(f"Pracownicy: {EMPLOYEES_WITH_MULTIPLIER}")
    logging.info(f"Zaplanowane uruchomienie: {RUN_HOUR:02d}:{RUN_MINUTE:02d}")
    
    if DASHBOARD_API_URL:
        logging.info(f"Dashboard API: {DASHBOARD_API_URL}")
    else:
        logging.info("Dashboard API nie skonfigurowane - działam autonomicznie")
        
    if DRY_RUN:
        logging.info("🧪 TRYB DRY RUN WŁĄCZONY - dane nie będą modyfikowane")
    if DEBUG:
        logging.info("🔍 TRYB DEBUG WŁĄCZONY - dodatkowe logi")
    if SUPER_DEBUG:
        logging.info("🔬 TRYB SUPER DEBUG WŁĄCZONY - maksymalne logowanie")
        
    if os.environ.get("RUN_ON_START", "false").lower() == "true":
        scheduled_job()
        
    scheduler = BlockingScheduler(timezone='Europe/Warsaw')
    scheduler.add_job(
        scheduled_job,
        'cron',
        hour=RUN_HOUR,
        minute=RUN_MINUTE,
        id='daily_time_update'
    )
    
    logging.info("Scheduler uruchomiony. Czekam na zaplanowane zadania...")
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logging.info("Zamykanie aplikacji...")
        scheduler.shutdown()

if __name__ == "__main__":
    main()
