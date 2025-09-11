"""
VidScaler - GUI-Anwendung zum Skalieren von Videos mit FFmpeg
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from typing import Optional, List, Tuple
import threading

from video_processor import VideoProcessor
from utils import get_video_info, generate_scaling_options


class VidScalerApp:
    def __init__(self, root: tk.Tk):
        """
        Initialize the VidScalerApp GUI.
        
        Sets up the main Tk window (title and geometry), creates the VideoProcessor, and initializes application state
        placeholders for the currently selected video, its resolution, and any subtitle path. Builds the UI by calling
        setup_ui().
        """
        self.root = root
        self.root.title("VidScaler - Video Skalierung")
        self.root.geometry("600x600")
        
        self.video_processor = VideoProcessor()
        self.current_video_path: Optional[str] = None
        self.current_resolution: Optional[Tuple[int, int]] = None
        self.current_subtitle_path: Optional[str] = None
        
        self.setup_ui()
        
    def setup_ui(self):
        """
        Builds the application's main tkinter user interface and initializes all widgets and their callbacks.
        
        Creates sections and widgets for:
        - video selection (file entry + browse),
        - video info (resolution label),
        - scaling options (width combobox),
        - subtitles (subtitle path entry, browse, audio transcription, text excerpt),
        - optional translation (enable checkbox, source/target language selectors, translation method and whisper model selector, translation mode radio buttons),
        - action buttons (analyze, scale, scale with subtitles, scale with translation),
        - progress label and indeterminate progress bar.
        
        Translation-related widgets are initially disabled; the subtitle path variable is traced to update UI state when changed. Widgets are laid out using ttk and grid geometry.
        """
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Video Auswahl
        ttk.Label(main_frame, text="Video auswählen:", font=("Arial", 12, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 5)
        )
        
        file_frame = ttk.Frame(main_frame)
        file_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        self.file_path_var = tk.StringVar()
        self.file_entry = ttk.Entry(file_frame, textvariable=self.file_path_var, width=50)
        self.file_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Button(file_frame, text="Durchsuchen...", command=self.browse_file).grid(
            row=0, column=1
        )
        
        file_frame.columnconfigure(0, weight=1)
        
        # Video Information
        ttk.Label(main_frame, text="Video Information:", font=("Arial", 12, "bold")).grid(
            row=2, column=0, sticky=tk.W, pady=(0, 5)
        )
        
        info_frame = ttk.Frame(main_frame)
        info_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        ttk.Label(info_frame, text="Aktuelle Auflösung:").grid(row=0, column=0, sticky=tk.W)
        self.resolution_label = ttk.Label(info_frame, text="Kein Video geladen", foreground="gray")
        self.resolution_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        # Skalierungsoptionen
        ttk.Label(main_frame, text="Skalierung:", font=("Arial", 12, "bold")).grid(
            row=4, column=0, sticky=tk.W, pady=(0, 5)
        )
        
        scale_frame = ttk.Frame(main_frame)
        scale_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        ttk.Label(scale_frame, text="Neue Breite:").grid(row=0, column=0, sticky=tk.W)
        self.scale_var = tk.StringVar()
        self.scale_combo = ttk.Combobox(scale_frame, textvariable=self.scale_var, width=20, state="readonly")
        self.scale_combo.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        # Untertitel-Sektion
        ttk.Label(main_frame, text="Untertitel:", font=("Arial", 12, "bold")).grid(
            row=6, column=0, sticky=tk.W, pady=(15, 5)
        )
        
        subtitle_frame = ttk.Frame(main_frame)
        subtitle_frame.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        self.subtitle_path_var = tk.StringVar()
        self.subtitle_path_var.trace('w', self._on_subtitle_path_change)  # Callback für Pfad-Änderungen
        self.subtitle_entry = ttk.Entry(subtitle_frame, textvariable=self.subtitle_path_var, width=40)
        self.subtitle_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Button(subtitle_frame, text="Untertitel wählen...", command=self.browse_subtitle_file).grid(
            row=0, column=1, padx=(0, 10)
        )
        
        ttk.Button(subtitle_frame, text="Audio transkribieren", command=self.open_audio_transcriber).grid(
            row=0, column=2, padx=(0, 10)
        )
        
        self.text_extract_button = ttk.Button(subtitle_frame, text="Text-Exzerpt erstellen", 
                                            command=self.open_text_extractor, state="disabled")
        self.text_extract_button.grid(row=0, column=3)
        
        subtitle_frame.columnconfigure(0, weight=1)
        
        # Übersetzungs-Sektion
        ttk.Label(main_frame, text="Übersetzung (optional):", font=("Arial", 12, "bold")).grid(
            row=8, column=0, sticky=tk.W, pady=(15, 5)
        )
        
        translation_frame = ttk.Frame(main_frame)
        translation_frame.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # Übersetzung aktivieren Checkbox
        self.translate_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(translation_frame, text="Übersetzung aktivieren", 
                       variable=self.translate_enabled_var,
                       command=self._on_translation_toggle).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        # Sprachauswahl
        lang_frame = ttk.Frame(translation_frame)
        lang_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(lang_frame, text="Von:").grid(row=0, column=0, sticky=tk.W)
        self.source_lang_var = tk.StringVar(value="en")
        self.source_lang_combo = ttk.Combobox(lang_frame, textvariable=self.source_lang_var, 
                                            width=12, state="readonly")
        self.source_lang_combo['values'] = ["auto", "de", "en", "fr", "es", "it", "pt", "ru", "zh"]
        self.source_lang_combo.grid(row=0, column=1, sticky=tk.W, padx=(5, 15))
        
        ttk.Label(lang_frame, text="Nach:").grid(row=0, column=2, sticky=tk.W)
        self.target_lang_var = tk.StringVar(value="de")
        self.target_lang_combo = ttk.Combobox(lang_frame, textvariable=self.target_lang_var, 
                                            width=12, state="readonly")
        self.target_lang_combo['values'] = ["de", "en", "fr", "es", "it", "pt", "ru", "zh"]
        self.target_lang_combo.grid(row=0, column=3, sticky=tk.W, padx=(5, 0))
        
        # Übersetzungsmethode
        method_frame = ttk.Frame(translation_frame)
        method_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(method_frame, text="Methode:").grid(row=0, column=0, sticky=tk.W)
        self.translation_method_var = tk.StringVar(value="OpenAI (beste Qualität)")
        self.method_combo = ttk.Combobox(method_frame, textvariable=self.translation_method_var, 
                                       width=20, state="readonly")
        self.method_combo['values'] = ["OpenAI (beste Qualität)", "Google Translate (schnell)", "Whisper (hochwertig)"]
        self.method_combo.bind('<<ComboboxSelected>>', self._on_method_change)
        self.method_combo.grid(row=0, column=1, sticky=tk.W, padx=(5, 15))
        
        # Whisper-Modell-Auswahl (initial versteckt)
        self.whisper_model_var = tk.StringVar(value="base")
        self.whisper_label = ttk.Label(method_frame, text="Modell:")
        self.whisper_combo = ttk.Combobox(method_frame, textvariable=self.whisper_model_var, 
                                        width=12, state="readonly")
        self.whisper_combo['values'] = ["tiny (schnell)", "base (empfohlen)", "small (genau)"]
        
        # Übersetzungsmodus
        mode_frame = ttk.Frame(translation_frame)
        mode_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E))
        
        self.translation_mode_var = tk.StringVar(value="dual")
        ttk.Radiobutton(mode_frame, text="Original oben, Übersetzung unten", 
                       variable=self.translation_mode_var, value="dual").grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(mode_frame, text="Nur Übersetzung", 
                       variable=self.translation_mode_var, value="only").grid(row=0, column=1, sticky=tk.W, padx=(20, 0))
        
        # Initial alle Übersetzungs-Widgets deaktivieren
        self._toggle_translation_widgets(False)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=10, column=0, columnspan=2, pady=(20, 0))
        
        self.analyze_button = ttk.Button(button_frame, text="Video analysieren", command=self.analyze_video)
        self.analyze_button.grid(row=0, column=0, padx=(0, 10))
        
        self.scale_button = ttk.Button(button_frame, text="Video skalieren", command=self.scale_video, state="disabled")
        self.scale_button.grid(row=0, column=1, padx=(0, 10))
        
        self.subtitle_button = ttk.Button(button_frame, text="Mit Untertiteln skalieren", command=self.scale_video_with_subtitles, state="disabled")
        self.subtitle_button.grid(row=0, column=2, padx=(0, 10))
        
        self.translate_button = ttk.Button(button_frame, text="Mit Übersetzung skalieren", command=self.scale_video_with_translation, state="disabled")
        self.translate_button.grid(row=0, column=3)
        
        # Progress Bar
        self.progress_var = tk.StringVar(value="Bereit")
        self.progress_label = ttk.Label(main_frame, textvariable=self.progress_var)
        self.progress_label.grid(row=11, column=0, columnspan=2, pady=(20, 0))
        
        self.progress_bar = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress_bar.grid(row=12, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Grid-Konfiguration
        main_frame.columnconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
    def browse_file(self):
        """Öffnet Datei-Dialog zur Video-Auswahl"""
        filetypes = [
            ("Video-Dateien", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm"),
            ("Alle Dateien", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title="Video auswählen",
            filetypes=filetypes
        )
        
        if filename:
            self.file_path_var.set(filename)
            self.current_video_path = filename
            self.reset_ui()
            
    def browse_subtitle_file(self):
        """Öffnet Datei-Dialog zur Untertitel-Auswahl"""
        filetypes = [
            ("Untertitel-Dateien", "*.srt *.ass *.vtt"),
            ("Alle Dateien", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title="Untertitel auswählen",
            filetypes=filetypes
        )
        
        if filename:
            self.subtitle_path_var.set(filename)
            self.current_subtitle_path = filename
            self._update_subtitle_button_state()
            
    def analyze_video(self):
        """Analysiert das ausgewählte Video"""
        if not self.current_video_path:
            messagebox.showerror("Fehler", "Bitte wählen Sie zuerst ein Video aus.")
            return
            
        if not os.path.exists(self.current_video_path):
            messagebox.showerror("Fehler", "Die ausgewählte Datei existiert nicht.")
            return
            
        self.progress_var.set("Video wird analysiert...")
        self.progress_bar.start()
        self.analyze_button.config(state="disabled")
        
        # Analyse in separatem Thread
        thread = threading.Thread(target=self._analyze_video_thread)
        thread.daemon = True
        thread.start()
        
    def _analyze_video_thread(self):
        """Analysiert Video in separatem Thread"""
        try:
            width, height = get_video_info(self.current_video_path)
            self.current_resolution = (width, height)
            
            # UI-Update im Hauptthread
            self.root.after(0, self._update_analysis_ui, width, height)
            
        except Exception as e:
            self.root.after(0, self._show_analysis_error, str(e))
            
    def _update_analysis_ui(self, width: int, height: int):
        """Aktualisiert UI nach erfolgreicher Analyse"""
        self.progress_bar.stop()
        self.progress_var.set("Bereit")
        self.analyze_button.config(state="normal")
        
        # Auflösung anzeigen
        self.resolution_label.config(text=f"{width} x {height}", foreground="black")
        
        # Skalierungsoptionen generieren
        scaling_options = generate_scaling_options(width, height)
        self.scale_combo['values'] = [f"{w} (Qualität: {q}%)" for w, q in scaling_options]
        
        if scaling_options:
            self.scale_combo.current(0)
            self.scale_button.config(state="normal")
            self._update_subtitle_button_state()
            
    def _show_analysis_error(self, error_msg: str):
        """Zeigt Analysefehler an"""
        self.progress_bar.stop()
        self.progress_var.set("Bereit")
        self.analyze_button.config(state="normal")
        messagebox.showerror("Analysefehler", f"Video konnte nicht analysiert werden:\n{error_msg}")
        
    def scale_video(self):
        """Startet Video-Skalierung"""
        if not self.current_video_path or not self.current_resolution:
            messagebox.showerror("Fehler", "Bitte analysieren Sie zuerst das Video.")
            return
            
        selected = self.scale_var.get()
        if not selected:
            messagebox.showerror("Fehler", "Bitte wählen Sie eine Skalierungsoption aus.")
            return
            
        # Breite aus Auswahl extrahieren
        new_width = int(selected.split()[0])
        
        # Ausgabedatei generieren
        input_path = self.current_video_path
        name, ext = os.path.splitext(input_path)
        output_path = f"{name}_scaled{ext}"
        
        self.progress_var.set("Video wird skaliert...")
        self.progress_bar.start()
        self.scale_button.config(state="disabled")
        self.analyze_button.config(state="disabled")
        
        # Skalierung in separatem Thread
        thread = threading.Thread(target=self._scale_video_thread, args=(input_path, output_path, new_width))
        thread.daemon = True
        thread.start()
        
    def _scale_video_thread(self, input_path: str, output_path: str, new_width: int):
        """Skaliert Video in separatem Thread"""
        try:
            self.video_processor.scale_video(input_path, output_path, new_width)
            self.root.after(0, self._show_scaling_success, output_path)
            
        except Exception as e:
            self.root.after(0, self._show_scaling_error, str(e))
            
    def _show_scaling_success(self, output_path: str):
        """Zeigt Erfolgsmeldung nach Skalierung"""
        self.progress_bar.stop()
        self.progress_var.set("Bereit")
        self.scale_button.config(state="normal")
        self.analyze_button.config(state="normal")
        self._update_subtitle_button_state()
        
        messagebox.showinfo("Erfolg", f"Video erfolgreich skaliert!\nGespeichert unter: {output_path}")
        
    def _show_scaling_error(self, error_msg: str):
        """Zeigt Skalierungsfehler an"""
        self.progress_bar.stop()
        self.progress_var.set("Bereit")
        self.scale_button.config(state="normal")
        self.analyze_button.config(state="normal")
        self._update_subtitle_button_state()
        messagebox.showerror("Skalierungsfehler", f"Video konnte nicht skaliert werden:\n{error_msg}")
        
    def reset_ui(self):
        """Setzt UI-Elemente zurück"""
        self.resolution_label.config(text="Kein Video geladen", foreground="gray")
        self.scale_combo['values'] = []
        self.scale_var.set("")
        self.scale_button.config(state="disabled")
        self.subtitle_button.config(state="disabled")
        self.translate_button.config(state="disabled")
        self.text_extract_button.config(state="disabled")
        self.current_resolution = None
        
    def _update_subtitle_button_state(self):
        """Aktualisiert Status der Untertitel/Übersetzungs-Buttons"""
        # Normale Untertitel-Button
        if (self.current_video_path and self.current_resolution and 
            self.current_subtitle_path and self.scale_var.get()):
            self.subtitle_button.config(state="normal")
        else:
            self.subtitle_button.config(state="disabled")
            
        # Übersetzungs-Button
        if (self.current_video_path and self.current_resolution and 
            self.current_subtitle_path and self.scale_var.get() and 
            self.translate_enabled_var.get()):
            self.translate_button.config(state="normal")
        else:
            self.translate_button.config(state="disabled")
            
        # Text-Exzerpt-Button
        if self.current_subtitle_path and os.path.exists(self.current_subtitle_path):
            self.text_extract_button.config(state="normal")
        else:
            self.text_extract_button.config(state="disabled")
            
    def scale_video_with_subtitles(self):
        """Startet Video-Skalierung mit Untertiteln"""
        if not self.current_video_path or not self.current_resolution:
            messagebox.showerror("Fehler", "Bitte analysieren Sie zuerst das Video.")
            return
            
        if not self.current_subtitle_path:
            messagebox.showerror("Fehler", "Bitte wählen Sie eine Untertitel-Datei aus.")
            return
            
        if not os.path.exists(self.current_subtitle_path):
            messagebox.showerror("Fehler", "Die ausgewählte Untertitel-Datei existiert nicht.")
            return
            
        selected = self.scale_var.get()
        if not selected:
            messagebox.showerror("Fehler", "Bitte wählen Sie eine Skalierungsoption aus.")
            return
            
        # Breite aus Auswahl extrahieren
        new_width = int(selected.split()[0])
        
        # Ausgabedatei generieren
        input_path = self.current_video_path
        name, ext = os.path.splitext(input_path)
        output_path = f"{name}_subtitled{ext}"
        
        self.progress_var.set("Video mit Untertiteln wird verarbeitet...")
        self.progress_bar.start()
        self.scale_button.config(state="disabled")
        self.subtitle_button.config(state="disabled")
        self.analyze_button.config(state="disabled")
        
        # Verarbeitung in separatem Thread
        thread = threading.Thread(target=self._scale_video_with_subtitles_thread, 
                                 args=(input_path, output_path, new_width, self.current_subtitle_path))
        thread.daemon = True
        thread.start()
        
    def _scale_video_with_subtitles_thread(self, input_path: str, output_path: str, new_width: int, subtitle_path: str):
        """Skaliert Video mit Untertiteln in separatem Thread"""
        try:
            self.video_processor.scale_video_with_subtitles(input_path, output_path, new_width, subtitle_path)
            self.root.after(0, self._show_scaling_success, output_path)
            
        except Exception as e:
            self.root.after(0, self._show_scaling_error, str(e))
            
    def scale_video_with_translation(self):
        """Startet Video-Skalierung mit Übersetzung"""
        if not self.current_video_path or not self.current_resolution:
            messagebox.showerror("Fehler", "Bitte analysieren Sie zuerst das Video.")
            return
            
        if not self.current_subtitle_path:
            messagebox.showerror("Fehler", "Bitte wählen Sie eine Untertitel-Datei aus.")
            return
            
        if not os.path.exists(self.current_subtitle_path):
            messagebox.showerror("Fehler", "Die ausgewählte Untertitel-Datei existiert nicht.")
            return
            
        selected = self.scale_var.get()
        if not selected:
            messagebox.showerror("Fehler", "Bitte wählen Sie eine Skalierungsoption aus.")
            return
            
        # Breite aus Auswahl extrahieren
        new_width = int(selected.split()[0])
        
        # Ausgabedatei generieren
        input_path = self.current_video_path
        name, ext = os.path.splitext(input_path)
        if self.translation_mode_var.get() == "dual":
            output_path = f"{name}_dual_subtitled{ext}"
        else:
            output_path = f"{name}_translated{ext}"
        
        self.progress_var.set("Video mit Übersetzung wird verarbeitet...")
        self.progress_bar.start()
        self.scale_button.config(state="disabled")
        self.subtitle_button.config(state="disabled")
        self.translate_button.config(state="disabled")
        self.analyze_button.config(state="disabled")
        
        # Verarbeitung in separatem Thread
        thread = threading.Thread(target=self._scale_video_with_translation_thread, 
                                 args=(input_path, output_path, new_width))
        thread.daemon = True
        thread.start()
        
    def _scale_video_with_translation_thread(self, input_path: str, output_path: str, new_width: int):
        """Skaliert Video mit Übersetzung in separatem Thread"""
        try:
            # Zuerst SRT übersetzen
            from translator import SubtitleTranslator
            translator = SubtitleTranslator()
            
            source_lang = self.source_lang_var.get()
            target_lang = self.target_lang_var.get()
            translation_mode = self.translation_mode_var.get()
            
            # Übersetzungsmethode bestimmen
            method_text = self.translation_method_var.get()
            if method_text == "Whisper (hochwertig)":
                method = "whisper"
                whisper_model = self.whisper_model_var.get().split()[0]  # "base (empfohlen)" -> "base"
            elif method_text == "OpenAI (beste Qualität)":
                method = "auto"  # Use auto to trigger OpenAI with fallback
                whisper_model = "base"
            else:  # "Google Translate (schnell)"
                method = "google"
                whisper_model = "base"
            
            self.root.after(0, lambda: self.progress_var.set(f"Untertitel werden übersetzt ({method})..."))
            
            translated_path = translator.translate_srt(
                self.current_subtitle_path, source_lang, target_lang,
                method=method, video_path=self.current_video_path, whisper_model=whisper_model
            )
            
            self.root.after(0, lambda: self.progress_var.set("Video wird mit Untertiteln verarbeitet..."))
            
            # Video mit Untertiteln verarbeiten
            self.video_processor.scale_video_with_translation(
                input_path, output_path, new_width, 
                self.current_subtitle_path, translated_path, translation_mode
            )
            
            self.root.after(0, self._show_scaling_success, output_path)
            
        except ImportError:
            self.root.after(0, lambda: messagebox.showerror("Fehler", 
                "Übersetzungsmodul konnte nicht geladen werden.\nBitte installieren Sie: pip install translators"))
        except Exception as e:
            self.root.after(0, self._show_scaling_error, str(e))
            
    def open_audio_transcriber(self):
        """Öffnet den Audio-Transkriptions-Editor"""
        if not self.current_video_path:
            messagebox.showerror("Fehler", "Bitte wählen Sie zuerst ein Video aus.")
            return
            
        if not os.path.exists(self.current_video_path):
            messagebox.showerror("Fehler", "Die ausgewählte Datei existiert nicht.")
            return
            
        try:
            from audio_transcriber import AudioTranscriber
            transcriber = AudioTranscriber(self.current_video_path, self.subtitle_path_var)
            transcriber.run()
            
        except ImportError:
            messagebox.showerror("Fehler", "Audio-Transkriptions-Modul konnte nicht geladen werden.\nBitte installieren Sie: pip install openai-whisper matplotlib pydub")
        except Exception as e:
            messagebox.showerror("Fehler", f"Audio-Transkriptor konnte nicht gestartet werden:\n{str(e)}")
            
    def open_text_extractor(self):
        """Öffnet den Text-Exzerpt-Ersteller"""
        if not self.current_subtitle_path:
            messagebox.showerror("Fehler", "Bitte wählen Sie zuerst eine SRT-Datei aus.")
            return
            
        if not os.path.exists(self.current_subtitle_path):
            messagebox.showerror("Fehler", "Die ausgewählte SRT-Datei existiert nicht.")
            return
            
        try:
            from text_extractor import TextExtractor
            extractor = TextExtractor(self.current_subtitle_path)
            extractor.run()
            
        except ImportError as e:
            missing_deps = []
            if "spacy" in str(e):
                missing_deps.append("spacy")
            if "openai" in str(e):
                missing_deps.append("openai")
            
            if missing_deps:
                messagebox.showwarning("Warnung", 
                    f"Text-Exzerpt-Ersteller gestartet mit eingeschränkter Funktionalität.\n"
                    f"Für erweiterte Features installieren Sie: pip install {' '.join(missing_deps)}")
                from text_extractor import TextExtractor
                extractor = TextExtractor(self.current_subtitle_path)
                extractor.run()
            else:
                messagebox.showerror("Fehler", f"Text-Exzerpt-Modul konnte nicht geladen werden:\n{str(e)}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Text-Exzerpt-Ersteller konnte nicht gestartet werden:\n{str(e)}")
            
    def _on_subtitle_path_change(self, *args):
        """Callback für Änderungen am Untertitel-Pfad"""
        subtitle_path = self.subtitle_path_var.get()
        if subtitle_path and os.path.exists(subtitle_path):
            self.current_subtitle_path = subtitle_path
        else:
            self.current_subtitle_path = None
        self._update_subtitle_button_state()
        
    def _on_translation_toggle(self):
        """Callback für Übersetzung aktivieren/deaktivieren"""
        enabled = self.translate_enabled_var.get()
        self._toggle_translation_widgets(enabled)
        self._update_subtitle_button_state()  # Button-State nach Toggle aktualisieren
        
    def _toggle_translation_widgets(self, enabled: bool):
        """Aktiviert/deaktiviert Übersetzungs-Widgets"""
        state = "normal" if enabled else "disabled"
        self.source_lang_combo.config(state=state)
        self.target_lang_combo.config(state=state)
        self.method_combo.config(state=state)
        if enabled and self.translation_method_var.get() == "Whisper (hochwertig)":
            self.whisper_combo.config(state="normal")
        else:
            self.whisper_combo.config(state="disabled")
            
    def _on_method_change(self, event=None):
        """Callback für Änderung der Übersetzungsmethode"""
        method = self.translation_method_var.get()
        if method == "Whisper (hochwertig)":
            # Whisper-Widgets anzeigen
            self.whisper_label.grid(row=0, column=2, sticky=tk.W, padx=(15, 5))
            self.whisper_combo.grid(row=0, column=3, sticky=tk.W)
            if self.translate_enabled_var.get():
                self.whisper_combo.config(state="normal")
        else:
            # Whisper-Widgets verstecken
            self.whisper_label.grid_remove()
            self.whisper_combo.grid_remove()


def main():
    """Hauptfunktion"""
    root = tk.Tk()
    app = VidScalerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()