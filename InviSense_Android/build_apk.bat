@echo off
echo ==========================================
echo   Building InviSense Android Application
echo ==========================================

set GRADLE_BIN=C:\Users\tonyj\.gradle\wrapper\dists\gradle-8.4-all\56r6xik2f6skrm47et0ibifug\gradle-8.4\bin\gradle.bat

if exist "%GRADLE_BIN%" (
    call "%GRADLE_BIN%" assembleDebug
) else (
    call gradle assembleDebug
)

echo.
echo ==========================================
echo   Build Finished!
echo   APK Location:
echo   app\build\outputs\apk\debug\app-debug.apk
echo ==========================================
pause
