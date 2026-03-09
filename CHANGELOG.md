# Changelog

Alle wichtigen Änderungen an diesem Projekt werden hier dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

## [2026-03-09]

### Fixed

- **PR #15**: Leere SRT-Segmente (nur Index + Timestamp) werden bei der Übersetzung erhalten statt stillschweigend übersprungen. Behebt Segmentverlust (113 -> 92) bei SRTs mit leeren Blöcken. Zusätzlich: CRLF-Robustheit, korrekter Ausgabedateiname, Merge-Fallback auf Original-Text.
- **PR #14**: TreeView und Edit-Feld werden bei erneuter Transkription geleert, sodass keine alten Ergebnisse mehr sichtbar bleiben.

### Changed

- **PR #13**: CodeRabbit-Fixes: Logging in ASS-Style-Methoden, Timeout-Guard im Validierungs-Dialog, Drift-Reporting-Genauigkeit, Shell-sichere pip-Kommandos in Doku.

## [2026-03-08]

### Fixed

- **PR #12**: Übersetzungs-Pipeline stabilisiert: 76 Unicode Smart Quotes (SyntaxError!) durch ASCII ersetzt, UTF-8 `errors='replace'`, Import-Scoping für Validierung, Docstring-Coverage auf 91.5%.

### Added

- **PR #12**: Validierungs-Safety-Net: Automatische Prüfung von Segment-Anzahl, leeren Segmenten und Timing-Drift vor dem Einbrennen. Dialog mit "Abbrechen" / "Trotzdem einbrennen".
- **PR #12**: Dynamische Schriftgröße in allen 3 Untertitel-Modi konsistent: `max(9, round(13 * (0.4 + scale_ratio * 0.6)))`.
- **PR #12**: Timing-Default auf `preserve_timing=True` für deutsche Übersetzungen.

## [2026-03-07]

### Added

- **PR #10**: UI-Vereinfachung: 4 klare Aktions-Buttons statt Checkbox/Radio-Logik. Issue #6 gelöst (VLC Auto-Load Verhalten dokumentiert).
- **PR #9**: Standard-SRT-Export-Benennung und deutsche Lesbarkeits-Presets im Translator.

## Ältere Versionen

### Added

- Audio-Transkription mit OpenAI Whisper (Multi-Language, Model-Selection, Segment-Editor)
- Übersetzungs-Engine mit OpenAI, Google Translate und Whisper
- Doppelte Untertitel (Original oben, Übersetzung unten) via SRT -> ASS Pipeline
- Smart Split: Videos in Segmente mit konfigurierbarer Überlappung
- Basis-Skalierung mit FFmpeg
