# Loops MVP — démarrage du backend
# Usage : clic-droit > "Exécuter avec PowerShell"  ou  .\start.ps1

$PORT = 8765
$BACKEND = "$PSScriptRoot\backend"

# Libère le port si occupé par un ancien uvicorn
$oldPid = (netstat -ano | Select-String ":$PORT\s" | Select-Object -First 1) -replace '.*\s(\d+)$','$1'
if ($oldPid -match '^\d+$') {
    $proc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
    if ($proc -and $proc.Name -eq "python") {
        Write-Host "Arrêt de l'ancien processus uvicorn (PID $oldPid)..."
        Stop-Process -Id $oldPid -Force
        Start-Sleep -Seconds 1
    }
}

Write-Host "Démarrage du backend sur http://localhost:$PORT ..."
Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "main:app", "--port", "$PORT", "--reload" `
    -WorkingDirectory $BACKEND `
    -WindowStyle Normal

Start-Sleep -Seconds 3
Write-Host ""
Write-Host "Backend actif sur http://localhost:$PORT"
Write-Host "Ouvre frontend\index.html dans ton navigateur."
