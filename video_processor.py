
"""
Video-Verarbeitung mit FFmpeg
"""

import subprocess
import os
import sys
import shutil
import tempfile
import logging
import re
from typing import Tuple

# FFmpeg timeout constants (in seconds)
FFMPEG_TIMEOUT_SHORT = int(os.getenv("FFMPEG_TIMEOUT_SHORT", "30"))     # quick ops
FFMPEG_TIMEOUT_LONG = int(os.getenv("FFMPEG_TIMEOUT_LONG", "600"))      # processing

# Windows-spezifische subprocess-Konfiguration um Console-Fenster zu unterdrücken
if sys.platform == "win32":
    SUBPROCESS_FLAGS = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    SUBPROCESS_FLAGS = {}


class VideoProcessor:
    def __init__(self):
        self.ffmpeg_path = self._find_ffmpeg()
        
    def _find_ffmpeg(self) -> str:
        """Findet FFmpeg-Pfad im System (secure, no shell injection)"""
        # 0) Explicit override
        ffmpeg_env = os.getenv("FFMPEG_PATH")
        if ffmpeg_env and os.path.exists(ffmpeg_env):
            return ffmpeg_env
        # 1) First try: Use shutil.which (cross-platform, secure)
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            return ffmpeg_path
            
        # Fallback: Platform-specific command (secure subprocess call)
        try:
            if sys.platform == "win32":
                # Windows: use 'where' command securely
                result = subprocess.run(['where', 'ffmpeg'], 
                                     capture_output=True, text=True, shell=False, 
                                     timeout=FFMPEG_TIMEOUT_SHORT, **SUBPROCESS_FLAGS)
            else:
                # Unix-like: use 'which' command securely  
                result = subprocess.run(['which', 'ffmpeg'],
                                     capture_output=True, text=True, shell=False,
                                     timeout=FFMPEG_TIMEOUT_SHORT, **SUBPROCESS_FLAGS)
            if result.returncode == 0:
                # Handle Windows CR/LF properly - get first non-empty line
                lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                if lines:
                    return lines[0]
        except (subprocess.TimeoutExpired, OSError) as e:
            logging.warning(f"FFmpeg path detection failed: {e}")
            pass
            
        # Fallback: Standard-Pfade prüfen
        if sys.platform == "win32":
            common_paths = [
                r'C:\ffmpeg\bin\ffmpeg.exe',
                r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
                r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
                r'C:\ProgramData\chocolatey\bin\ffmpeg.exe',
            ]
        else:
            common_paths = [
                '/opt/homebrew/bin/ffmpeg',   # macOS arm64 (Homebrew)
                '/usr/local/bin/ffmpeg',      # macOS/intel or custom installs
                '/usr/bin/ffmpeg',            # common Linux
            ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
                
        raise FileNotFoundError("FFmpeg wurde nicht gefunden. Bitte installieren Sie FFmpeg, stellen Sie sicher, dass es im PATH verfügbar ist, oder setzen Sie FFMPEG_PATH auf den absoluten ffmpeg-Pfad.")
    
    def get_video_dimensions(self, video_path: str) -> Tuple[int, int]:
        """Ermittelt Video-Dimensionen mit ffprobe"""
        try:
            # ffprobe verwenden für genauere Informationen
            ffprobe_path = shutil.which('ffprobe') or 'ffprobe'
            cmd = [
                ffprobe_path,  # Keep unmodified for PATH resolution
                '-hide_banner', '-loglevel', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'csv=s=x:p=0',
                os.path.abspath(video_path)
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, shell=False,
                                      timeout=FFMPEG_TIMEOUT_SHORT, check=True, **SUBPROCESS_FLAGS)
            except subprocess.CalledProcessError as e:
                err = e.stderr or e.stdout or str(e)
                logging.exception("FFprobe failed: %s", err)
                raise RuntimeError(f"Video-Analyse fehlgeschlagen: {err}") from e
            dimensions = result.stdout.strip().split('x')
            if len(dimensions) != 2:
                raise ValueError("Konnte Video-Dimensionen nicht ermitteln")
            width = int(dimensions[0])
            height = int(dimensions[1])
            if width <= 0 or height <= 0:
                raise ValueError(f"Ungültige Dimensionen: {width}x{height}")
            
            return width, height
            
        except subprocess.TimeoutExpired as e:
            logging.exception(f"ffprobe timeout after {FFMPEG_TIMEOUT_SHORT}s on file: {video_path}")
            raise RuntimeError(f"Video-Analyse timeout nach {FFMPEG_TIMEOUT_SHORT}s - Datei möglicherweise beschädigt") from e
        except (ValueError, IndexError) as e:
            raise ValueError(f"Ungültige Video-Dimensionen: {e}") from e
        except Exception as e:
            logging.exception(f"Unexpected error analyzing video: {video_path}")
            raise RuntimeError(f"Unerwarteter Fehler bei Video-Analyse: {e}") from e
    
    def scale_video(self, input_path: str, output_path: str, new_width: int):
        """Skaliert Video mit FFmpeg"""
        try:
            # Stelle sicher, dass new_width gerade ist
            if new_width % 2 != 0:
                new_width += 1
            
            cmd = [
                self.ffmpeg_path, '-nostdin', '-hide_banner', '-loglevel', 'error',
                '-i', input_path,
                '-vf', f'scale={new_width}:-2',
                # insert faststart for MP4/MOV containers
                *(['-movflags', '+faststart'] if output_path.lower().endswith(('.mp4', '.m4v', '.mov')) else []),
                '-y',
                output_path
            ]
            
            subprocess.run(cmd, capture_output=True, text=True, shell=False,
                          timeout=FFMPEG_TIMEOUT_LONG, check=True, **SUBPROCESS_FLAGS)
            logging.info(f"Video scaling completed: {output_path}")
            
            # Prüfe, ob Ausgabedatei erstellt wurde
            if not os.path.exists(output_path):
                raise RuntimeError("Ausgabedatei wurde nicht erstellt")
                
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            raise RuntimeError(f"FFmpeg-Fehler: {error_msg}") from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Video-Skalierung timeout nach {FFMPEG_TIMEOUT_LONG}s") from e
        except Exception as e:
            logging.exception("Unexpected error during video scaling")
            raise RuntimeError("Unerwarteter Fehler bei der Video-Skalierung") from e
    
    def is_ffmpeg_available(self) -> bool:
        """Prüft, ob FFmpeg verfügbar ist"""
        try:
            subprocess.run([self.ffmpeg_path, '-nostdin', '-hide_banner', '-loglevel', 'error', '-version'], 
                         capture_output=True, shell=False, timeout=FFMPEG_TIMEOUT_SHORT, 
                         check=True, **SUBPROCESS_FLAGS)
            return True
        except Exception:
            logging.exception("FFmpeg availability check failed")
            return False
    
    def get_ffmpeg_version(self) -> str:
        """Gibt FFmpeg-Version zurück"""
        try:
            result = subprocess.run([self.ffmpeg_path, '-nostdin', '-hide_banner', '-loglevel', 'error', '-version'], 
                                 capture_output=True, text=True, shell=False, 
                                 timeout=FFMPEG_TIMEOUT_SHORT, check=True, **SUBPROCESS_FLAGS)
            # Erste Zeile enthält Version
            first_line = result.stdout.split('\n')[0]
            return first_line
        except Exception:
            logging.exception("FFmpeg version check failed")
            return "Unbekannt"
            
    def scale_video_with_subtitles(self, input_path: str, output_path: str, new_width: int, subtitle_path: str):
        """Skaliert Video und brennt Untertitel unterhalb des Videos ein"""
        temp_subtitle_abs = None
        try:
            # Stelle sicher, dass new_width gerade ist
            if new_width % 2 != 0:
                new_width += 1
            
            # Berechne Padding-Höhe für Untertitel (100px sollten ausreichen)
            subtitle_padding = 100
            
            # Kopiere Untertitel-Datei temporär ins Arbeitsverzeichnis
            # um Windows-Pfad-Probleme zu vermeiden
            with tempfile.NamedTemporaryFile(dir=os.getcwd(), prefix="temp_subtitles_", suffix=".srt", delete=False) as tf:
                temp_subtitle_abs = tf.name
                temp_subtitle_basename = os.path.basename(tf.name)  # for subtitles= filter
            shutil.copy2(subtitle_path, temp_subtitle_abs)
            
            # FFmpeg-Befehl: Video erweitern und Untertitel einbrennen
            # Verwende einfachen relativen Pfad
            cmd = [
                self.ffmpeg_path, '-nostdin', '-hide_banner', '-loglevel', 'error',
                '-i', input_path,
                '-vf', f'scale={new_width}:-2,pad=iw:ih+{subtitle_padding}:0:0:black,subtitles={temp_subtitle_basename}:charenc=UTF-8',
                '-y',  # Überschreibe Ausgabedatei ohne Nachfrage
                output_path
            ]
            
            # Führe FFmpeg-Befehl aus (hardened with timeout)
            subprocess.run(cmd, capture_output=True, text=True, shell=False,
                           timeout=FFMPEG_TIMEOUT_LONG, check=True, **SUBPROCESS_FLAGS)
            
            # Prüfe, ob Ausgabedatei erstellt wurde
            if not os.path.exists(output_path):
                raise RuntimeError("Ausgabedatei wurde nicht erstellt")
                
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            raise RuntimeError(f"FFmpeg-Fehler bei Untertitel-Verarbeitung: {error_msg}") from e
        except Exception as e:
            raise RuntimeError("Unerwarteter Fehler bei der Untertitel-Verarbeitung") from e
        finally:
            # Temporäre Untertitel-Datei aufräumen
            if temp_subtitle_abs and os.path.exists(temp_subtitle_abs):
                try:
                    os.remove(temp_subtitle_abs)
                except OSError as e:
                    logging.debug("Failed to cleanup temp file %s: %s", temp_subtitle_abs, e)
                    
    def scale_video_with_translation(self, input_path: str, output_path: str, new_width: int, 
                                 original_subtitle_path: str, translated_subtitle_path: str,
                                 translation_mode: str = "dual"):
        """Skaliert Video mit originalen und übersetzten Untertiteln (SRT -> ASS, feste Styles)"""
        temp_original_srt = temp_translated_srt = None
        temp_original_ass = temp_translated_ass = None

        def _convert_srt_to_ass(src_srt: str, dst_ass: str):
            # SRT -> ASS (UTF-8 erzwingen) - hardened subprocess call
            subprocess.run([self.ffmpeg_path, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-sub_charenc", "UTF-8", "-i", src_srt, dst_ass],
                capture_output=True, text=True, shell=False, timeout=FFMPEG_TIMEOUT_SHORT, 
                check=True, **SUBPROCESS_FLAGS)

        def _ensure_wrapstyle(ass_path: str, wrap_style: int = 3):
            # 0/3 = “smart” (3 bevorzugt meist gleichmäßiger),
            # 1 = nur manuelle \N, 2 = keine Umbrüche
            with open(ass_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # vorhandenen Eintrag ersetzen oder unter [Script Info] hinzufügen
            done = False
            for i, line in enumerate(lines):
                if line.strip().lower().startswith("wrapstyle:"):
                    lines[i] = f"WrapStyle: {wrap_style}\n"
                    done = True
                    break
            if not done:
                for i, line in enumerate(lines):
                    if line.strip().lower().startswith("[script info]"):
                        insert_at = i + 1
                        while insert_at < len(lines) and lines[insert_at].strip().startswith(";"):
                            insert_at += 1
                        lines.insert(insert_at, f"WrapStyle: {wrap_style}\n")
                        break

            with open(ass_path, "w", encoding="utf-8") as f:
                f.writelines(lines)


        def _tweak_ass_style(ass_path: str, *, alignment: int, margin_v: int,
                             font_size: int = 13, outline: int = 2, shadow: int = 0, # vorher 20→15, jetzt 13
                             margin_l: int = 2, margin_r: int = 2): # vorher 10/10, jetzt 2/2
            # Passe "Style: Default,..." an (ASS V4+ Format-Reihenfolge)
            with open(ass_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # TODO: fmt_idx_map was removed as dead code (Code-Rabbit suggestion)
            # The indices are now inlined below for minimal function complexity
            # fmt_idx_map = { ... } # Previously here for documentation

            for i, line in enumerate(lines):
                if line.strip().lower().startswith("style: default"):
                    parts = [p.strip() for p in line.strip().split(",")]
                    # Sicherstellen, dass genügend Felder vorhanden sind
                    if len(parts) >= 23:
                        parts[2]  = str(font_size)                    # Fontsize
                        parts[16] = str(outline)                      # Outline
                        parts[17] = str(shadow)                       # Shadow
                        parts[18] = str(alignment)                    # Alignment (2=BottomCenter, 8=TopCenter)
                        parts[19] = str(margin_l)                     # MarginL
                        parts[20] = str(margin_r)                     # MarginR
                        parts[21] = str(margin_v)                     # MarginV (oben bzw. unten)
                        lines[i] = ",".join(parts) + "\n"
                    break

            with open(ass_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

        try:
            # Breite gerade machen
            if new_width % 2 != 0:
                new_width += 1

            if translation_mode == "dual":
                # Asymmetrisches Padding für sichere 2-Zeiler
                top_pad, bot_pad = 140, 160

                # Temporäre Dateien im cwd -> keine Laufwerks-Doppelpunkte im Filter
                cwd = os.getcwd()
                temp_original_srt = os.path.join(cwd, "temp_original.srt")
                temp_translated_srt = os.path.join(cwd, "temp_translated.srt")
                shutil.copy2(original_subtitle_path, temp_original_srt)
                shutil.copy2(translated_subtitle_path, temp_translated_srt)

                temp_original_ass = os.path.join(cwd, "temp_original.ass")
                temp_translated_ass = os.path.join(cwd, "temp_translated.ass")

                # 1) SRT -> ASS
                _convert_srt_to_ass(temp_original_srt,  temp_original_ass)
                _convert_srt_to_ass(temp_translated_srt, temp_translated_ass)
                _ensure_wrapstyle(temp_original_ass, 3)
                _ensure_wrapstyle(temp_translated_ass, 3)

                # 2) Styles je Datei (oben / unten)
                _tweak_ass_style(temp_original_ass,  alignment=8, margin_v=10)   # TopCenter
                _tweak_ass_style(temp_translated_ass, alignment=2, margin_v=12)  # BottomCenter

                # 3) Video filtern: scale -> pad -> ass (oben) -> ass (unten)
                vf = (
                    f"scale={new_width}:-2,"
                    f"pad=iw:ih+{top_pad+bot_pad}:0:{top_pad}:black,"
                    f"ass=filename={os.path.basename(temp_original_ass)},"
                    f"ass=filename={os.path.basename(temp_translated_ass)}"
                )

                cmd = [self.ffmpeg_path, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", input_path, "-vf", vf, "-y", output_path]

            else:
                # Nur Übersetzung unten
                bot_pad = 100
                cwd = os.getcwd()
                temp_translated_srt = os.path.join(cwd, "temp_subtitles.srt")
                shutil.copy2(translated_subtitle_path, temp_translated_srt)
                temp_translated_ass = os.path.join(cwd, "temp_subtitles.ass")

                _convert_srt_to_ass(temp_translated_srt, temp_translated_ass)
                _tweak_ass_style(temp_translated_ass, alignment=2, margin_v=12)

                vf = (
                    f"scale={new_width}:-2,"
                    f"pad=iw:ih+{bot_pad}:0:0:black,"
                    f"ass=filename={os.path.basename(temp_translated_ass)}"
                )

                cmd = [self.ffmpeg_path, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", input_path, "-vf", vf, "-y", output_path]

            # Ausführen (hardened with timeout)
            subprocess.run(cmd, capture_output=True, text=True, shell=False, 
                         timeout=FFMPEG_TIMEOUT_LONG, check=True, **SUBPROCESS_FLAGS)

            if not os.path.exists(output_path):
                raise RuntimeError("Ausgabedatei wurde nicht erstellt")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFmpeg-Fehler bei Übersetzungs-Verarbeitung: {e.stderr or str(e)}") from e
        except Exception as e:
            raise RuntimeError("Unerwarteter Fehler bei der Übersetzungs-Verarbeitung") from e
        finally:
            # Aufräumen
            for p in [temp_original_srt, temp_translated_srt, temp_original_ass, temp_translated_ass]:
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        # Ignore cleanup errors
                        pass

    
    def _parse_srt(self, srt_path: str):
        """Parsed SRT-Datei und gibt Segmente zurück"""
        segments = []
        
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
        # SRT-Blöcke splitten (durch doppelte Zeilenumbrüche getrennt)
        blocks = re.split(r'\r?\n\r?\n', content)
        
        for block in blocks:
            if not block.strip():
                continue
                
            lines = block.strip().splitlines()
            if len(lines) < 3:
                continue
                
            try:
                index = int(lines[0])
                timestamp = lines[1]
                text = '\n'.join(lines[2:])
                
                segments.append({
                    'index': index,
                    'timestamp': timestamp,
                    'text': text.strip()
                })
            except (ValueError, IndexError):
                continue
                
        return segments