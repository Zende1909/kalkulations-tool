# Kalkulations-Tool

Kalkulationstool für Kunststoffmodule in der Automotive-Zuliefererindustrie.

## Tech-Stack

- **Frontend:** React + TypeScript + Tailwind CSS + AG Grid (Vite)
- **Backend:** Python + FastAPI + SQLAlchemy
- **Datenbank:** PostgreSQL (Docker)

## Schnellstart

```bash
cp .env.example .env
docker compose up --build
```

| Service      | URL                          |
|--------------|------------------------------|
| Frontend     | http://localhost:5173        |
| Backend API  | http://localhost:8000        |
| Swagger Docs | http://localhost:8000/docs   |
| PostgreSQL   | localhost:5432               |

## Standard-Login

Nach dem ersten Start wird automatisch ein Admin-Benutzer angelegt:

- **E-Mail:** admin@kalkulation.local
- **Passwort:** admin123

## Rollen

| Rolle       | Berechtigung                          |
|-------------|---------------------------------------|
| `admin`     | Vollzugriff inkl. Benutzerverwaltung  |
| `kalkulator`| Stammdaten lesen & schreiben          |
| `viewer`    | Nur Lesen                             |
