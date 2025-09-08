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

REM ========================================

echo.
echo Programm beendet.
echo Virtual Environment ist noch aktiv.
echo.
echo Druecke eine beliebige Taste zum Beenden...
echo (Das Virtual Environment wird automatisch deaktiviert)
pause >nul

REM Virtual Environment wird automatisch deaktiviert wenn die Konsole geschlossen wird
REM Kein explizites "deactivate" nötig!