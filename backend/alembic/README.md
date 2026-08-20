# Alembic – kontrollierte Datenbank-Migrationen

## Überblick

Alembic ist eingerichtet. Die **Baseline** `e1a0001_baseline` bildet den
aktuellen Schema-Stand explizit ab (DDL only: Tabellen, Indizes, FKs,
Unique-/Check-Constraints, PostgreSQL-Enum, JSONB).

- Kein ORM-`create_all` in der Revision
- Keine Seed-Daten (kein Admin, keine Zuschlagssätze)
- Keine Daten-Updates
- Bestehende GEMEINKOSTEN-Datensätze werden nicht angefasst
- vvgk / gewinn / skonto werden **nicht** automatisch geseedet

Die Konfiguration liest `DATABASE_URL` ausschließlich über
`app.config.settings` (Umgebung / `.env`). In `alembic.ini` stehen
**keine** Passwörter.

## Fall 1: Frische Datenbank

Schema anlegen und Alembic-Version setzen:

```powershell
cd backend
# DATABASE_URL auf eine leere Test-/Dev-DB zeigen (nicht Produktion)
alembic upgrade head
```

Erwartetes Ergebnis: alle Anwendungstabellen existieren,
`alembic_version.version_num` = aktueller Head
(derzeit `e1a0004_m5_assembly_positions`).

## Fall 2: Bereits vorhandene Datenbank

Wenn Tabellen bereits durch `create_all` / `db_upgrade` existieren:

1. Schema manuell gegen die Models prüfen (Spalten, JSONB, Enums, FKs, Indizes, Constraints).
2. **Nur nach ausdrücklicher Freigabe** die Baseline stampen (kein `upgrade`,
   sonst drohen Konflikte mit bestehenden Objekten):

```powershell
cd backend
alembic stamp e1a0001_baseline
```

**Niemals** automatisch `stamp` oder `upgrade` gegen die bestehende lokale
Arbeits-DB oder Produktion ausführen, ohne Freigabe.

## Downgrade

Die Baseline-Revision unterstützt **keinen** Downgrade. Ein `DROP` aller
Tabellen wäre destruktiv und ist bewusst mit `NotImplementedError` blockiert.

## Nützliche Befehle (ohne Datenänderung)

```powershell
cd backend
alembic history
alembic heads
# Nur wenn DATABASE_URL bewusst gesetzt ist und Freigabe vorliegt:
# alembic current
```

## Beziehung zu Startup (AP2)

**Produktion** (`APP_ENV=production`):

- Kein `create_all`, keine `ensure_*`, keine Seeds
- Startup prüft JWT, DB-Verbindung und **read-only** den Alembic-Head
- Fehlende oder abweichende Revision → klarer Startup-Fehler

**Entwicklung / Tests** (Standard):

- Kontrollierter Schema-Bootstrap: `create_all` + `ensure_*` (nur DDL) – **kein** automatischer Admin-Seed
- Override: `ALLOW_STARTUP_SCHEMA_BOOTSTRAP=false` erzwingt dieselbe Alembic-Prüfung wie in Produktion
- In Produktion ist Bootstrap **hart deaktiviert** (auch wenn das Flag gesetzt ist)

`ensure_*` enthält keine DML mehr (keine Investitions-Status-/Name-Updates).

## Admin-Seed (CLI only)

Der lokale Admin wird **nicht** beim App-Start angelegt. Explizit aus `backend/`:

```bash
# Windows (PowerShell): $env:LOCAL_ADMIN_SEED_ENABLED="true"; …
set LOCAL_ADMIN_SEED_ENABLED=true
set LOCAL_ADMIN_EMAIL=admin@example.com
set LOCAL_ADMIN_PASSWORD=...
python -m app.scripts.seed_admin
```

Voraussetzungen: `LOCAL_ADMIN_SEED_ENABLED`, lokale `DATABASE_URL` (localhost / 127.0.0.1 / sqlite) und gesetzte Zugangsdaten. Bestehende Benutzer bleiben unverändert (idempotent).

## Top-Level-Markup-Seed (CLI only)

Die Sätze `vvgk` / `gewinn` / `skonto` werden **nicht** beim App-Start und **nicht**
über Alembic angelegt. Explizit aus `backend/`:

```bash
python -m app.scripts.seed_top_level_markup_rates
```

Voraussetzungen und Grenzen:

- `DATABASE_URL` muss lokal sein (localhost / 127.0.0.1 / sqlite)
- nur fehlende **aktive** Sätze für `vvgk`, `gewinn`, `skonto` werden eingefügt
- bestehende `GEMEINKOSTEN`-, `GEWINN`- und `VERSCHROTTUNG`-Zeilen bleiben unverändert
- erneutes Ausführen ist idempotent (`skip:` für bereits aktive Typen)

## Docker Compose (AP3)

Standard-`docker-compose.yml` startet das Backend mit `APP_ENV=production`:

1. `db` wird healthy (`pg_isready`)
2. Backend-Entrypoint: `python -m alembic upgrade head` (Fehler → Container-Exit, kein Uvicorn)
3. danach `uvicorn` (keine Seeds)

`JWT_SECRET_KEY` muss gesetzt sein (kein Compose-Default, kein
`change-me-in-production`). `DATABASE_URL` zeigt auf den Service `db`.

Lokale Compose-Entwicklung mit Reload:

```powershell
# JWT_SECRET_KEY in .env setzen (nicht der Default-Wert)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```
