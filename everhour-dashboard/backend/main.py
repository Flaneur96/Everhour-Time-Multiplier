from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import os
import json
import asyncpg
from contextlib import asynccontextmanager
import logging
import requests

# Konfiguracja
DATABASE_URL = os.environ.get("DATABASE_URL")
EVERHOUR_API_KEY = os.environ.get("EVERHOUR_API_KEY")
DASHBOARD_SECRET = os.environ.get("DASHBOARD_SECRET", "your-secret-key")
BASE_URL = "https://api.everhour.com"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Prosta weryfikacja tokena"""
    if credentials.credentials != DASHBOARD_SECRET:
        raise HTTPException(status_code=403, detail="Invalid authentication")
    return credentials.credentials

# Models
class Employee(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    multiplier: float = 1.5
    active: bool = True
    created_at: Optional[datetime] = None

class UpdateEmployee(BaseModel):
    multiplier: Optional[float] = None
    active: Optional[bool] = None

class SystemConfig(BaseModel):
    run_hour: int
    run_minute: int
    default_multiplier: float
    dry_run: bool

class OperationLog(BaseModel):
    id: Optional[int] = None
    employee_id: str
    employee_name: str
    date: str
    original_hours: float
    updated_hours: float
    status: str
    created_at: Optional[datetime] = None

class DashboardStats(BaseModel):
    total_employees: int
    active_employees: int
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    total_hours_added_this_week: float
    total_hours_added_this_month: float

# Database connection
@asynccontextmanager
async def get_db():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        await conn.close()

# Database initialization
async def init_db():
    """Inicjalizuje tabele w bazie danych"""
    async with get_db() as conn:
        # Tabela pracowników
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                multiplier FLOAT DEFAULT 1.5,
                active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela konfiguracji
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS system_config (
                id INTEGER PRIMARY KEY DEFAULT 1,
                run_hour INTEGER DEFAULT 1,
                run_minute INTEGER DEFAULT 0,
                default_multiplier FLOAT DEFAULT 1.5,
                dry_run BOOLEAN DEFAULT true,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela logów operacji
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS operation_logs (
                id SERIAL PRIMARY KEY,
                employee_id VARCHAR(50),
                employee_name VARCHAR(255),
                date DATE,
                original_hours FLOAT,
                updated_hours FLOAT,
                status VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Domyślna konfiguracja
        await conn.execute('''
            INSERT INTO system_config (run_hour, run_minute, default_multiplier, dry_run)
            VALUES (1, 0, 1.5, true)
            ON CONFLICT (id) DO NOTHING
        ''')

# FastAPI app
app = FastAPI(title="Everhour Time Multiplier Dashboard API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # W produkcji ustaw konkretne domeny
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Inicjalizacja przy starcie"""
    await init_db()
    logger.info("Dashboard API started")

# Endpoints
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now()}

@app.get("/api/stats", response_model=DashboardStats)
async def get_dashboard_stats(token: str = Depends(verify_token)):
    """Pobiera statystyki dashboard"""
    async with get_db() as conn:
        # Liczba pracowników
        total_employees = await conn.fetchval("SELECT COUNT(*) FROM employees")
        active_employees = await conn.fetchval("SELECT COUNT(*) FROM employees WHERE active = true")
        
        # Ostatnie uruchomienie
        last_run = await conn.fetchval(
            "SELECT MAX(created_at) FROM operation_logs WHERE status = 'success'"
        )
        
        # Następne uruchomienie
        config = await conn.fetchrow("SELECT run_hour, run_minute FROM system_config WHERE id = 1")
        next_run = None
        if config:
            now = datetime.now()
            next_run = now.replace(hour=config['run_hour'], minute=config['run_minute'], second=0)
            if next_run <= now:
                next_run += timedelta(days=1)
        
        # Godziny dodane w tym tygodniu
        week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        week_hours = await conn.fetchval(
            """
            SELECT COALESCE(SUM(updated_hours - original_hours), 0)
            FROM operation_logs
            WHERE created_at >= $1 AND status = 'success'
            """,
            week_start
        )
        
        # Godziny dodane w tym miesiącu
        month_start = datetime.now().replace(day=1)
        month_hours = await conn.fetchval(
            """
            SELECT COALESCE(SUM(updated_hours - original_hours), 0)
            FROM operation_logs
            WHERE created_at >= $1 AND status = 'success'
            """,
            month_start
        )
        
        return DashboardStats(
            total_employees=total_employees,
            active_employees=active_employees,
            last_run=last_run,
            next_run=next_run,
            total_hours_added_this_week=float(week_hours or 0),
            total_hours_added_this_month=float(month_hours or 0)
        )

@app.get("/api/employees", response_model=List[Employee])
async def get_employees(token: str = Depends(verify_token)):
    """Pobiera listę pracowników"""
    async with get_db() as conn:
        rows = await conn.fetch(
            "SELECT * FROM employees ORDER BY name"
        )
        return [Employee(**dict(row)) for row in rows]

