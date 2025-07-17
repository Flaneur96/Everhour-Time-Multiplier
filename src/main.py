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
        self.processed_dates = set()  # Zabezpieczenie przed podwójnym przetwarzaniem
    
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
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Błąd podczas pobierania rekordów dla użytkownika {user_id}: {e}")
            return None
    
    def update_time_record(self, time_record_id, new_time_seconds):
        """Aktualizuje rekord czasu"""
        url = f"{BASE_URL}/time-records/{time_record_id}"
        
        hours = int(new_time_seconds // 3600)
        minutes = int((new_time_seconds % 3600) // 60)
        seconds = int(new_time_seconds % 60)
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        data = {
            "time": time_str
        }
        
        try:
            response = requests.patch(url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Błąd podczas aktualizacji rekordu {time_record_id}: {e}")
            return None
    
    def process_user_time(self, user_id, date):
        """Przetwarza i aktualizuje czas dla użytkownika"""
        logging.info(f"Przetwarzanie czasu dla użytkownika {user_id} z dnia {date}")
        
        time_records = self.get_user_time_records(user_id, date)
        
        if not time_records:
            logging.warning(f"Brak rekordów czasu dla użytkownika {user_id}")
            return
        
        total_original_time = 0
        total_updated_time = 0
        
        for record in time_records:
            record_id = record.get('id')
            original_time_seconds = record.get('time', 0)
            
            # Sprawdź czy nie jest to już przetworzone (poprzez komentarz lub tag)
            if record.get('comment', '').endswith('[AUTO-MULTIPLIED]'):
                logging.info(f"Rekord {record_id} już był przetworzony, pomijam")
                continue
            
            new_time_seconds = int(original_time_seconds * TIME_MULTIPLIER)
            
            result = self.update_time_record(record_id, new_time_seconds)
            
            if result:
                total_original_time += original_time_seconds
                total_updated_time += new_time_seconds
                logging.info(f"Zaktualizowano rekord {record_id}: {original_time_seconds}s -> {new_time_seconds}s")
                
                # Opcjonalnie: dodaj komentarz oznaczający przetworzenie
                self.add_comment_to_record(record_id, "[AUTO-MULTIPLIED]")
            else:
                logging.error(f"Nie udało się zaktualizować rekordu {record_id}")
        
        if total_original_time > 0:
            original_hours = total_original_time / 3600
            updated_hours = total_updated_time / 3600
            logging.info(f"Użytkownik {user_id}: {original_hours:.2f}h -> {updated_hours:.2f}h")
    
    def add_comment_to_record(self, record_id, comment):
        """Dodaje komentarz do rekordu czasu"""
        # Implementacja zależna od API Everhour
        pass
    
    def run_daily_update(self, process_date=None):
        """Uruchamia aktualizację dla wszystkich użytkowników"""
        if process_date is None:
            process_date = datetime.now().date() - timedelta(days=1)
        
        # Zabezpieczenie przed podwójnym przetwarzaniem
        date_key = process_date.strftime("%Y-%m-%d")
        if date_key in self.processed_dates:
            logging.warning(f"Data {date_key} już była przetworzona!")
            return
        
        logging.info(f"=== Rozpoczynanie aktualizacji czasu za dzień {process_date} ===")
        
        success_count = 0
        error_count = 0
        
        for user_id in EMPLOYEES_WITH_MULTIPLIER:
            if not user_id.strip():  # Pomijaj puste ID
                continue
                
            try:
                self.process_user_time(user_id.strip(), process_date)
                success_count += 1
            except Exception as e:
                logging.error(f"Błąd podczas przetwarzania użytkownika {user_id}: {e}")
                error_count += 1
        
        self.processed_dates.add(date_key)
        
        logging.info(f"=== Aktualizacja zakończona. Sukces: {success_count}, Błędy: {error_count} ===")

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
