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

$portInUse = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if ($portInUse) { Write-Host "Erreur : le port $port est deja utilise. Ferme l'ancienne fenetre." -ForegroundColor Red; exit 1 }

$serverProc = Start-Process -FilePath "python" -ArgumentList "main.py" -PassThru -NoNewWindow
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

Write-Host "`n[3/3] Lancement du tunnel public Cloudflare..." -ForegroundColor Green
Write-Host "(URL valable tant que cette fenetre est ouverte)" -ForegroundColor Cyan

$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cf) {
    $cfPath = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
    if (Test-Path -LiteralPath $cfPath) { $cf = Get-Item -LiteralPath $cfPath }
}
if ($cf) {
    $cfExe = if ($cf.Source) { $cf.Source } else { $cf.FullName }
    $ErrorActionPreference = "Continue"
    try {
        & $cfExe tunnel --url "http://localhost:$port"
    } catch {
        Write-Host "Cloudflared a echoue. Utilise l'IP locale ci-dessus (iPhone sur le meme WiFi)." -ForegroundColor Yellow
    }
} else {
    Write-Host "Cloudflared introuvable. Utilise l'IP locale ci-dessus. (installe : winget install Cloudflare.cloudflared)" -ForegroundColor Yellow
}

# Arrêt du serveur quand on ferme
if ($serverProc -and -not $serverProc.HasExited) { Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue }
Pop-Location