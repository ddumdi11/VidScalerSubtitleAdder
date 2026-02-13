# VidScaler

Eine benutzerfreundliche GUI-Anwendung zum Skalieren von Videos mit FFmpeg – inklusive Untertitel-Einbettung, automatischer Audio-Transkription und mehrsprachiger Übersetzung.

## Überblick

VidScaler vereinfacht das Skalieren von Videos unter Windows. Die Anwendung zeigt die aktuelle Videoauflösung an und bietet eine Dropdown-Liste mit optimierten Skalierungsoptionen, um die Dateigröße zu reduzieren und gleichzeitig die bestmögliche Qualität zu erhalten.

## Funktionen

- **Smart-Skalierung**: Dropdown-Menü mit optimierten Skalierungswerten (automatisch gerade Pixelwerte)
- **Untertitel-Einbettung**: Brennt .srt-Untertitel in einen schwarzen Balken unterhalb des Videos ein
- **Audio-Transkription**: Erstellt automatisch SRT-Dateien aus Video-Audio mit OpenAI Whisper
- **Mehrsprachige Übersetzung**: Untertitel übersetzen mit drei Methoden:
  - **OpenAI Translation** (beste Qualität): KI-Übersetzung via smart-srt-translator
  - **Google Translate** (schnell): Kostenlose, schnelle Übersetzung
  - **Whisper Translation** (lokal): Lokale Übersetzung, nur nach Englisch
- **Dual Subtitles**: Original-Untertitel oben, Übersetzung unten – perfekt für Sprachlerner
- **Smart Split**: Videos automatisch in konfigurierbare Segmente aufteilen (mit Überlappung)
- **Text-Exzerpt**: Konvertiert SRT-Dateien zu gut lesbaren Text-/Markdown-Dokumenten mit KI-Veredelung

## Voraussetzungen

- **Python 3.7+** (tkinter ist bereits enthalten)
- **FFmpeg** muss installiert und im PATH verfügbar sein
  - Download: <https://ffmpeg.org/download.html>
  - Alternativ via Chocolatey: `choco install ffmpeg`

## Installation

1. Repository klonen:

   ```bash
   git clone https://github.com/ddumdi11/VidScalerSubtitleAdder.git
   cd VidScalerSubtitleAdder
   ```

2. Virtuelle Umgebung einrichten und aktivieren:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Dependencies installieren:

   ```bash
   pip install -r requirements.txt
   ```

4. Anwendung starten:

   ```bash
   python vidscaler.py
   ```

Oder einfach per Doppelklick: `start.bat`

## Verwendung

### Grundlegender Workflow

1. **Video auswählen** und **"Video analysieren"** klicken – aktuelle Auflösung wird angezeigt
2. Gewünschte **Skalierung** aus dem Dropdown-Menü wählen
3. Optional: **"Audio transkribieren"** klicken, um SRT-Untertitel aus dem Audio zu erstellen
4. Optional: **Übersetzung** konfigurieren (Quell-/Zielsprache und Methode wählen)

### Aktions-Buttons

| Button | Beschreibung | Ausgabe-Suffix |
| --- | --- | --- |
| **Video skalieren** | Nur Skalierung, keine Untertitel | `_scaled` |
| **Mit Original-Untertiteln** | Original-SRT im schwarzen Balken unter dem Video | `_subtitled` |
| **Mit Übersetzung** | Nur übersetzte Untertitel im schwarzen Balken | `_translated` |
| **Mit Original + Übersetzung** | Original oben, Übersetzung unten (Dual Mode) | `_dual_subtitled` |

### Weitere Features

- **Smart Split**: Checkbox aktivieren, Teillänge (1–60 Min) und Überlappung (0–30 Sek) einstellen. Das Video wird nach der Verarbeitung automatisch aufgeteilt.
- **Text-Exzerpt**: SRT zu lesbarem Text/Markdown konvertieren – optional mit SpaCy (Satzgrenzen) und OpenAI (KI-Veredelung).

## Technische Details

Die Anwendung verwendet folgende FFmpeg-Filter:

**Skalierung:**
```bash
ffmpeg -i input.mp4 -vf "scale=WIDTH:-2" output_scaled.mp4
```

**Untertitel (einzeln):**
```bash
ffmpeg -i input.mp4 -vf "scale=WIDTH:-2,pad=iw:ih+100:0:0:black,subtitles=file.srt:charenc=UTF-8" output_subtitled.mp4
```

**Dual Subtitles (SRT → ASS Pipeline):**
```bash
ffmpeg -i input.mp4 -vf "scale=WIDTH:-2,pad=iw:ih+300:0:140:black,ass=original.ass,ass=translated.ass" output.mp4
```

- `-2` erzwingt gerade Pixelwerte für Codec-Kompatibilität
- `pad` erweitert das Video um einen schwarzen Balken für Untertitel
- `subtitles=` brennt SRT direkt ein, `ass=` ermöglicht präzise Style-Kontrolle

## Fehlerbehebung

**FFmpeg nicht gefunden:**
Stelle sicher, dass FFmpeg korrekt installiert und im System-PATH verfügbar ist.

**Untertitel werden nicht angezeigt:**

- Prüfe, ob die .srt-Datei korrekt formatiert ist (UTF-8)
- Unterstützte Formate: .srt, .ass, .vtt

**Doppelte Untertitel in VLC:**
VLC lädt automatisch externe SRT-Dateien mit gleichem Basisnamen. Wenn `_translated.mp4` und `_translated.srt` im selben Ordner liegen, zeigt VLC die Untertitel doppelt an. Lösung: In VLC unter *Untertitel → Unterspur → Deaktivieren*.

## Lizenz

Dieses Projekt steht unter der MIT-Lizenz.
