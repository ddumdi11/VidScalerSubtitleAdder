"""
Hilfsfunktionen für VidScaler
"""

from typing import List, Tuple
from video_processor import VideoProcessor


def get_video_info(video_path: str) -> Tuple[int, int]:
    """Wrapper-Funktion für Video-Informationen"""
    processor = VideoProcessor()
    return processor.get_video_dimensions(video_path)


def generate_scaling_options(original_width: int, original_height: int) -> List[Tuple[int, int]]:
    """
    Generiert sinnvolle Skalierungsoptionen basierend auf der ursprünglichen Auflösung
    
    Returns:
        List von Tupeln (neue_breite, qualitäts_prozent)
    """
    options = []
    
    # Basis-Skalierungsfaktoren (von bester zu niedrigster Qualität)
    scale_factors = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]
    
    for factor in scale_factors:
        new_width = int(original_width * factor)
        
        # Stelle sicher, dass die Breite gerade ist
        if new_width % 2 != 0:
            new_width -= 1
        
        # Mindestbreite von 100 Pixel
        if new_width < 100:
            break
            
        quality_percent = int(factor * 100)
        options.append((new_width, quality_percent))
    
    # Zusätzliche Standard-Auflösungen hinzufügen (falls sinnvoll)
    standard_widths = [1920, 1280, 1024, 854, 640, 480, 320]
    
    for width in standard_widths:
        if width < original_width and width >= 100:
            # Stelle sicher, dass die Breite gerade ist
            if width % 2 == 0:
                # Berechne Qualitätsprozent basierend auf Breiten-Verhältnis
                quality = int((width / original_width) * 100)
                
                # Füge nur hinzu, wenn noch nicht vorhanden
                if not any(opt[0] == width for opt in options):
                    options.append((width, quality))
    
    # Nach Qualität sortieren (beste zuerst)
    options.sort(key=lambda x: x[1], reverse=True)
    
    # Duplikate entfernen (basierend auf Breite)
    seen_widths = set()
    unique_options = []
    for width, quality in options:
        if width not in seen_widths:
            seen_widths.add(width)
            unique_options.append((width, quality))
    
    return unique_options[:10]  # Maximal 10 Optionen


def format_file_size(size_bytes: int) -> str:
    """Formatiert Dateigröße in menschenlesbarem Format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"


def is_video_file(file_path: str) -> bool:
    """Prüft, ob eine Datei eine unterstützte Videodatei ist"""
    video_extensions = {
        '.mp4', '.avi', '.mov', '.mkv', '.wmv', 
        '.flv', '.webm', '.m4v', '.3gp', '.ogv'
    }
    
    return any(file_path.lower().endswith(ext) for ext in video_extensions)


class ToolTip:
    """Einfacher Tooltip für tkinter widgets"""
    def __init__(self, widget, text):
        """Bindet Enter/Leave-Events an das Widget für Tooltip-Anzeige."""
        import tkinter as tk
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self._tk = tk
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        """Zeigt den Tooltip neben dem Widget an."""
        x = self.widget.winfo_rootx() + 25
        y = self.widget.winfo_rooty() + 25

        self.tooltip_window = tw = self._tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = self._tk.Label(tw, text=self.text, justify=self._tk.LEFT,
                        background="#ffffe0", relief=self._tk.SOLID, borderwidth=1,
                        font=("Arial", 9))
        label.pack()

    def hide(self, event=None):
        """Versteckt und zerstört das Tooltip-Fenster."""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


def calculate_estimated_size_reduction(original_width: int, new_width: int) -> float:
    """
    Schätzt die Größenreduzierung basierend auf der Auflösungsänderung
    
    Returns:
        Geschätzte Größenreduzierung als Faktor (z.B. 0.5 für 50% kleiner)
    """
    if new_width >= original_width:
        return 1.0  # Keine Reduzierung
    
    # Vereinfachte Schätzung basierend auf Pixel-Verhältnis
    pixel_ratio = (new_width / original_width) ** 2
    
    # Berücksichtige, dass die Kompression nicht linear ist
    # Kleinere Videos haben oft bessere Kompressionsraten
    compression_bonus = 0.9 if pixel_ratio < 0.5 else 1.0
    
    return pixel_ratio * compression_bonus


def validate_ffmpeg_installation() -> Tuple[bool, str]:
    """
    Validiert FFmpeg-Installation
    
    Returns:
        Tupel (ist_verfügbar, nachricht)
    """
    try:
        processor = VideoProcessor()
        if processor.is_ffmpeg_available():
            version = processor.get_ffmpeg_version()
            return True, f"FFmpeg gefunden: {version}"
        else:
            return False, "FFmpeg ist installiert, aber nicht funktionsfähig"
    except FileNotFoundError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unerwarteter Fehler bei FFmpeg-Validierung: {e}"