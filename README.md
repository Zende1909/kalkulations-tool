# Kalkulations-Tool

Kalkulationstool für Kunststoffmodule in der Automotive-Zulieferindustrie.

## Bereiche

- Stammdatenverwaltung
- Spritzguss-Kalkulation
- Veredelung
- Investitionen
- Baugruppen
- Dashboard

## Lokale Entwicklung

Backend:

```powershell
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm.cmd run dev -- --port 5173
```

### Optionale lokale Seeds (CLI only)

Seeds laufen **nicht** beim App-Start und **nicht** über Alembic. Nur gegen lokale
`DATABASE_URL` (localhost / 127.0.0.1 / sqlite), aus `backend/`:

```powershell
# Admin (zusätzlich LOCAL_ADMIN_SEED_ENABLED + Email/Passwort nötig)
python -m app.scripts.seed_admin

# TOP_LEVEL-Zuschlagssätze vvgk / gewinn / skonto (idempotent)
python -m app.scripts.seed_top_level_markup_rates
```

Details: `backend/alembic/README.md`.

## Docker Compose

Produktion (Standard): Backend mit `APP_ENV=production`, wartet auf DB-Healthcheck,
führt `alembic upgrade head` aus, startet dann Uvicorn. Keine automatischen Seeds.
`JWT_SECRET_KEY` muss in `.env` gesetzt sein (kein Default).

```powershell
docker compose up --build
```

Lokale Compose-Entwicklung (Reload + Bind-Mount):

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