@app.post("/api/employees", response_model=Employee)
async def add_employee(employee_id: str, token: str = Depends(verify_token)):
    """Dodaje pracownika do systemu"""
    # Pobierz dane z Everhour API
    headers = {"X-Api-Key": EVERHOUR_API_KEY}
    response = requests.get(f"{BASE_URL}/users/{employee_id}", headers=headers)
    
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="Employee not found in Everhour")
    
    user_data = response.json()
    
    async with get_db() as conn:
        # Sprawdź czy już istnieje
        existing = await conn.fetchrow("SELECT * FROM employees WHERE id = $1", employee_id)
        if existing:
            raise HTTPException(status_code=400, detail="Employee already exists")
        
        # Dodaj do bazy
        row = await conn.fetchrow(
            """
            INSERT INTO employees (id, name, email, multiplier, active)
            VALUES ($1, $2, $3, $4, true)
            RETURNING *
            """,
            employee_id,
            user_data.get('name', 'Unknown'),
            user_data.get('email'),
            1.5
        )
        return Employee(**dict(row))

@app.patch("/api/employees/{employee_id}", response_model=Employee)
async def update_employee(
    employee_id: str,
    update: UpdateEmployee,
    token: str = Depends(verify_token)
):
    """Aktualizuje dane pracownika"""
    async with get_db() as conn:
        # Buduj zapytanie UPDATE dynamicznie
        updates = []
        values = []
        i = 1
        
        if update.multiplier is not None:
            updates.append(f"multiplier = ${i}")
            values.append(update.multiplier)
            i += 1
        
        if update.active is not None:
            updates.append(f"active = ${i}")
            values.append(update.active)
            i += 1
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        values.append(employee_id)
        query = f"""
            UPDATE employees
            SET {', '.join(updates)}
            WHERE id = ${i}
            RETURNING *
        """
        
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        return Employee(**dict(row))

@app.delete("/api/employees/{employee_id}")
async def delete_employee(employee_id: str, token: str = Depends(verify_token)):
    """Usuwa pracownika z systemu"""
    async with get_db() as conn:
        result = await conn.execute(
            "DELETE FROM employees WHERE id = $1",
            employee_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Employee not found")
        return {"message": "Employee deleted"}

@app.get("/api/config", response_model=SystemConfig)
async def get_config(token: str = Depends(verify_token)):
    """Pobiera konfigurację systemu"""
    async with get_db() as conn:
        row = await conn.fetchrow("SELECT * FROM system_config WHERE id = 1")
        return SystemConfig(**dict(row))

@app.put("/api/config", response_model=SystemConfig)
async def update_config(config: SystemConfig, token: str = Depends(verify_token)):
    """Aktualizuje konfigurację systemu"""
    async with get_db() as conn:
        row = await conn.fetchrow(
            """
            UPDATE system_config
            SET run_hour = $1, run_minute = $2, default_multiplier = $3, dry_run = $4
            WHERE id = 1
            RETURNING *
            """,
            config.run_hour,
            config.run_minute,
            config.default_multiplier,
            config.dry_run
        )
        
        # TODO: Tutaj możesz dodać logikę do restartu głównego skryptu z nowymi ustawieniami
        
        return SystemConfig(**dict(row))

@app.get("/api/logs", response_model=List[OperationLog])
async def get_logs(
    limit: int = 100,
    offset: int = 0,
    employee_id: Optional[str] = None,
    token: str = Depends(verify_token)
):
    """Pobiera logi operacji"""
    async with get_db() as conn:
        query = "SELECT * FROM operation_logs"
        params = []
        
        if employee_id:
            query += " WHERE employee_id = $1"
            params.append(employee_id)
        
        query += " ORDER BY created_at DESC LIMIT $%d OFFSET $%d" % (
            len(params) + 1,
            len(params) + 2
        )
        params.extend([limit, offset])
        
        rows = await conn.fetch(query, *params)
        return [OperationLog(**dict(row)) for row in rows]

@app.post("/api/trigger-update")
async def trigger_manual_update(
    employee_id: Optional[str] = None,
    date: Optional[str] = None,
    token: str = Depends(verify_token)
):
    """Ręcznie uruchamia aktualizację"""
    # TODO: Implementacja komunikacji z głównym skryptem
    # Możesz użyć Redis Queue, Celery lub prostego HTTP call
    return {
        "message": "Update triggered",
        "employee_id": employee_id,
        "date": date
    }

# Endpoint do zapisywania logów z głównego skryptu
@app.post("/api/logs/record")
async def record_operation(log: OperationLog, token: str = Depends(verify_token)):
    """Zapisuje log operacji (wywoływane przez główny skrypt)"""
    async with get_db() as conn:
        await conn.execute(
            """
            INSERT INTO operation_logs (employee_id, employee_name, date, original_hours, updated_hours, status)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            log.employee_id,
            log.employee_name,
            log.date,
            log.original_hours,
            log.updated_hours,
            log.status
        )
        return {"message": "Log recorded"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
