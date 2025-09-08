"""
Subtitle Translator - Übersetzt SRT-Dateien mit verschiedenen Services
"""

import os
import re
import tempfile
from typing import List, Dict, Optional, Tuple

try:
    import translators as ts
    TRANSLATORS_AVAILABLE = True
except ImportError:
    TRANSLATORS_AVAILABLE = False

# Optional high-quality LLM translation module (OpenAI)
try:
    from smart_translation import translate_srt as smart_translate_srt
    SMART_TRANSLATION_AVAILABLE = True
except Exception:
    SMART_TRANSLATION_AVAILABLE = False

try:
    import whisper
    import subprocess
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


class WhisperTranslator:
    """Übersetzt Videos mittels Whisper-Transkription"""
    
    def __init__(self):
        if not WHISPER_AVAILABLE:
            raise ImportError("Whisper not available. Install with: pip install openai-whisper")
        self.model = None
        
    def extract_audio_for_whisper(self, video_path: str) -> str:
        """Extrahiert Audio aus Video für Whisper (wiederverwendet AudioTranscriber Logik)"""
        temp_dir = tempfile.mkdtemp()
        audio_path = os.path.join(temp_dir, "whisper_audio.wav")
        
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            "-y", audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"FFmpeg Audio-Extraktion fehlgeschlagen: {result.stderr}")
            
        return audio_path
    
    def translate_via_whisper(self, video_path: str, original_srt_path: str, 
                            target_lang: str, model_size: str = "base") -> str:
        """Übersetzt Video via Whisper-Transkription mit Original-Timing"""
        try:
            # 1. Audio extrahieren
            audio_path = self.extract_audio_for_whisper(video_path)
            
            # 2. Whisper-Modell laden
            if self.model is None or getattr(self.model, 'model_name', '') != model_size:
                self.model = whisper.load_model(model_size)
                self.model.model_name = model_size
            
            # 3. Original SRT-Timing lesen
            original_segments = self._parse_srt_timing(original_srt_path)
            
            # 4. Whisper-Transkription in Zielsprache
            result = self.model.transcribe(
                audio_path, 
                language=target_lang if target_lang != 'auto' else None,
                word_timestamps=True
            )
            
            # 5. Timing-Mapping: Whisper-Result auf Original-Segmente mappen
            translated_segments = self._map_whisper_to_original_timing(
                result["segments"], original_segments
            )
            
            # 6. Übersetzte SRT erstellen
            output_path = self._create_translated_srt(original_srt_path, translated_segments, "whisper")
            
            # 7. Aufräumen
            try:
                os.remove(audio_path)
                os.rmdir(os.path.dirname(audio_path))
            except:
                pass
                
            return output_path
            
        except Exception as e:
            raise Exception(f"Whisper-Übersetzung fehlgeschlagen: {str(e)}")
    
    def _parse_srt_timing(self, srt_path: str) -> List[Dict]:
        """Extrahiert nur Timing-Info aus Original-SRT"""
        segments = []
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
        blocks = content.split('\n\n')
        for block in blocks:
            if not block.strip():
                continue
            lines = block.strip().split('\n')
            if len(lines) >= 2:
                try:
                    index = int(lines[0])
                    timestamp = lines[1]
                    # Parse timestamp to seconds
                    start_str, end_str = timestamp.split(' --> ')
                    start_sec = self._srt_time_to_seconds(start_str)
                    end_sec = self._srt_time_to_seconds(end_str)
                    
                    segments.append({
                        'index': index,
                        'start': start_sec,
                        'end': end_sec,
                        'timestamp': timestamp
                    })
                except (ValueError, IndexError):
                    continue
        return segments
    
    def _srt_time_to_seconds(self, time_str: str) -> float:
        """Konvertiert SRT-Zeit zu Sekunden"""
        time_str = time_str.replace(',', '.')
        h, m, s = time_str.split(':')
        return int(h) * 3600 + int(m) * 60 + float(s)
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Konvertiert Sekunden zu SRT-Zeit"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')
    
    def _map_whisper_to_original_timing(self, whisper_segments: List[Dict], 
                                      original_segments: List[Dict]) -> List[Dict]:
        """Mappt Whisper-Transkription auf Original-Timing"""
        mapped_segments = []
        
        for orig_seg in original_segments:
            # Finde alle Whisper-Segmente die in diesem Zeitfenster liegen
            matching_whisper_texts = []
            for whisper_seg in whisper_segments:
                # Overlap-Check: Whisper-Segment überlappt mit Original-Segment
                if (whisper_seg["start"] < orig_seg["end"] and 
                    whisper_seg["end"] > orig_seg["start"]):
                    matching_whisper_texts.append(whisper_seg["text"].strip())
            
            # Kombiniere alle passenden Texte
            combined_text = " ".join(matching_whisper_texts) if matching_whisper_texts else "[Keine Übersetzung]"
            
            mapped_segments.append({
                'index': orig_seg['index'],
                'timestamp': orig_seg['timestamp'],
                'text': combined_text.strip()
            })
            
        return mapped_segments
    
    def _create_translated_srt(self, original_path: str, segments: List[Dict], suffix: str) -> str:
        """Erstellt übersetzte SRT-Datei"""
        name, ext = os.path.splitext(original_path)
        output_path = f"{name}_{suffix}{ext}"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for segment in segments:
                f.write(f"{segment['index']}\n")
                f.write(f"{segment['timestamp']}\n")
                f.write(f"{segment['text']}\n\n")
        
        return output_path


