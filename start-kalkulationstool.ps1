# Startet Backend und Frontend jeweils in einem eigenen PowerShell-Fenster.
# Aufruf aus dem Projektroot:
#   powershell -ExecutionPolicy Bypass -File .\start-kalkulationstool.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

if (-not (Test-Path -LiteralPath $backendDir)) {
    throw "Backend-Verzeichnis nicht gefunden: $backendDir"
}
if (-not (Test-Path -LiteralPath $frontendDir)) {
    throw "Frontend-Verzeichnis nicht gefunden: $frontendDir"
}

Write-Host "Starte Backend in neuem Fenster ($backendDir) ..."
Start-Process -FilePath "powershell.exe" -WorkingDirectory $backendDir -ArgumentList @(
    "-NoExit",
    "-Command",
    "python -m alembic upgrade head; if (`$LASTEXITCODE -ne 0) { Write-Host 'Alembic-Migration fehlgeschlagen.' -ForegroundColor Red; pause; exit `$LASTEXITCODE }; python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
)

Write-Host "Starte Frontend in neuem Fenster ($frontendDir) ..."
Start-Process -FilePath "powershell.exe" -WorkingDirectory $frontendDir -ArgumentList @(
    "-NoExit",
    "-Command",
    "npm run dev"
)

Write-Host ""
Write-Host "Beide Server laufen in eigenen Fenstern."
Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "Frontend: Adresse laut Vite-Ausgabe im Frontend-Fenster"
Write-Host "Beenden:  die beiden geöffneten PowerShell-Fenster schließen"
