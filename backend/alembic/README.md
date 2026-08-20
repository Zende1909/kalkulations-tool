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
`alembic_version.version_num = e1a0001_baseline`.

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

## Beziehung zu Startup (`create_all` / `ensure_*`)

AP1 ändert das Startup-Verhalten **nicht**. `create_all` und `ensure_*`
laufen weiterhin. Spätere Arbeitspakete (AP2) entkoppeln Startup und
Migrationen.
