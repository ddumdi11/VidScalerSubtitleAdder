
"""
Video-Verarbeitung mit FFmpeg
"""

import subprocess
import os
from typing import Tuple
import shlex
import shutil
import tempfile


class VideoProcessor:
    def __init__(self):
        self.ffmpeg_path = self._find_ffmpeg()
        
    def _find_ffmpeg(self) -> str:
        """Findet FFmpeg-Pfad im System"""
        # Versuche ffmpeg im PATH zu finden
        try:
            result = subprocess.run(['where', 'ffmpeg'], 
                                 capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except:
            pass
            
        # Fallback: Standard-Pfade prüfen
        common_paths = [
            r'C:\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
            'ffmpeg'  # Hoffen, dass es im PATH ist
        ]
        
        for path in common_paths:
            if os.path.exists(path) or path == 'ffmpeg':
                return path
                
        raise FileNotFoundError("FFmpeg wurde nicht gefunden. Bitte installieren Sie FFmpeg und stellen Sie sicher, dass es im PATH verfügbar ist.")
    
    def get_video_dimensions(self, video_path: str) -> Tuple[int, int]:
        """Ermittelt Video-Dimensionen mit ffprobe"""
        try:
            # ffprobe verwenden für genauere Informationen
            cmd = [
                'ffprobe', 
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'csv=s=x:p=0',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            dimensions = result.stdout.strip().split('x')
            
            if len(dimensions) != 2:
                raise ValueError("Konnte Video-Dimensionen nicht ermitteln")
                
            width = int(dimensions[0])
            height = int(dimensions[1])
            
            return width, height
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Fehler beim Lesen der Video-Informationen: {e.stderr}")
        except (ValueError, IndexError) as e:
            raise ValueError(f"Ungültige Video-Dimensionen: {e}")
    
    def scale_video(self, input_path: str, output_path: str, new_width: int):
        """Skaliert Video mit FFmpeg"""
        try:
            # Stelle sicher, dass new_width gerade ist
            if new_width % 2 != 0:
                new_width += 1
            
            # Erste Versuch: Wie dein ursprünglicher Befehl
            cmd = [
                self.ffmpeg_path,
                '-i', input_path,
                '-vf', f'scale={new_width}:-1',  # -1 für proportionale Höhe (wie ursprünglich)
                '-y',  # Überschreibe Ausgabedatei ohne Nachfrage
                output_path
            ]
            
            # Führe FFmpeg-Befehl aus
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Prüfe, ob Ausgabedatei erstellt wurde
            if not os.path.exists(output_path):
                raise RuntimeError("Ausgabedatei wurde nicht erstellt")
                
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            
            # Prüfe auf "height not divisible by 2" Fehler und versuche Fallback
            if "height not divisible by 2" in error_msg.lower():
                try:
                    # Fallback: Verwende -2 für gerade Höhe (wie du es manuell machst)
                    fallback_cmd = [
                        self.ffmpeg_path,
                        '-i', input_path,
                        '-vf', f'scale={new_width}:-2',  # -2 erzwingt gerade Höhe
                        '-y',
                        output_path
                    ]
                    subprocess.run(fallback_cmd, capture_output=True, text=True, check=True)
                    
                    # Prüfe, ob Ausgabedatei erstellt wurde
                    if not os.path.exists(output_path):
                        raise RuntimeError("Ausgabedatei wurde nicht erstellt")
                        
                except subprocess.CalledProcessError:
                    # Wenn auch der Fallback fehlschlägt, ursprünglichen Fehler anzeigen
                    raise RuntimeError(f"FFmpeg-Fehler: {error_msg}")
            else:
                raise RuntimeError(f"FFmpeg-Fehler: {error_msg}")
        except Exception as e:
            raise RuntimeError(f"Unerwarteter Fehler bei der Video-Skalierung: {e}")
    
    def is_ffmpeg_available(self) -> bool:
        """Prüft, ob FFmpeg verfügbar ist"""
        try:
            subprocess.run([self.ffmpeg_path, '-version'], 
                         capture_output=True, check=True)
            return True
        except:
            return False
    
    def get_ffmpeg_version(self) -> str:
        """Gibt FFmpeg-Version zurück"""
        try:
            result = subprocess.run([self.ffmpeg_path, '-version'], 
                                 capture_output=True, text=True, check=True)
            # Erste Zeile enthält Version
            first_line = result.stdout.split('\n')[0]
            return first_line
        except:
            return "Unbekannt"
            
    def scale_video_with_subtitles(self, input_path: str, output_path: str, new_width: int, subtitle_path: str):
        """Skaliert Video und brennt Untertitel unterhalb des Videos ein"""
        temp_subtitle_path = None
        try:
            # Stelle sicher, dass new_width gerade ist
            if new_width % 2 != 0:
                new_width += 1
            
            # Berechne Padding-Höhe für Untertitel (100px sollten ausreichen)
            subtitle_padding = 100
            
            # Kopiere Untertitel-Datei temporär ins Arbeitsverzeichnis
            # um Windows-Pfad-Probleme zu vermeiden
            temp_subtitle_path = os.path.join(os.getcwd(), "temp_subtitles.srt")
            shutil.copy2(subtitle_path, temp_subtitle_path)
            
            # FFmpeg-Befehl: Video erweitern und Untertitel einbrennen
            # Verwende einfachen relativen Pfad
            cmd = [
                self.ffmpeg_path,
                '-i', input_path,
                '-vf', f'scale={new_width}:-2,pad=iw:ih+{subtitle_padding}:0:0:black,subtitles=temp_subtitles.srt',
                '-y',  # Überschreibe Ausgabedatei ohne Nachfrage
                output_path
            ]
            
            # Führe FFmpeg-Befehl aus
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Prüfe, ob Ausgabedatei erstellt wurde
            if not os.path.exists(output_path):
                raise RuntimeError("Ausgabedatei wurde nicht erstellt")
                
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            raise RuntimeError(f"FFmpeg-Fehler bei Untertitel-Verarbeitung: {error_msg}")
        except Exception as e:
            raise RuntimeError(f"Unerwarteter Fehler bei der Untertitel-Verarbeitung: {e}")
        finally:
            # Temporäre Untertitel-Datei aufräumen
            if temp_subtitle_path and os.path.exists(temp_subtitle_path):
                try:
                    os.remove(temp_subtitle_path)
                except:
                    pass  # Ignoriere Fehler beim Aufräumen
                    
    def scale_video_with_translation(self, input_path: str, output_path: str, new_width: int, 
                                 original_subtitle_path: str, translated_subtitle_path: str,
                                 translation_mode: str = "dual"):
        """Skaliert Video mit originalen und übersetzten Untertiteln (SRT -> ASS, feste Styles)"""
        temp_original_srt = temp_translated_srt = None
        temp_original_ass = temp_translated_ass = None

        def _convert_srt_to_ass(src_srt: str, dst_ass: str):
            # SRT -> ASS (UTF-8 erzwingen)
            subprocess.run(
                [self.ffmpeg_path, "-loglevel", "error", "-y", "-sub_charenc", "UTF-8", "-i", src_srt, dst_ass],
                capture_output=True, text=True, check=True
            )

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
                             font_size: int = 15, outline: int = 2, shadow: int = 0, # vorher 20, jetzt 15
                             margin_l: int = 2, margin_r: int = 2): # vorher 10/10, jetzt 2/2
            # Passe "Style: Default,..." an (ASS V4+ Format-Reihenfolge)
            with open(ass_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            fmt_idx_map = {
                # 0:"Style: Default" (kein Feld), dann:
                1:"Fontname", 2:"Fontsize", 3:"PrimaryColour", 4:"SecondaryColour", 5:"OutlineColour",
                6:"BackColour", 7:"Bold", 8:"Italic", 9:"Underline", 10:"StrikeOut", 11:"ScaleX",
                12:"ScaleY", 13:"Spacing", 14:"Angle", 15:"BorderStyle", 16:"Outline", 17:"Shadow",
                18:"Alignment", 19:"MarginL", 20:"MarginR", 21:"MarginV", 22:"Encoding"
            }

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

                cmd = [self.ffmpeg_path, "-loglevel", "error", "-i", input_path, "-vf", vf, "-y", output_path]

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

                cmd = [self.ffmpeg_path, "-loglevel", "error", "-i", input_path, "-vf", vf, "-y", output_path]

            # Ausführen
            subprocess.run(cmd, capture_output=True, text=True, check=True)

            if not os.path.exists(output_path):
                raise RuntimeError("Ausgabedatei wurde nicht erstellt")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFmpeg-Fehler bei Übersetzungs-Verarbeitung: {e.stderr or str(e)}")
        except Exception as e:
            raise RuntimeError(f"Unerwarteter Fehler bei der Übersetzungs-Verarbeitung: {e}")
        finally:
            # Aufräumen
            for p in [temp_original_srt, temp_translated_srt, temp_original_ass, temp_translated_ass]:
                if p and os.path.exists(p):
                    try: os.remove(p)
                    except: pass

    
    def _parse_srt(self, srt_path: str):
        """Parsed SRT-Datei und gibt Segmente zurück"""
        segments = []
        
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
        # SRT-Blöcke splitten (durch doppelte Zeilenumbrüche getrennt)
        blocks = content.split('\n\n')
        
        for block in blocks:
            if not block.strip():
                continue
                
            lines = block.strip().split('\n')
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