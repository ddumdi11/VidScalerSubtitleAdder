"""
Text Extractor - SRT zu aufbereitetem Text-Exzerpt
Konvertiert .srt-Dateien zu gut lesbaren .txt/.md-Dokumenten
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import re
import threading
from typing import List, Optional
from dataclasses import dataclass

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class SRTEntry:
    """Repräsentiert einen SRT-Eintrag"""
    start_time: str
    end_time: str
    text: str


class TextExtractor:
    """Extrahiert und verarbeitet Text aus SRT-Dateien"""
    
    def __init__(self, srt_path: str):
        self.srt_path = srt_path
        self.raw_text = ""
        self.processed_text = ""
        
        # SpaCy-Pipeline laden (falls verfügbar)
        self.nlp = None
        if SPACY_AVAILABLE:
            try:
                # Versuche deutsche Pipeline zu laden
                self.nlp = spacy.load("de_core_news_sm")
            except OSError:
                try:
                    # Fallback: englische Pipeline
                    self.nlp = spacy.load("en_core_web_sm")
                except OSError:
                    pass
        
        self.root = tk.Toplevel()
        self.root.title("Text-Exzerpt Ersteller")
        self.root.geometry("800x600")
        self.setup_ui()
        
    def setup_ui(self):
        """Erstellt die Benutzeroberfläche"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Header
        ttk.Label(main_frame, text="Text-Exzerpt Ersteller", font=("Arial", 16, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 10)
        )
        
        srt_name = os.path.basename(self.srt_path)
        ttk.Label(main_frame, text=f"SRT-Datei: {srt_name}", font=("Arial", 10)).grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 15)
        )
        
        # Verarbeitungsoptionen
        options_frame = ttk.LabelFrame(main_frame, text="Verarbeitungsoptionen", padding="10")
        options_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # SpaCy Option
        self.use_spacy_var = tk.BooleanVar(value=SPACY_AVAILABLE and self.nlp is not None)
        self.spacy_check = ttk.Checkbutton(options_frame, text="SpaCy für Satzgrenzen verwenden", 
                                         variable=self.use_spacy_var,
                                         state="normal" if (SPACY_AVAILABLE and self.nlp) else "disabled")
        self.spacy_check.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        if not SPACY_AVAILABLE:
            ttk.Label(options_frame, text="(SpaCy nicht installiert)", foreground="gray").grid(
                row=0, column=1, sticky=tk.W, padx=(10, 0)
            )
        elif self.nlp is None:
            ttk.Label(options_frame, text="(SpaCy Sprachmodell fehlt)", foreground="gray").grid(
                row=0, column=1, sticky=tk.W, padx=(10, 0)
            )
        
        # OpenAI Option
        self.use_openai_var = tk.BooleanVar(value=OPENAI_AVAILABLE)
        self.openai_check = ttk.Checkbutton(options_frame, text="OpenAI für Textveredelung verwenden", 
                                          variable=self.use_openai_var,
                                          state="normal" if OPENAI_AVAILABLE else "disabled")
        self.openai_check.grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        if not OPENAI_AVAILABLE:
            ttk.Label(options_frame, text="(OpenAI nicht installiert)", foreground="gray").grid(
                row=1, column=1, sticky=tk.W, padx=(10, 0)
            )
        
        # API Key Eingabe (nur sichtbar wenn OpenAI verfügbar)
        if OPENAI_AVAILABLE:
            ttk.Label(options_frame, text="OpenAI API Key:").grid(row=2, column=0, sticky=tk.W, pady=(10, 5))
            self.api_key_var = tk.StringVar()
            self.api_key_entry = ttk.Entry(options_frame, textvariable=self.api_key_var, width=50, show="*")
            self.api_key_entry.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # Export-Format
        format_frame = ttk.LabelFrame(main_frame, text="Export-Format", padding="10")
        format_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        self.format_var = tk.StringVar(value="txt")
        ttk.Radiobutton(format_frame, text="Einfacher Text (.txt)", variable=self.format_var, value="txt").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 20)
        )
        ttk.Radiobutton(format_frame, text="Markdown (.md)", variable=self.format_var, value="md").grid(
            row=0, column=1, sticky=tk.W
        )
        
        # Verarbeitungs-Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=(0, 15))
        
        self.process_button = ttk.Button(button_frame, text="Text verarbeiten", command=self.process_text)
        self.process_button.grid(row=0, column=0, padx=(0, 10))
        
        self.export_button = ttk.Button(button_frame, text="Als Datei speichern", 
                                      command=self.export_text, state="disabled")
        self.export_button.grid(row=0, column=1)
        
        # Text-Vorschau
        preview_frame = ttk.LabelFrame(main_frame, text="Vorschau", padding="10")
        preview_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Scrollbarer Text-Bereich
        self.text_widget = tk.Text(preview_frame, wrap=tk.WORD, width=70, height=15)
        scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)
        
        self.text_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Status
        self.status_var = tk.StringVar(value="Bereit")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var)
        self.status_label.grid(row=6, column=0, columnspan=2, pady=(10, 0))
        
        # Grid-Konfiguration
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(5, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
    def parse_srt(self) -> List[SRTEntry]:
        """Parsed SRT-Datei zu strukturierten Einträgen"""
        try:
            with open(self.srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(self.srt_path, 'r', encoding='latin-1') as f:
                content = f.read()
        
        entries = []
        # SRT-Pattern: Nummer, Zeit, Text, Leerzeile
        pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\d+\n|\n*$)'
        
        matches = re.findall(pattern, content, re.DOTALL)
        
        for match in matches:
            start_time = match[1]
            end_time = match[2]
            text = match[3].strip().replace('\n', ' ')
            
            if text:  # Nur nicht-leere Einträge
                entries.append(SRTEntry(start_time, end_time, text))
        
        return entries
        
    def extract_raw_text(self, entries: List[SRTEntry]) -> str:
        """Extrahiert reinen Text aus SRT-Einträgen"""
        texts = []
        for entry in entries:
            # HTML-Tags entfernen (falls vorhanden)
            clean_text = re.sub(r'<[^>]+>', '', entry.text)
            # Mehrfache Leerzeichen durch einzelne ersetzen
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            if clean_text:
                texts.append(clean_text)
        
        return ' '.join(texts)
    
    def process_with_spacy(self, text: str) -> str:
        """Verarbeitet Text mit SpaCy für bessere Satzgrenzen"""
        if not self.nlp:
            return text
            
        doc = self.nlp(text)
        sentences = []
        
        for sent in doc.sents:
            sentence = sent.text.strip()
            if sentence:
                sentences.append(sentence)
        
        return '\n\n'.join(sentences)
    
    def process_with_openai(self, text: str, api_key: str) -> str:
        """Verarbeitet Text mit OpenAI für bessere Formatierung"""
        if not OPENAI_AVAILABLE or not api_key:
            return text
            
        try:
            openai.api_key = api_key
            
            prompt = """Bitte überarbeite den folgenden Transkriptionstext und verbessere die Formatierung:

1. Gliedere den Text in sinnvolle Absätze
2. Korrigiere offensichtliche Transkriptionsfehler
3. Verbessere die Satzzeichen und Groß-/Kleinschreibung
4. Strukturiere den Text für bessere Lesbarkeit
5. Behalte den ursprünglichen Inhalt bei, ändere nur Formatierung und kleine Korrekturen

Text:
"""
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Du bist ein Experte für Textbearbeitung und Transkriptionsverbesserung."},
                    {"role": "user", "content": prompt + text}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"OpenAI-Verarbeitung fehlgeschlagen: {str(e)}")
    
    def process_text(self):
        """Startet Textverarbeitung in separatem Thread"""
        self.process_button.config(state="disabled")
        self.export_button.config(state="disabled")
        self.status_var.set("Verarbeitung läuft...")
        
        thread = threading.Thread(target=self._process_text_thread)
        thread.daemon = True
        thread.start()
    
    def _process_text_thread(self):
        """Verarbeitet Text in separatem Thread"""
        try:
            # 1. SRT parsen
            self.root.after(0, lambda: self.status_var.set("SRT-Datei wird geparst..."))
            entries = self.parse_srt()
            
            if not entries:
                raise Exception("Keine gültigen SRT-Einträge gefunden")
            
            # 2. Rohtext extrahieren
            self.root.after(0, lambda: self.status_var.set("Text wird extrahiert..."))
            self.raw_text = self.extract_raw_text(entries)
            
            if not self.raw_text.strip():
                raise Exception("Kein Text im SRT gefunden")
            
            # 3. SpaCy-Verarbeitung (falls aktiviert)
            processed_text = self.raw_text
            if self.use_spacy_var.get() and self.nlp:
                self.root.after(0, lambda: self.status_var.set("Text wird mit SpaCy verarbeitet..."))
                processed_text = self.process_with_spacy(processed_text)
            
            # 4. OpenAI-Verarbeitung (falls aktiviert)
            if self.use_openai_var.get() and OPENAI_AVAILABLE:
                api_key = self.api_key_var.get().strip()
                if api_key:
                    self.root.after(0, lambda: self.status_var.set("Text wird mit OpenAI veredelt..."))
                    processed_text = self.process_with_openai(processed_text, api_key)
                else:
                    self.root.after(0, lambda: messagebox.showwarning("Warnung", 
                        "OpenAI-Verarbeitung übersprungen: Kein API-Key eingegeben"))
            
            self.processed_text = processed_text
            
            # UI-Update
            self.root.after(0, self._update_preview)
            
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self._show_error(error_msg))
    
    def _update_preview(self):
        """Aktualisiert Vorschau nach erfolgreicher Verarbeitung"""
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(1.0, self.processed_text)
        
        self.process_button.config(state="normal")
        self.export_button.config(state="normal")
        self.status_var.set("Verarbeitung abgeschlossen - bereit zum Export")
    
    def _show_error(self, error_msg: str):
        """Zeigt Fehler an"""
        self.process_button.config(state="normal")
        self.status_var.set("Fehler bei der Verarbeitung")
        messagebox.showerror("Verarbeitungsfehler", f"Text konnte nicht verarbeitet werden:\n{error_msg}")
    
    def export_text(self):
        """Exportiert verarbeiteten Text als Datei"""
        if not self.processed_text.strip():
            messagebox.showerror("Fehler", "Kein Text zum Exportieren verfügbar. Bitte verarbeiten Sie zuerst den Text.")
            return
        
        # Dateiname vorschlagen
        srt_name = os.path.splitext(os.path.basename(self.srt_path))[0]
        format_ext = self.format_var.get()
        default_name = f"{srt_name}_exzerpt.{format_ext}"
        
        # Datei-Dialog
        if format_ext == "md":
            filetypes = [("Markdown-Dateien", "*.md"), ("Alle Dateien", "*.*")]
        else:
            filetypes = [("Text-Dateien", "*.txt"), ("Alle Dateien", "*.*")]
        
        output_path = filedialog.asksaveasfilename(
            title="Text-Exzerpt speichern",
            defaultextension=f".{format_ext}",
            initialvalue=default_name,
            filetypes=filetypes
        )
        
        if output_path:
            try:
                content = self.processed_text
                
                # Markdown-spezifische Formatierung hinzufügen
                if format_ext == "md":
                    video_name = os.path.splitext(os.path.basename(self.srt_path.replace('_subtitles.srt', '')))[0]
                    content = f"# Transkript: {video_name}\n\n{content}"
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.status_var.set(f"Text erfolgreich exportiert: {os.path.basename(output_path)}")
                messagebox.showinfo("Erfolg", f"Text-Exzerpt erfolgreich gespeichert!\n{output_path}")
                
            except Exception as e:
                messagebox.showerror("Export-Fehler", f"Datei konnte nicht gespeichert werden:\n{str(e)}")
    
    def run(self):
        """Startet das Fenster"""
        self.root.mainloop()


def extract_text_from_srt(srt_path: str):
    """Standalone-Funktion zum Öffnen des Text-Extractors"""
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f"SRT-Datei nicht gefunden: {srt_path}")
    
    extractor = TextExtractor(srt_path)
    extractor.run()


if __name__ == "__main__":
    # Test-Funktionalität
    import sys
    if len(sys.argv) > 1:
        extract_text_from_srt(sys.argv[1])
    else:
        print("Usage: python text_extractor.py <srt_file_path>")