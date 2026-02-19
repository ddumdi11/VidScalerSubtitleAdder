"""
Subtitle Validator - Prüft übersetzte SRT-Dateien auf Qualitätsprobleme
vor dem Einbrennen ins Video.
"""

import re
from typing import List, Dict, Optional, NamedTuple


class ValidationResult(NamedTuple):
    """Ergebnis der Übersetzungs-Validierung."""
    is_valid: bool              # True = keine Probleme erkannt
    empty_count: int            # Anzahl leerer Segmente (wo Original Text hat)
    total_count: int            # Gesamtzahl Segmente
    empty_percentage: float     # Prozent leere Segmente
    drift_start: Optional[int]  # Segment-Nummer ab der Drift erkannt wurde (oder None)
    drift_amount: int           # Geschätzte Anzahl verschobener Segmente
    details: str                # Menschenlesbarer Bericht


def parse_srt_segments(srt_path: str) -> List[Dict]:
    """Parsed SRT-Datei und gibt Segmente zurück.

    Jedes Segment hat: index, timestamp, text
    """
    segments = []
    with open(srt_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read().strip()

    blocks = re.split(r'\r?\n\r?\n', content)
    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().splitlines()
        if len(lines) < 2:  # Bewusst < 2 (nicht < 3): Validator braucht auch
            continue        # text-leere Segmente, um sie als "leer" zu erkennen
        try:
            index = int(lines[0])
            timestamp = lines[1]
            text = '\n'.join(lines[2:]).strip()
            segments.append({
                'index': index,
                'timestamp': timestamp,
                'text': text
            })
        except (ValueError, IndexError):
            continue
    return segments


def validate_translation(original_path: str, translated_path: str,
                         empty_threshold_pct: float = 2.0) -> ValidationResult:
    """Validiert eine übersetzte SRT-Datei gegen das Original.

    Prüft:
    1. Segment-Anzahl stimmt überein
    2. Leere Segmente (wo Original Text hat)
    3. Drift-Erkennung (inhaltliche Verschiebung durch Segment-Merging)

    Args:
        original_path: Pfad zur Original-SRT
        translated_path: Pfad zur übersetzten SRT
        empty_threshold_pct: Ab wieviel Prozent leerer Segmente ein Problem gemeldet wird

    Returns:
        ValidationResult mit Details
    """
    orig_segments = parse_srt_segments(original_path)
    trans_segments = parse_srt_segments(translated_path)

    total = len(orig_segments)

    # Grundcheck: Segment-Anzahl
    if total == 0:
        return ValidationResult(
            is_valid=True, empty_count=0, total_count=0,
            empty_percentage=0.0, drift_start=None, drift_amount=0,
            details="Keine Segmente im Original."
        )

    if len(trans_segments) != total:
        return ValidationResult(
            is_valid=False, empty_count=0, total_count=total,
            empty_percentage=0.0, drift_start=None, drift_amount=0,
            details=(
                f"Segment-Anzahl stimmt nicht überein!\n"
                f"Original: {total} Segmente\n"
                f"Übersetzung: {len(trans_segments)} Segmente\n\n"
                f"Die Übersetzung hat eine andere Anzahl Segmente als das Original. "
                f"Das Video wird wahrscheinlich nicht korrekt synchronisiert."
            )
        )

    # Leere Segmente finden (wo Original Text hat)
    empty_indices = []
    for i in range(total):
        orig_has_text = bool(orig_segments[i]['text'].strip())
        trans_has_text = bool(trans_segments[i]['text'].strip())
        if orig_has_text and not trans_has_text:
            empty_indices.append(orig_segments[i]['index'])

    empty_count = len(empty_indices)
    empty_pct = (empty_count / total) * 100 if total > 0 else 0.0

    # Drift-Erkennung: Prüfe ob die leeren Segmente am Ende gehäuft sind
    # (typisches Muster bei LLM-Segment-Merging)
    drift_start = None
    drift_amount = 0

    if empty_count >= 3:
        # Prüfe ob die leeren Segmente am Ende des Videos clustern
        # (= typisches Merging-Muster: Inhalt verschiebt sich nach vorne,
        #  letzte N Segmente bleiben leer)
        max_index = max(seg['index'] for seg in orig_segments)

        # Wenn >50% der leeren Segmente im letzten Viertel liegen -> Drift
        last_quarter_start = max_index * 0.75
        empty_in_last_quarter = sum(1 for idx in empty_indices if idx >= last_quarter_start)

        if empty_in_last_quarter >= empty_count * 0.5:
            drift_amount = empty_in_last_quarter

            # Finde den Startpunkt: erstes leeres Segment in der zweiten Hälfte
            for i in range(total):
                orig_has_text = bool(orig_segments[i]['text'].strip())
                trans_has_text = bool(trans_segments[i]['text'].strip())
                if orig_has_text and not trans_has_text and i > total * 0.5:
                    drift_start = orig_segments[i]['index']
                    break

            # Fallback: erstes leeres Segment überhaupt
            if drift_start is None and empty_indices:
                drift_start = empty_indices[0]

    # Ergebnis zusammenstellen
    is_valid = empty_pct < empty_threshold_pct and drift_amount == 0

    # Details-Text erstellen
    if is_valid:
        details = (
            f"Übersetzung OK: {total} Segmente, "
            f"{empty_count} ohne Text ({empty_pct:.1f}%)."
        )
    else:
        lines = []
        lines.append("Mögliche Qualitätsprobleme erkannt:")
        lines.append("")
        lines.append(f"Segmente gesamt: {total}")
        lines.append(f"Leere Segmente: {empty_count} ({empty_pct:.1f}%)")

        if drift_amount > 0:
            lines.append("")
            lines.append("Inhaltliche Verschiebung erkannt:")
            lines.append(f"  Vermuteter Drift: ~{drift_amount} Segmente")
            if drift_start:
                lines.append(f"  Möglicher Beginn: ab Segment {drift_start}")
            lines.append("")
            lines.append(
                f"Das bedeutet: Die Übersetzung ist wahrscheinlich um "
                f"~{drift_amount} Segmente verschoben. Untertitel und "
                f"gesprochener Text werden nicht zusammenpassen."
            )
        else:
            lines.append("")
            lines.append(
                f"{empty_count} Segmente haben keine Übersetzung, "
                f"obwohl das Original dort Text enthält."
            )

        if empty_count <= 5 and empty_indices:
            lines.append("")
            lines.append(f"Betroffene Segmente: {', '.join(str(i) for i in empty_indices)}")

        details = "\n".join(lines)

    return ValidationResult(
        is_valid=is_valid,
        empty_count=empty_count,
        total_count=total,
        empty_percentage=empty_pct,
        drift_start=drift_start,
        drift_amount=drift_amount,
        details=details
    )
