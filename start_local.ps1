$ErrorActionPreference = "Stop"
$port = 8000

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  YT Download - Mode local (IP de la maison)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

Push-Location "$PSScriptRoot"

Write-Host "`n[1/3] Demarrage du serveur sur http://localhost:$port ..."
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  💡 Laisse cette fenetre OUVERTE." -ForegroundColor Yellow
Write-Host "  Quand tu as fini, ferme-la pour tout arreter." -ForegroundColor Yellow
Write-Host "==============================================" -ForegroundColor Cyan

$existing = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Port $port occupe - nettoyage de l'ancien serveur..." -ForegroundColor Yellow
    $existing | ForEach-Object {
        try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
    }
    Start-Sleep -Seconds 2
    $existing = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($existing) { Write-Host "Erreur : le port $port est toujours occupe. Redemarre le PC." -ForegroundColor Red; exit 1 }
    Write-Host "[OK] Ancien serveur arrete." -ForegroundColor Green
}

$serverProc = Start-Process -FilePath "python" -ArgumentList "main.py" -PassThru -NoNewWindow
# Garantit l'arret meme si la fenetre est fermee via la croix
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    if ($serverProc -and -not $serverProc.HasExited) { Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue }
} -ErrorAction SilentlyContinue
function Test-PortOpen {
    $c = New-Object System.Net.Sockets.TcpClient
    try {
        $r = $c.BeginConnect("localhost", $port, $null, $null)
        if ($r.AsyncWaitHandle.WaitOne(2000)) {
            $c.EndConnect($r)
            return $true
        }
    } catch { }
    finally { $c.Close() }
    return $false
}
$serverReady = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-PortOpen) { $serverReady = $true; break }
}
if (-not $serverReady) {
    Write-Host "Le serveur ne demarre pas. Verifie l'installation de Python puis relance." -ForegroundColor Red
    if ($serverProc) { Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue }
    exit 1
}
Write-Host "[OK] Serveur local lance." -ForegroundColor Green

$lanIP = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.InterfaceAlias -notlike "*vEthernet*" } |
    Sort-Object -Property { $_.InterfaceMetric } |
    Select-Object -First 1).IPAddress

Write-Host "`n[2/3] Lien sur ton reseau WiFi (sans internet) :" -ForegroundColor Green
if ($lanIP) {
    Write-Host "  http://$lanIP`:$port  (meme reseau WiFi uniquement)" -ForegroundColor Cyan
} else {
    Write-Host "  (IP locale introuvable)"
}

Write-Host "`n[3/3] Ton lien permanent (utilise celui-ci sur l'iPhone) :" -ForegroundColor Green

$tail = "C:\Program Files\Tailscale\tailscale.exe"
$tsUrl = $null
if (Test-Path -LiteralPath $tail) {
    try {
        $json = & $tail status --json | ConvertFrom-Json
        $tsUrl = "https://" + $json.Self.DNSName.TrimEnd('.')
    } catch { }
}
if ($tsUrl) {
    Write-Host "  $tsUrl" -ForegroundColor Cyan
    Write-Host "  (URL fixe : meme PC, meme WiFi ou en dehors, cette adresse ne change jamais)" -ForegroundColor Yellow
} else {
    Write-Host "  (Tailscale introuvable. Utilise l'IP locale ci-dessus avec ton iPhone sur le meme WiFi.)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  Serveur en cours d'execution.                 " -ForegroundColor Green
Write-Host "  Ferme cette fenetre pour tout arreter.       " -ForegroundColor Yellow
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""
try {
    Read-Host "Appuie sur Entree pour arreter le serveur"
} finally {
    if ($serverProc -and -not $serverProc.HasExited) { Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue }
    Unregister-Event -SourceIdentifier PowerShell.Exiting -ErrorAction SilentlyContinue
    Get-Job | Remove-Job -Force -ErrorAction SilentlyContinue
}
Pop-Location