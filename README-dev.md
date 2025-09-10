# VidScaler

Eine benutzerfreundliche GUI-Anwendung zum Skalieren von Videos mit FFmpeg.

## Überblick

VidScaler vereinfacht das Skalieren von Videos, die mit dem Windows Snipping-Tool aufgenommen wurden. Die Anwendung zeigt die aktuelle Videoauflösung an und bietet eine Dropdown-Liste mit optimierten Skalierungsoptionen, um die Dateigröße zu reduzieren und gleichzeitig die bestmögliche Qualität zu erhalten.

## Funktionen

- **Video-Auswahl**: Einfache Dateiauswahl über GUI
- **Auflösungsanzeige**: Zeigt aktuelle Videomaße (Breite x Höhe)
- **Smart-Skalierung**: Dropdown-Menü mit vorgeschlagenen Skalierungswerten
  - Automatische Berechnung gerader Pixelwerte (durch 2 teilbar)
  - Sortierung von bester zu niedrigster Qualität
- **FFmpeg-Integration**: Nahtlose Videobearbeitung über Python subprocess
- **Windows-optimiert**: Speziell für Windows 11 entwickelt
- **Untertitel-Einfügen**: Brennt Untertitel aus .srt-Dateien unterhalb des Videos ein (mit automatischer Videoerweiterung)
- **🆕 Audio-Transkription**: Erstellt automatisch SRT-Dateien aus Video-Audio mit OpenAI Whisper
- **Untertitel-Übersetzer**: Zeigt Original-Untertitel oberhalb und übersetzte Untertitel unterhalb des Videos an - wahlweise auch nur die Übersetzung
  - **OpenAI Translation (beste Qualität)**: Hochwertige KI-Übersetzung via smart-srt-translator 
  - **Google Translate (schnell)**: Kostenlose, schnelle Übersetzung
  - **Whisper Translation (English-only)**: Lokale Übersetzung, nur nach Englisch
- **📄 Text-Exzerpt**: Konvertiert SRT-Dateien zu gut lesbaren Text-/Markdown-Dokumenten mit KI-Veredelung

## Voraussetzungen

- **Python 3.7+** (tkinter ist bereits enthalten)
- **FFmpeg** muss installiert und im PATH verfügbar sein
  - Download: https://ffmpeg.org/download.html
  - Alternativ via chocolatey: `choco install ffmpeg`

## Installation

1. Repository klonen oder herunterladen
2. FFmpeg installieren (falls noch nicht vorhanden)
3. Virtuelle Umgebung einrichten und aktivieren:
   ```bash
   cd VidScaler
   py -m venv .venv
   .venv\Scripts\activate.bat
   ```
4. **Für erweiterte Features:** Dependencies installieren:
   ```bash
   py -m pip install -r requirements.txt
   ```
   Optional für Text-Exzerpt:
   ```bash
   pip install spacy openai
   python -m spacy download de_core_news_sm  # Deutsches Sprachmodell
   python -m spacy download en_core_web_sm # Englisches Sprachmodell "efficiency"
   ```
5. Anwendung starten:
   ```bash
   py vidscaler.py
   ```

## Verwendung

1. Sicherstellen, dass die virtuelle Umgebung aktiv ist:
   ```bash
   .venv\Scripts\activate.bat
   ```
2. Anwendung starten:
   ```bash
   py vidscaler.py
   ```
3. "Video auswählen" klicken und gewünschte Videodatei auswählen
4. "Video analysieren" klicken - aktuelle Auflösung wird angezeigt
5. Gewünschte Skalierung aus Dropdown-Menü wählen
6. **🆕 SRT aus Audio erstellen:** "Audio transkribieren" klicken → separates Fenster öffnet sich → Audio wird extrahiert und mit Whisper transkribiert → Text editieren → als SRT exportieren
7. **📄 Text-Exzerpt erstellen:** "Text-Exzerpt erstellen" klicken → SRT wird zu gut lesbarem Text verarbeitet → optional mit SpaCy (Satzgrenzen) und OpenAI (KI-Veredelung) → als .txt oder .md exportieren
8. **Ohne Untertitel:** "Video skalieren" klicken - das bearbeitete Video wird mit "_scaled" Suffix gespeichert
9. **Mit Untertiteln:** "Untertitel wählen..." klicken und .srt-Datei auswählen, dann "Mit Untertiteln skalieren" - das Video wird mit "_subtitled" Suffix gespeichert

## Technische Details

Die Anwendung verwendet folgende FFmpeg-Befehle:

**Normale Skalierung:**
```bash
ffmpeg -i input.mp4 -vf scale=WIDTH:-1 output_scaled.mp4
```

**Skalierung mit Untertiteln:**
```bash
ffmpeg -i input.mp4 -vf "scale=WIDTH:-2,pad=iw:ih+100:0:0:black,subtitles=subtitles.srt:force_style='Alignment=2,MarginV=20'" output_subtitled.mp4
```

- `-1` sorgt für automatische, proportionale Höhenberechnung
- `-2` erzwingt gerade Pixelwerte für bessere Kompatibilität  
- `pad` erweitert das Video um 100px nach unten für Untertitel
- `subtitles` brennt die Untertitel unten ins Video ein

## Fehlerbehebung

**"Höhe nicht durch 2 teilbar" Fehler**: 
Die Anwendung berechnet automatisch gerade Pixelwerte, um diesen häufigen FFmpeg-Fehler zu vermeiden.

**FFmpeg nicht gefunden**: 
Stelle sicher, dass FFmpeg korrekt installiert und im System-PATH verfügbar ist.

**Untertitel werden nicht angezeigt**:
- Prüfe, ob die .srt-Datei korrekt formatiert ist
- Unterstützte Formate: .srt, .ass, .vtt
- Stelle sicher, dass die Zeitangaben im Video existieren

## Lizenz

Dieses Projekt steht unter der MIT-Lizenz.