class SubtitleTranslator:
    """Übersetzt SRT-Untertitel zwischen verschiedenen Sprachen"""
    
    def __init__(self):
        self.whisper_translator = None
        
        # Check dependencies
        self.has_translators = TRANSLATORS_AVAILABLE
        self.has_whisper = WHISPER_AVAILABLE
        
        self.supported_languages = {
            'auto': 'Automatisch erkennen',
            'de': 'Deutsch',
            'en': 'Englisch', 
            'fr': 'Französisch',
            'es': 'Spanisch',
            'it': 'Italienisch',
            'pt': 'Portugiesisch',
            'ru': 'Russisch',
            'zh': 'Chinesisch'
        }
        
    def parse_srt(self, srt_path: str) -> List[Dict]:
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
    
    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """Übersetzt einen Text"""
        if source_lang == target_lang:
            return text
            
        try:
            # Google Translate verwenden (kostenlos)
            if source_lang == 'auto':
                translated = ts.translate_text(text, translator='google', to_language=target_lang)
            else:
                translated = ts.translate_text(text, translator='google', 
                                            from_language=source_lang, to_language=target_lang)
            return translated
        except Exception as e:
            print(f"Translation error: {e}")
            return text  # Fallback: Original-Text zurückgeben
    
    def translate_srt(self, input_path: str, source_lang: str, target_lang: str, 
                     method: str = "google", video_path: str = None, 
                     whisper_model: str = "base") -> str:
        """Übersetzt eine SRT-Datei und gibt den Pfad der übersetzten Datei zurück"""
        # OpenAI (LLM) Uebersetzung via smart_translation, falls verfuegbar
        if method in ("openai", "auto") and SMART_TRANSLATION_AVAILABLE:
            try:
                return smart_translate_srt(
                    input_path,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    provider="openai",
                    keep_timing=True,
                )
            except Exception as e:
                print(f"OpenAI-Uebersetzung fehlgeschlagen, Fallback auf Google: {e}")

        if method == "whisper" and self.has_whisper and video_path:
            # Whisper-Übersetzung
            if self.whisper_translator is None:
                self.whisper_translator = WhisperTranslator()
            return self.whisper_translator.translate_via_whisper(
                video_path, input_path, target_lang, whisper_model
            )
        
        elif method == "google" and self.has_translators:
            # Google Translate (bestehende Implementierung)
            return self._translate_srt_google(input_path, source_lang, target_lang)
        
        else:
            raise Exception(f"Übersetzungsmethode '{method}' nicht verfügbar oder Video-Pfad fehlt")
    
    def _translate_srt_google(self, input_path: str, source_lang: str, target_lang: str) -> str:
        """Übersetzt SRT mit Google Translate (ursprüngliche Methode)"""
        segments = self.parse_srt(input_path)
        
        # Übersetzung durchführen
        translated_segments = []
        for segment in segments:
            translated_text = self.translate_text(segment['text'], source_lang, target_lang)
            translated_segments.append({
                'index': segment['index'],
                'timestamp': segment['timestamp'],
                'text': translated_text
            })
        
        # Übersetzte SRT-Datei erstellen
        name, ext = os.path.splitext(input_path)
        output_path = f"{name}_translated{ext}"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for segment in translated_segments:
                f.write(f"{segment['index']}\n")
                f.write(f"{segment['timestamp']}\n")
                f.write(f"{segment['text']}\n\n")
        
        return output_path
    
    def create_dual_srt(self, original_path: str, translated_path: str, 
                       vertical_offset: int = 2) -> str:
        """Erstellt eine SRT-Datei mit Original oben und Übersetzung unten"""
        original_segments = self.parse_srt(original_path)
        translated_segments = self.parse_srt(translated_path)
        
        # Kombinierte SRT erstellen
        name, ext = os.path.splitext(original_path)
        output_path = f"{name}_dual{ext}"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for orig, trans in zip(original_segments, translated_segments):
                f.write(f"{orig['index']}\n")
                f.write(f"{orig['timestamp']}\n")
                # Original oben, Übersetzung unten mit Zeilenabstand
                f.write(f"{orig['text']}\n")
                f.write('\n' * vertical_offset)  # Vertikaler Abstand
                f.write(f"{trans['text']}\n\n")
        
        return output_path


if __name__ == "__main__":
    # Test-Modus
    import sys
    if len(sys.argv) >= 4:
        translator = SubtitleTranslator()
        input_file = sys.argv[1]
        source_lang = sys.argv[2] 
        target_lang = sys.argv[3]
        
        print(f"Übersetze {input_file} von {source_lang} nach {target_lang}...")
        output_file = translator.translate_srt(input_file, source_lang, target_lang)
        print(f"Übersetzung gespeichert: {output_file}")
