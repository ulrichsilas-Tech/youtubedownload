@echo off
title YT Download - Serveur local
echo.
echo ==========================================
echo    YT Download - Demarrage automatique
echo ==========================================
echo.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_local.ps1"
echo.
echo ==========================================
echo    Serveur arrete. Tu peux fermer cette
echo    fenetre.
echo ==========================================
echo.
pause