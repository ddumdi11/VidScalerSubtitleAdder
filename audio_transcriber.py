"""
Audio Transcriber - GUI-Anwendung für Video-zu-SRT Transkription mit Whisper
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import tempfile
import threading
from typing import List, Dict, Optional, Callable
import subprocess
import json

# FFmpeg timeout constant (in seconds)
FFMPEG_TIMEOUT = 300  # 5 minutes should be enough for audio extraction

# Windows-spezifische subprocess-Konfiguration um Console-Fenster zu unterdrücken
if sys.platform == "win32":
    SUBPROCESS_FLAGS = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    SUBPROCESS_FLAGS = {}

try:
    import whisper
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import numpy as np
    from pydub import AudioSegment
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    MISSING_DEPS = str(e)


class TranscriptionSegment:
    """Repräsentiert ein Audio-Segment mit Transkription"""
    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text
        self.edited = False


class AudioTranscriber:
    def __init__(self, video_path: str, subtitle_var: tk.StringVar):
        if not DEPENDENCIES_AVAILABLE:
            raise ImportError(f"Fehlende Abhängigkeiten: {MISSING_DEPS}")
            
        self.video_path = video_path
        self.subtitle_var = subtitle_var
        self.audio_segments: List[TranscriptionSegment] = []
        self.temp_audio_path = None
        self.whisper_model = None
        self.audio_data = None
        self.sample_rate = None
        
        self.root = tk.Toplevel()
        self.root.title("Audio Transkriptor")
        self.root.geometry("1000x700")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.setup_ui()
        
    def setup_ui(self):
        """
        Set up the transcription tool's Tkinter user interface.
        
        Creates and lays out the main window contents used by AudioTranscriber:
        - Header and video filename label.
        - Whisper model and language selection controls (radio buttons).
        - Action buttons for extracting audio, transcribing, and exporting (with initial enabled/disabled states).
        - Progress label and indeterminate progress bar.
        - Results area containing a scrollable Treeview of detected segments and an editor for selected segment text.
        - Event bindings (Treeview selection to load a segment into the editor) and grid weight configuration for responsive resizing.
        
        Side effects:
        - Initializes instance UI-related attributes such as self.model_var, self.language_var, self.extract_button, self.transcribe_button, self.export_button, self.progress_var, self.progress_label, self.progress_bar, self.segments_tree, and self.edit_text.
        """
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Header
        ttk.Label(main_frame, text="Audio Transkription", font=("Arial", 16, "bold")).grid(
            row=0, column=0, columnspan=3, pady=(0, 10)
        )
        
        video_name = os.path.basename(self.video_path)
        ttk.Label(main_frame, text=f"Video: {video_name}", font=("Arial", 10)).grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(0, 15)
        )
        
        # Whisper Model Selection
        model_frame = ttk.LabelFrame(main_frame, text="Whisper Modell", padding="5")
        model_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.model_var = tk.StringVar(value="base")
        models = [("Tiny (schnell, weniger genau)", "tiny"), 
                  ("Base (empfohlen)", "base"),
                  ("Small (langsamer, genauer)", "small")]
        
        for i, (text, value) in enumerate(models):
            ttk.Radiobutton(model_frame, text=text, variable=self.model_var, 
                           value=value).grid(row=0, column=i, padx=10, sticky=tk.W)
        
        # Language Selection
        lang_frame = ttk.LabelFrame(main_frame, text="Sprache", padding="5")
        lang_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.language_var = tk.StringVar(value="en")
        languages = [("Deutsch", "de"), ("Englisch", "en"), ("Auto-Erkennung", "auto")]
        
        for i, (text, value) in enumerate(languages):
            ttk.Radiobutton(lang_frame, text=text, variable=self.language_var, 
                           value=value).grid(row=0, column=i, padx=10, sticky=tk.W)
        
        # Action Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)
        
        self.extract_button = ttk.Button(button_frame, text="1. Audio extrahieren", 
                                        command=self.extract_audio)
        self.extract_button.grid(row=0, column=0, padx=(0, 10))
        
        self.transcribe_button = ttk.Button(button_frame, text="2. Transkribieren", 
                                           command=self.start_transcription, state="disabled")
        self.transcribe_button.grid(row=0, column=1, padx=(0, 10))
        
        self.export_button = ttk.Button(button_frame, text="3. Als SRT exportieren", 
                                       command=self.export_srt, state="disabled")
        self.export_button.grid(row=0, column=2)
        
        # Progress
        self.progress_var = tk.StringVar(value="Bereit für Audio-Extraktion")
        self.progress_label = ttk.Label(main_frame, textvariable=self.progress_var)
        self.progress_label.grid(row=5, column=0, columnspan=3, pady=10)
        
        self.progress_bar = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress_bar.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Results Area
        results_frame = ttk.LabelFrame(main_frame, text="Transkriptions-Ergebnisse", padding="5")
        results_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Text segments list with scrollbar
        list_frame = ttk.Frame(results_frame)
        list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.segments_tree = ttk.Treeview(list_frame, columns=("time", "text"), show="headings", height=15)
        self.segments_tree.heading("time", text="Zeit")
        self.segments_tree.heading("text", text="Text")
        self.segments_tree.column("time", width=100)
        self.segments_tree.column("text", width=500)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.segments_tree.yview)
        self.segments_tree.configure(yscrollcommand=scrollbar.set)
        
        self.segments_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Edit frame
        edit_frame = ttk.Frame(results_frame)
        edit_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Label(edit_frame, text="Text bearbeiten:").grid(row=0, column=0, sticky=tk.W)
        self.edit_text = tk.Text(edit_frame, height=3, width=70)
        self.edit_text.grid(row=1, column=0, columnspan=2, pady=5, sticky=(tk.W, tk.E))
        
        ttk.Button(edit_frame, text="Änderung übernehmen", 
                  command=self.update_segment).grid(row=2, column=0, pady=5, sticky=tk.W)
        
        # Bind events
        self.segments_tree.bind("<<TreeviewSelect>>", self.on_segment_select)
        self.segments_tree.bind("<Double-Button-1>", self.on_segment_double_click)
        
        # Grid configuration
        main_frame.columnconfigure(0, weight=1)
        results_frame.columnconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        edit_frame.columnconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.rowconfigure(7, weight=1)
        results_frame.rowconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
    def extract_audio(self):
        """Extrahiert Audio aus dem Video"""
        self.progress_var.set("Audio wird extrahiert...")
        self.progress_bar.start()
        self.extract_button.config(state="disabled")
        
        thread = threading.Thread(target=self._extract_audio_thread)
        thread.daemon = True
        thread.start()
        
    def _extract_audio_thread(self):
        """Extrahiert Audio in separatem Thread"""
        try:
            # Temporäre Audio-Datei erstellen
            temp_dir = tempfile.mkdtemp()
            self.temp_audio_path = os.path.join(temp_dir, "audio.wav")
            
            # FFmpeg Befehl für Audio-Extraktion
            cmd = [
                "ffmpeg", "-nostdin", "-i", self.video_path,
                "-vn",  # Kein Video
                "-acodec", "pcm_s16le",  # WAV Format
                "-ar", "16000",  # 16kHz Sample Rate für Whisper
                "-ac", "1",  # Mono
                "-y",  # Überschreiben
                self.temp_audio_path
            ]
            
            # Hardened subprocess invocation with proper error handling
            subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                shell=False, 
                timeout=FFMPEG_TIMEOUT, 
                check=True, 
                **SUBPROCESS_FLAGS
            )
            
            self.root.after(0, self._extraction_complete)
            
        except subprocess.CalledProcessError as e:
            # FFmpeg failed with non-zero exit code
            error_msg = f"FFmpeg Fehler (Exit Code {e.returncode}):\nStderr: {e.stderr}\nStdout: {e.stdout}"
            self.root.after(0, self._extraction_error, error_msg)
        except subprocess.TimeoutExpired as e:
            # FFmpeg timed out
            error_msg = f"FFmpeg Timeout nach {FFMPEG_TIMEOUT}s - Video möglicherweise zu groß oder beschädigt"
            self.root.after(0, self._extraction_error, error_msg)
        except Exception as e:
            # Other errors (file not found, permission issues, etc.)
            self.root.after(0, self._extraction_error, str(e))
            
    def _extraction_complete(self):
        """Audio-Extraktion erfolgreich abgeschlossen"""
        self.progress_bar.stop()
        self.progress_var.set("Audio erfolgreich extrahiert - bereit für Transkription")
        self.extract_button.config(state="normal")
        self.transcribe_button.config(state="normal")
        
    def _extraction_error(self, error_msg: str):
        """Fehler bei Audio-Extraktion"""
        self.progress_bar.stop()
        self.progress_var.set("Fehler bei Audio-Extraktion")
        self.extract_button.config(state="normal")
        messagebox.showerror("Extraktion fehlgeschlagen", f"Audio konnte nicht extrahiert werden:\n{error_msg}")
        
    def start_transcription(self):
        """Startet die Whisper-Transkription"""
        if not self.temp_audio_path or not os.path.exists(self.temp_audio_path):
            messagebox.showerror("Fehler", "Bitte extrahieren Sie zuerst das Audio.")
            return
            
        self.progress_var.set("Whisper-Modell wird geladen...")
        self.progress_bar.start()
        self.transcribe_button.config(state="disabled")
        
        thread = threading.Thread(target=self._transcribe_thread)
        thread.daemon = True
        thread.start()
        
    def _transcribe_thread(self):
        """Führt Transkription in separatem Thread aus"""
        try:
            # Whisper Modell laden
            model_name = self.model_var.get()
            self.whisper_model = whisper.load_model(model_name)
            
            self.root.after(0, lambda: self.progress_var.set("Transkription läuft..."))
            
            # Sprache für Whisper
            language = self.language_var.get() if self.language_var.get() != "auto" else None
            
            # Transkription durchführen
            result = self.whisper_model.transcribe(
                self.temp_audio_path,
                language=language,
                word_timestamps=True
            )
            
            # Segmente extrahieren
            self.audio_segments = []
            for segment in result["segments"]:
                audio_seg = TranscriptionSegment(
                    start=segment["start"],
                    end=segment["end"],
                    text=segment["text"].strip()
                )
                self.audio_segments.append(audio_seg)
            
            self.root.after(0, self._transcription_complete)
            
        except Exception as e:
            self.root.after(0, self._transcription_error, str(e))
            
    def _transcription_complete(self):
        """Transkription erfolgreich abgeschlossen"""
        self.progress_bar.stop()
        self.progress_var.set(f"Transkription abgeschlossen - {len(self.audio_segments)} Segmente erkannt")
        self.transcribe_button.config(state="normal")
        self.export_button.config(state="normal")
        
        # Ergebnisse in TreeView anzeigen
        for segment in self.audio_segments:
            time_str = f"{self._format_time(segment.start)} - {self._format_time(segment.end)}"
            self.segments_tree.insert("", "end", values=(time_str, segment.text))
            
    def _transcription_error(self, error_msg: str):
        """Fehler bei Transkription"""
        self.progress_bar.stop()
        self.progress_var.set("Fehler bei Transkription")
        self.transcribe_button.config(state="normal")
        messagebox.showerror("Transkription fehlgeschlagen", f"Transkription konnte nicht durchgeführt werden:\n{error_msg}")
        
    def on_segment_select(self, event):
        """Wird aufgerufen wenn ein Segment ausgewählt wird"""
        selection = self.segments_tree.selection()
        if selection:
            item = selection[0]
            index = self.segments_tree.index(item)
            if 0 <= index < len(self.audio_segments):
                segment = self.audio_segments[index]
                self.edit_text.delete(1.0, tk.END)
                self.edit_text.insert(1.0, segment.text)

    def on_segment_double_click(self, event):
        """Wird aufgerufen bei Doppelklick auf ein Segment - spielt Audio ab"""
        selection = self.segments_tree.selection()
        if selection:
            item = selection[0]
            index = self.segments_tree.index(item)
            self.play_audio_segment(index)
                
    def update_segment(self):
        """Aktualisiert das ausgewählte Segment"""
        selection = self.segments_tree.selection()
        if not selection:
            messagebox.showwarning("Warnung", "Bitte wählen Sie ein Segment aus.")
            return

        item = selection[0]
        index = self.segments_tree.index(item)
        if 0 <= index < len(self.audio_segments):
            new_text = self.edit_text.get(1.0, tk.END).strip()
            self.audio_segments[index].text = new_text
            self.audio_segments[index].edited = True

            # TreeView aktualisieren
            time_str = f"{self._format_time(self.audio_segments[index].start)} - {self._format_time(self.audio_segments[index].end)}"
            self.segments_tree.item(item, values=(time_str, new_text))

    def play_audio_segment(self, index: int):
        """Spielt das Audio-Segment für den gegebenen Index ab"""
        if not self.temp_audio_path or not os.path.exists(self.temp_audio_path):
            messagebox.showerror("Fehler", "Audio-Datei nicht verfügbar. Bitte extrahieren Sie zuerst das Audio.")
            return

        if 0 <= index < len(self.audio_segments):
            segment = self.audio_segments[index]
            try:
                # Temporäre Datei für das Segment erstellen
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    segment_path = temp_file.name

                # FFmpeg verwenden, um das Segment zu extrahieren
                # Puffer von 50ms vorne und hinten für sanftere Übergänge
                buffer_ms = 0.050  # 50 Millisekunden
                start_time = max(0, segment.start - buffer_ms)  # Nicht vor 0 gehen
                end_time = segment.end + buffer_ms

                # Sicherstellen, dass end_time nicht über die Audio-Länge hinausgeht
                # (Wir kennen die Audio-Länge nicht genau, aber FFmpeg handhabt das)
                duration = end_time - start_time

                cmd = [
                    "ffmpeg",
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{start_time:.3f}",
                    "-t",
                    f"{duration:.3f}",
                    "-i",
                    self.temp_audio_path,
                    "-vn",
                    "-y",
                    "-acodec",
                    "copy",
                    segment_path,
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    shell=False,
                    timeout=30,  # 30 Sekunden Timeout
                    **SUBPROCESS_FLAGS,
                    check=False,
                )
                    if result.returncode != 0:
                        messagebox.showerror(
                            "Fehler",
                            f"FFmpeg konnte das Segment nicht extrahieren "
                            f"(Exit Code {result.returncode}):\n{result.stderr or 'Kein Fehlerausgabe'}"
                        )
                        if os.path.exists(segment_path):
                            os.remove(segment_path)
                        return

                    # Segment mit ffplay abspielen (asynchron)
                    play_cmd = [
                        "ffplay", "-nodisp", "-autoexit", segment_path
                    ]
                    play_thread = threading.Thread(
                        target=self._play_with_ffplay,
                        args=(play_cmd, segment_path),
                        daemon=True,
                    )
                    play_thread.start()
            except Exception as e:
                messagebox.showerror("Fehler", f"Audio konnte nicht abgespielt werden:\n{str(e)}")
        """Spielt Audio mit ffplay ab und bereinigt temporäre Datei"""
        try:
            subprocess.run(cmd, **SUBPROCESS_FLAGS)
        except Exception as e:
            print(f"ffplay error: {e}")
        finally:
            # Temporäre Datei löschen
            try:
                if os.path.exists(segment_path):
                    os.remove(segment_path)
            except:
                pass
            
    def export_srt(self):
        """Exportiert die Transkription als SRT-Datei"""
        if not self.audio_segments:
            messagebox.showerror("Fehler", "Keine Transkription verfügbar.")
            return
            
        # Datei-Dialog für Speicherort mit Video-basiertem Standard-Namen
        video_basename = os.path.basename(self.video_path)
        video_name_without_ext = os.path.splitext(video_basename)[0]
        default_srt_name = f"{video_name_without_ext}.srt"
        
        filename = filedialog.asksaveasfilename(
            title="SRT-Datei speichern",
            defaultextension=".srt",
            filetypes=[("SRT-Dateien", "*.srt"), ("Alle Dateien", "*.*")],
            initialfile=default_srt_name,
            initialdir=os.path.dirname(self.video_path),
            confirmoverwrite=True
        )
        
        if not filename:
            return
            
        try:
            self._write_srt_file(filename)
            self.subtitle_var.set(filename)  # Setze Pfad in Haupt-App
            messagebox.showinfo("Erfolg", f"SRT-Datei erfolgreich gespeichert:\n{filename}")
            
            # Fenster nach erfolgreichem Export schließen
            self.root.after(500, self.on_closing)  # Kurze Verzögerung für Benutzer-Feedback
            
        except Exception as e:
            messagebox.showerror("Export fehlgeschlagen", f"SRT-Datei konnte nicht gespeichert werden:\n{str(e)}")
            
    def _write_srt_file(self, filename: str):
        """Schreibt SRT-Datei"""
        with open(filename, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(self.audio_segments, 1):
                start_time = self._format_srt_time(segment.start)
                end_time = self._format_srt_time(segment.end)
                
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{segment.text}\n\n")
                
    def _format_time(self, seconds: float) -> str:
        """Formatiert Zeit für Anzeige"""
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:05.2f}"
        
    def _format_srt_time(self, seconds: float) -> str:
        """Formatiert Zeit für SRT-Format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')
        
    def on_closing(self):
        """Aufräumen beim Schließen"""
        if self.temp_audio_path and os.path.exists(self.temp_audio_path):
            try:
                os.remove(self.temp_audio_path)
                os.rmdir(os.path.dirname(self.temp_audio_path))
            except:
                pass
        self.root.destroy()
        
    def run(self):
        """Startet die Anwendung"""
        self.root.mainloop()


if __name__ == "__main__":
    # Test-Modus
    if len(sys.argv) > 1:
        import sys
        video_path = sys.argv[1]
        dummy_var = tk.StringVar()
        transcriber = AudioTranscriber(video_path, dummy_var)
        transcriber.run()