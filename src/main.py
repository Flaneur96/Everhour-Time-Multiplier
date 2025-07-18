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

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
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
    
    def get_user_time_records(self, user_id, date):
        """Pobiera rekordy czasu dla użytkownika z danego dnia"""
        date_str = date.strftime("%Y-%m-%d")
        
        url = f"{BASE_URL}/users/{user_id}/time"
        params = {
            "from": date_str,
            "to": date_str
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if DEBUG and data:
                logging.debug(f"Przykładowy rekord: {json.dumps(data[0], indent=2)}")
            
            return data
        except requests.exceptions.RequestException as e:
            logging.error(f"Błąd podczas pobierania rekordów dla użytkownika {user_id}: {e}")
            return None
    
    def update_time_record(self, record_id, new_time_seconds, original_record):
        """Aktualizuje rekord czasu ZACHOWUJĄC WSZYSTKIE dane"""
        url = f"{BASE_URL}/time/{record_id}"
        
        hours = int(new_time_seconds // 3600)
        minutes = int((new_time_seconds % 3600) // 60)
        seconds = int(new_time_seconds % 60)
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        if DRY_RUN:
            logging.info(f"     🧪 [DRY RUN] Zaktualizowałbym rekord {record_id} na {time_str}")
            return {"success": True, "dry_run": True}
        
        # WAŻNE: Buduj payload z WSZYSTKIMI oryginalnymi danymi
        data = {
            "time": time_str,
            "date": original_record.get('date')  # Zachowaj datę
        }
        
        # Zachowaj użytkownika
        user_data = original_record.get('user')
        if user_data:
            if isinstance(user_data, dict):
                data["user"] = user_data.get('id')
            else:
                data["user"] = user_data
        
        # KLUCZOWE: Zachowaj zadanie używając poprawnego pola "task"
        task_data = original_record.get('task')
        if task_data:
            if isinstance(task_data, dict):
                data["task"] = task_data.get('id')
            elif isinstance(task_data, str):
                data["task"] = task_data
        
        # Zachowaj komentarz jeśli istnieje
        if original_record.get('comment'):
            data["comment"] = original_record.get('comment')
        
        if DEBUG:
            logging.debug(f"Payload do wysłania: {json.dumps(data)}")
        
        try:
            response = requests.put(url, headers=self.headers, json=data)
            response.raise_for_status()
            logging.info(f"     ✅ Zaktualizowano czas na {time_str}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Błąd podczas aktualizacji rekordu {record_id}: {e}")
            if DEBUG and hasattr(e, 'response'):
                logging.debug(f"Status: {e.response.status_code}")
                logging.debug(f"Odpowiedź: {e.response.text}")
            return None
    
    def get_task_name(self, task_data):
        """Bezpiecznie pobiera nazwę zadania"""
        if task_data is None:
            return "Bez zadania"
        
        if isinstance(task_data, str):
            return f"Zadanie ID: {task_data}"
        
        if isinstance(task_data, dict):
            return task_data.get('name', f"Zadanie ID: {task_data.get('id', 'Nieznane')}")
        
        return "Nieznane zadanie"
    
    def get_project_name(self, task_data):
        """Bezpiecznie pobiera nazwę projektu"""
        if not isinstance(task_data, dict):
            return "Bez projektu"
        
        projects = task_data.get('projects', [])
        if projects and isinstance(projects, list) and len(projects) > 0:
            if isinstance(projects[0], dict):
                return projects[0].get('name', 'Bez nazwy projektu')
        
        return "Bez projektu"
    
    def process_user_time(self, user_id, date):
        """Przetwarza i aktualizuje czas dla użytkownika"""
        if DRY_RUN:
            logging.info(f"🧪 [DRY RUN] Przetwarzanie czasu dla użytkownika {user_id} z dnia {date}")
        else:
            logging.info(f"Przetwarzanie czasu dla użytkownika {user_id} z dnia {date}")
        
        time_records = self.get_user_time_records(user_id, date)
        
        if not time_records:
            logging.warning(f"Brak rekordów czasu dla użytkownika {user_id}")
            return
        
        total_original_time = 0
        total_updated_time = 0
        successful_updates = 0
        skipped_no_task = 0
        
        logging.info(f"Znaleziono {len(time_records)} rekordów:")
        
        for i, record in enumerate(time_records):
            try:
                record_id = record.get('id')
                original_time_seconds = record.get('time', 0)
                
                # Debugowanie struktury pierwszego rekordu
                if DEBUG and i == 0:
                    logging.debug(f"Struktura rekordu: {json.dumps(record, indent=2)}")
                
                # Pobierz informacje o zadaniu
                task_data = record.get('task')
                task_name = self.get_task_name(task_data)
                project_name = self.get_project_name(task_data)
                
                # WAŻNE: Pomijaj rekordy bez zadania
                if not task_data:
                    logging.warning(f"  ⚠️  Pomijam rekord {record_id} - brak przypisanego zadania")
                    skipped_no_task += 1
                    continue

                if i >= 0:  # Przetworzy tylko pierwszy rekord
                    break
                
                # Oblicz nowy czas z mnożnikiem
                new_time_seconds = int(original_time_seconds * TIME_MULTIPLIER)
                
                original_hours = original_time_seconds / 3600
                new_hours = new_time_seconds / 3600
                
                logging.info(f"  📋 [{project_name}] {task_name}:")
                logging.info(f"     ⏱️  {original_hours:.2f}h → {new_hours:.2f}h (+{new_hours - original_hours:.2f}h)")
                
                # Sprawdź czy nie jest to już przetworzone
                comment = record.get('comment', '')
                if comment and '[AUTO-MULTIPLIED]' in comment:
                    logging.info(f"     ⏭️  Rekord już był przetworzony, pomijam")
                    continue
                
                # Aktualizuj z PEŁNYM rekordem
                result = self.update_time_record(record_id, new_time_seconds, record)
                
                if result:
                    total_original_time += original_time_seconds
                    total_updated_time += new_time_seconds
                    successful_updates += 1
                else:
                    if not DRY_RUN:
                        logging.error(f"     ❌ Błąd aktualizacji")
                        
            except Exception as e:
                logging.error(f"Błąd podczas przetwarzania rekordu {i}: {e}")
                if DEBUG:
                    logging.debug(f"Problematyczny rekord: {record}")
        
        # Podsumowanie
        logging.info("")
        logging.info("📊 PODSUMOWANIE:")
        logging.info(f"   Znalezionych rekordów: {len(time_records)}")
        logging.info(f"   Przetworzonych rekordów: {successful_updates}")
        logging.info(f"   Pominiętych (brak zadania): {skipped_no_task}")
        
        if total_original_time > 0:
            original_hours = total_original_time / 3600
            updated_hours = total_updated_time / 3600
            diff_hours = updated_hours - original_hours
            
            logging.info(f"   Czas oryginalny: {original_hours:.2f}h")
            logging.info(f"   Czas po aktualizacji: {updated_hours:.2f}h")
            logging.info(f"   Różnica: +{diff_hours:.2f}h")
    
    def run_daily_update(self, process_date=None):
        """Uruchamia aktualizację dla wszystkich użytkowników"""
        if process_date is None:
            process_date = datetime.now().date() - timedelta(days=1)
        
        # Zabezpieczenie przed podwójnym przetwarzaniem
        date_key = process_date.strftime("%Y-%m-%d")
        if date_key in self.processed_dates and not DRY_RUN:
            logging.warning(f"Data {date_key} już była przetworzona!")
            return
        
        if DRY_RUN:
            logging.info("=" * 60)
            logging.info("🧪 TRYB TESTOWY (DRY RUN) - ŻADNE DANE NIE ZOSTANĄ ZMIENIONE")
            logging.info("=" * 60)
        
        logging.info(f"=== Rozpoczynanie aktualizacji czasu za dzień {process_date} ===")
        
        success_count = 0
        error_count = 0
        
        for user_id in EMPLOYEES_WITH_MULTIPLIER:
            if not user_id.strip():
                continue
                
            try:
                self.process_user_time(user_id.strip(), process_date)
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
    """Zadanie do wykonania przez scheduler"""
    logging.info("Uruchamiam zaplanowane zadanie...")
    
    if not EVERHOUR_API_KEY:
        logging.error("Brak klucza API Everhour!")
        return
    
    if not EMPLOYEES_WITH_MULTIPLIER or EMPLOYEES_WITH_MULTIPLIER == ['']:
        logging.error("Brak listy pracowników!")
        return
    
    multiplier = EverhourTimeMultiplier(EVERHOUR_API_KEY)
    multiplier.run_daily_update()

def main():
    """Główna funkcja aplikacji"""
    logging.info("Everhour Time Multiplier - Start")
    logging.info(f"Mnożnik: {TIME_MULTIPLIER}x")
    logging.info(f"Pracownicy: {EMPLOYEES_WITH_MULTIPLIER}")
    logging.info(f"Zaplanowane uruchomienie: {RUN_HOUR:02d}:{RUN_MINUTE:02d}")
    
    if DRY_RUN:
        logging.info("🧪 TRYB DRY RUN WŁĄCZONY - dane nie będą modyfikowane")
    
    if DEBUG:
        logging.info("🔍 TRYB DEBUG WŁĄCZONY - dodatkowe logi")
    
    # Uruchom raz na starcie (dla testów)
    if os.environ.get("RUN_ON_START", "false").lower() == "true":
        scheduled_job()
    
    # Skonfiguruj scheduler
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
