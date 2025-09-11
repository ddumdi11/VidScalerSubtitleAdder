@echo off
REM ========================================
REM VidScalerSubtitleAdder - Tkinter GUI Starter
REM ========================================

REM Wechsle zum Projektverzeichnis (falls die .bat nicht im Projektordner liegt)
cd /d "%~dp0"

REM Zeige aktuelles Verzeichnis
echo Starte VidScalerSubtitleAdder in: %CD%

REM Prüfe ob .venv Ordner existiert
if not exist ".venv" (
    echo FEHLER: .venv Ordner nicht gefunden!
    echo Bitte erstelle zuerst ein Virtual Environment mit: python -m venv .venv
    pause
    exit /b 1
)

REM Aktiviere das Virtual Environment
echo Aktiviere Virtual Environment...
call .venv\Scripts\activate.bat

REM Prüfe ob Aktivierung erfolgreich war
if "%VIRTUAL_ENV%"=="" (
    echo FEHLER: Virtual Environment konnte nicht aktiviert werden!
    pause
    exit /b 1
)

echo Virtual Environment aktiviert: %VIRTUAL_ENV%
echo.

REM ========================================
REM VidScalerSubtitleAdder GUI starten
REM ========================================

echo Starte VidScalerSubtitleAdder GUI...
python vidscaler.py

REM Check exit code immediately after python command
if %ERRORLEVEL% neq 0 (
    echo.
    echo FEHLER: GUI wurde mit Exit-Code %ERRORLEVEL% beendet!
    echo Mögliche Ursachen: Python-Fehler, fehlende Dependencies, etc.
    echo Bitte prüfe die obigen Fehlermeldungen.
    echo.
    echo Druecke eine beliebige Taste um die Konsole zu schließen...
    pause >nul
) else (
    echo.
    echo GUI wurde normal geschlossen. Konsole schließt automatisch in 3 Sekunden...
    timeout /t 3 >nul
)

REM ========================================

REM Virtual Environment wird automatisch deaktiviert wenn die Konsole geschlossen wird
REM Kein explizites "deactivate" nötig!