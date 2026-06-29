@echo off
title Start All Dashboards
echo ==========================================
echo  Starting All Dashboards
echo ==========================================
echo.

echo [1] Tesseract Dashboard - :3000 (pm2 managed)
powershell -Command "if (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue) { Write-Host '  Already running' } else { Write-Host '  NOT running - start elevated pm2 manually' }"

echo [2] PriceHawk - :3050
start "PriceHawk :3050" cmd /k "cd /d C:\Claude\pricehawk && node server.js"

echo [3] Meta Ads Automation - :3040
start "Meta Ads :3040" cmd /k "cd /d C:\Claude\meta-ads-automation && node ui/server.js"

echo [4] Job Auto-Apply - :5050 (hidden)
powershell -Command "Start-Process 'C:\Users\sanks\AppData\Local\Python\bin\pythonw.exe' -ArgumentList 'dashboard/app.py' -WorkingDirectory 'C:\Claude\job-autoapply'"

echo.
echo ==========================================
echo  Dashboards launched in separate windows
echo  Marketing Automation also uses :3040
echo  - run separately if needed (conflicts with Meta Ads)
echo ==========================================
pause
