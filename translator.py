"""
Subtitle Translator - Übersetzt SRT-Dateien mit verschiedenen Services
"""

import os
import re
import sys
import subprocess
import tempfile
from typing import List, Dict, Optional, Tuple, TypedDict

# Import debug logger
from debug_logger import debug_logger

class DePreset(TypedDict):
    wrap_width: int
    expansion_factor: float
    min_seg_dur: float
    reading_wpm: int
    min_gap_ms: int

# Auto-mode fallback order helper
def _get_auto_fallback_order() -> List[str]:
    """Return auto mode fallback order from env or default.

    Env vars (first wins):
      - SRT_FALLBACK_ORDER
      - SMART_SRT_FALLBACK_ORDER
    Format: comma-separated, e.g. "openai,google,whisper"
    """
    raw = os.getenv("SRT_FALLBACK_ORDER") or os.getenv("SMART_SRT_FALLBACK_ORDER") or "openai,google,whisper"
    order = [t.strip().lower() for t in raw.split(",") if t.strip()]
    valid = {"openai", "google", "whisper"}
    return [m for m in order if m in valid]

# Language-aware preset for German
def _get_de_preset() -> DePreset:
    """Return DE-friendly preset parameters (can be overridden via env).

    Env overrides:
      - SRT_DE_WRAP (int)
      - SRT_DE_EXPANSION_FACTOR (float)
      - SRT_DE_MIN_SEG_DUR (float seconds)
      - SRT_DE_READING_WPM (int)
      - SRT_DE_MIN_GAP_MS (int)
    """
    def _int(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, str(default)))
        except (ValueError, TypeError):
            return default
    def _float(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, str(default)))
        except (ValueError, TypeError):
            return default

    return {
        "wrap_width": max(100, _int("SRT_DE_WRAP", 120)),
        "expansion_factor": _float("SRT_DE_EXPANSION_FACTOR", 1.35),
        "min_seg_dur": _float("SRT_DE_MIN_SEG_DUR", 2.2),
        "reading_wpm": _int("SRT_DE_READING_WPM", 200),
        "min_gap_ms": _int("SRT_DE_MIN_GAP_MS", 120),
    }

# Windows-spezifische subprocess-Konfiguration um Console-Fenster zu unterdrücken
if sys.platform == "win32":
    SUBPROCESS_FLAGS = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    SUBPROCESS_FLAGS = {}

try:
    import translators as ts
    TRANSLATORS_AVAILABLE = True
except ImportError:
    TRANSLATORS_AVAILABLE = False

# Optional high-quality LLM translation module (OpenAI) - now using smart-srt-translator package
try:
    from smart_srt_translator import translate_srt_smart as smart_translate_srt
    from smart_srt_translator import TranslateOptions
    from smart_srt_translator.env import load_env_vars
    try:
        # Optional: provider import (requires openai extra installed)
        from smart_srt_translator.providers.openai_provider import OpenAITranslator
        OPENAI_PROVIDER_AVAILABLE = True
    except Exception as e:
        OPENAI_PROVIDER_AVAILABLE = False
        debug_logger.error("OpenAI provider import failed", e)
    SMART_TRANSLATION_AVAILABLE = True
    debug_logger.debug("smart-srt-translator imported successfully")
except Exception as e:
    SMART_TRANSLATION_AVAILABLE = False
    OPENAI_PROVIDER_AVAILABLE = False
    debug_logger.error("smart-srt-translator import failed", e)

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
        
        result = subprocess.run(cmd, capture_output=True, text=True, **SUBPROCESS_FLAGS)
        if result.returncode != 0:
            raise Exception(f"FFmpeg Audio-Extraktion fehlgeschlagen: {result.stderr}")
            
        return audio_path
    
    def translate_via_whisper(self, video_path: str, original_srt_path: str, 
                            target_lang: str, model_size: str = "base") -> str:
        """
        Translates video audio to English via Whisper with original SRT timing.
        
        Note: Whisper's translate task can ONLY output English. The target_lang
        parameter must be 'en' or this method will raise an exception.
        """
        # Validate that target language is English
        if target_lang != "en":
            raise Exception(f"Whisper translate task only supports English output, not '{target_lang}'")
        
        try:
            # 1. Audio extrahieren
            audio_path = self.extract_audio_for_whisper(video_path)
            
            # 2. Whisper-Modell laden
            if self.model is None or getattr(self.model, 'model_name', '') != model_size:
                self.model = whisper.load_model(model_size)
                self.model.model_name = model_size
            
            # 3. Original SRT-Timing lesen
            original_segments = self._parse_srt_timing(original_srt_path)
            
            # 4. Whisper-Translation (to English only)
            result = self.model.transcribe(
                audio_path, 
                task="translate",  # Use translate task, not transcribe
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
        # Initialize logging
        debug_logger.test_imports()
        
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
                     whisper_model: str = "base", de_readability_optimization: bool = False) -> str:
        """
                     Translate an SRT file into the target language and return the path to the translated SRT.
                     
                     This function selects a translation backend based on `method` and available optional dependencies:
                     - "openai" or "auto": attempt LLM-based timed translation via smart_srt_translator (if available); on failure falls back to other methods.
                     - "whisper": use Whisper-based transcription-to-translation that maps transcripts back to the original SRT timings (requires `video_path` and Whisper availability). Note: Whisper can only translate TO English ('en'), target_lang will be forced to 'en'.
                     - "google": translate using the translators library.
                     
                     Parameters that require non-obvious context:
                     - method: one of "google", "whisper", "openai", or "auto". Behavior depends on availability flags for optional backends.
                     - video_path: required when method == "whisper"; path to the source video used for transcription.
                     - whisper_model: Whisper model size to load when using the "whisper" method.
                     
                     Returns:
                         str: Path to the generated translated SRT file.
                     
                     Raises:
                         Exception: If the requested method is unavailable, required dependencies are missing, or `video_path` is not provided for Whisper.
                     """
        
        # === DEBUG LOGGING START ===
        debug_logger.step("Starting translate_srt", {
            "input_path": input_path,
            "source_lang": source_lang, 
            "target_lang": target_lang,
            "method": method,
            "video_path": video_path,
            "whisper_model": whisper_model
        })
        
        debug_logger.file_info(input_path, "Input SRT file")
        
        # Parse input SRT to get segment info for debugging
        input_segments: List[Dict] = []
        try:
            input_segments = self.parse_srt(input_path)
            debug_logger.debug("Input SRT analysis", {
                "total_segments": len(input_segments),
                "first_segment": {
                    "index": input_segments[0]['index'] if input_segments else None,
                    "timestamp": input_segments[0]['timestamp'] if input_segments else None,
                    "text_preview": input_segments[0]['text'][:50] + "..." if input_segments and len(input_segments[0]['text']) > 50 else input_segments[0]['text'] if input_segments else None
                },
                "last_segment": {
                    "index": input_segments[-1]['index'] if input_segments else None,
                    "timestamp": input_segments[-1]['timestamp'] if input_segments else None,
                    "text_preview": input_segments[-1]['text'][:50] + "..." if input_segments and len(input_segments[-1]['text']) > 50 else input_segments[-1]['text'] if input_segments else None
                }
            })
        except (OSError, UnicodeError, ValueError) as e:
            debug_logger.error("Failed to parse input SRT for analysis", e)
        
        # Log availability flags
        debug_logger.debug("Availability flags", {
            "SMART_TRANSLATION_AVAILABLE": SMART_TRANSLATION_AVAILABLE,
            "TRANSLATORS_AVAILABLE": TRANSLATORS_AVAILABLE,
            "WHISPER_AVAILABLE": WHISPER_AVAILABLE
        })
        # === DEBUG LOGGING END ===
        
        # AUTO mode with configurable fallback order
        if method == "auto":
            order = _get_auto_fallback_order()
            debug_logger.debug("Auto mode fallback order", {"order": order})
            last_err: Optional[Exception] = None
            for m in order:
                try:
                    if m == "openai" and SMART_TRANSLATION_AVAILABLE:
                        debug_logger.step("Attempting OpenAI Translation", {
                            "function": "smart_translate_srt",
                            "src_lang": source_lang,
                            "tgt_lang": target_lang
                        })
                        try:
                            load_env_vars()
                        except Exception:
                            pass
                        if not OPENAI_PROVIDER_AVAILABLE:
                            raise RuntimeError("OpenAI provider not available (install smart-srt-translator[openai])")
                        provider = OpenAITranslator()
                        debug_logger.debug("Initialized OpenAI provider", {"model": getattr(provider, "model", "?")})
                        # Language-aware defaults for German with optimization choice
                        is_de = (target_lang or "").lower().startswith("de")
                        if is_de and de_readability_optimization:
                            # German EXPANSION mode (experimental, may cause timing drift)
                            de = _get_de_preset()
                            debug_logger.debug("German EXPANSION mode (experimental)", {
                                "de_readability_optimization": True,
                                "expand_timing": True,
                                "expansion_factor": de["expansion_factor"],
                                "min_seg_dur": de["min_seg_dur"],
                                "reading_wpm": de["reading_wpm"],
                                "min_gap_ms": de["min_gap_ms"],
                                "wrap_width": max(100, int(de["wrap_width"])),
                                "balance": False,
                                "smooth": False
                            })
                            result_path = smart_translate_srt(
                                input_path,
                                src_lang=source_lang,
                                tgt_lang=target_lang,
                                provider=provider,
                                expand_timing=True,
                                expansion_factor=de["expansion_factor"],
                                min_segment_duration=de["min_seg_dur"],
                                reading_speed_wpm=de["reading_wpm"],
                                min_gap_ms=de["min_gap_ms"],
                                wrap_width=max(100, int(de["wrap_width"])),
                                balance=False,
                                smooth=False,
                            )
                        elif is_de:
                            # German PRESERVE TIMING mode (default, recommended)
                            de = _get_de_preset()
                            debug_logger.debug("German PRESERVE TIMING mode (default)", {
                                "preserve_timing": True,
                                "wrap_width": max(100, int(de["wrap_width"])),
                                "balance": False,
                                "smooth": False
                            })
                            result_path = smart_translate_srt(
                                input_path,
                                src_lang=source_lang,
                                tgt_lang=target_lang,
                                provider=provider,
                                preserve_timing=True,
                                wrap_width=max(100, int(de["wrap_width"])),
                                balance=False,
                                smooth=False,
                            )
                        else:
                            # Conservative non-DE defaults
                            result_path = smart_translate_srt(
                                input_path,
                                src_lang=source_lang,
                                tgt_lang=target_lang,
                                provider=provider,
                                wrap_width=120,
                                balance=False,
                                smooth=False,
                            )
                        debug_logger.step("OpenAI Translation SUCCESS", {"result_path": result_path})
                        debug_logger.file_info(result_path, "OpenAI translated SRT file")
                        
                        # Parse output SRT to analyze results
                        try:
                            output_segments = self.parse_srt(result_path)
                            debug_logger.debug("Output SRT analysis", {
                                "total_segments": len(output_segments),
                                "segment_count_diff": len(output_segments) - len(input_segments),
                                "first_segment": {
                                    "index": output_segments[0]['index'] if output_segments else None,
                                    "timestamp": output_segments[0]['timestamp'] if output_segments else None,
                                    "text_preview": output_segments[0]['text'][:50] + "..." if output_segments and len(output_segments[0]['text']) > 50 else output_segments[0]['text'] if output_segments else None
                                },
                                "last_segment": {
                                    "index": output_segments[-1]['index'] if output_segments else None,
                                    "timestamp": output_segments[-1]['timestamp'] if output_segments else None,
                                    "text_preview": output_segments[-1]['text'][:50] + "..." if output_segments and len(output_segments[-1]['text']) > 50 else output_segments[-1]['text'] if output_segments else None
                                }
                            })
                            
                            # Timing comparison
                            if input_segments and output_segments:
                                debug_logger.debug("Timing comparison", {
                                    "input_first_timestamp": input_segments[0]['timestamp'],
                                    "output_first_timestamp": output_segments[0]['timestamp'],
                                    "input_last_timestamp": input_segments[-1]['timestamp'],
                                    "output_last_timestamp": output_segments[-1]['timestamp'],
                                    "timestamps_match": (
                                        input_segments[0]['timestamp'] == output_segments[0]['timestamp'] and
                                        input_segments[-1]['timestamp'] == output_segments[-1]['timestamp']
                                    )
                                })
                        except (OSError, UnicodeError, ValueError) as e:
                            debug_logger.error("Failed to analyze output SRT", e)
                        
                        return result_path
                    elif m == "google" and TRANSLATORS_AVAILABLE:
                        debug_logger.step("Attempting Google translators backend", {
                            "src_lang": source_lang,
                            "tgt_lang": target_lang,
                        })
                        return self._translate_srt_google(input_path, source_lang, target_lang)
                    elif m == "whisper" and self.has_whisper and video_path and target_lang == "en":
                        debug_logger.step("Attempting Whisper translate (to English)", {
                            "video_path": video_path,
                            "whisper_model": whisper_model,
                        })
                        if self.whisper_translator is None:
                            self.whisper_translator = WhisperTranslator()
                        return self.whisper_translator.translate_via_whisper(
                            video_path, input_path, "en", whisper_model
                        )
                except Exception as e:
                    last_err = e
                    debug_logger.error(f"AUTO fallback '{m}' failed", e)
                    continue
            if last_err:
                raise last_err
            raise Exception("No available translation method succeeded in AUTO mode")

        # OpenAI (LLM) Uebersetzung via smart-srt-translator, falls verfuegbar
        if method == "openai" and SMART_TRANSLATION_AVAILABLE:
            debug_logger.step("Attempting OpenAI Translation", {
                "function": "smart_translate_srt",
                "src_lang": source_lang,
                "tgt_lang": target_lang
            })
            try:
                # Ensure OPENAI_* env is loaded from .env if present
                try:
                    load_env_vars()
                except Exception:
                    pass

                if not OPENAI_PROVIDER_AVAILABLE:
                    raise RuntimeError("OpenAI provider not available (install smart-srt-translator[openai])")

                provider = OpenAITranslator()
                debug_logger.debug("Initialized OpenAI provider", {"model": getattr(provider, "model", "?")})

                # Call smart pipeline with language-aware defaults and optimization choice
                is_de = (target_lang or "").lower().startswith("de")
                if is_de and de_readability_optimization:
                    # German EXPANSION mode (experimental, may cause timing drift)
                    de = _get_de_preset()
                    debug_logger.debug("German EXPANSION mode (experimental)", {
                        "de_readability_optimization": True,
                        "expand_timing": True,
                        "expansion_factor": de["expansion_factor"],
                        "min_seg_dur": de["min_seg_dur"],
                        "reading_wpm": de["reading_wpm"],
                        "min_gap_ms": de["min_gap_ms"],
                        "wrap_width": max(100, int(de["wrap_width"])),
                        "balance": False,
                        "smooth": False
                    })
                    result_path = smart_translate_srt(
                        input_path,
                        src_lang=source_lang,
                        tgt_lang=target_lang,
                        provider=provider,
                        expand_timing=True,
                        expansion_factor=de["expansion_factor"],
                        min_segment_duration=de["min_seg_dur"],
                        reading_speed_wpm=de["reading_wpm"],
                        min_gap_ms=de["min_gap_ms"],
                        wrap_width=max(100, int(de["wrap_width"])),
                        balance=False,
                        smooth=False,
                    )
                elif is_de:
                    # German PRESERVE TIMING mode (default, recommended)
                    de = _get_de_preset()
                    debug_logger.debug("German PRESERVE TIMING mode (default)", {
                        "preserve_timing": True,
                        "wrap_width": max(100, int(de["wrap_width"])),
                        "balance": False,
                        "smooth": False
                    })
                    result_path = smart_translate_srt(
                        input_path,
                        src_lang=source_lang,
                        tgt_lang=target_lang,
                        provider=provider,
                        preserve_timing=True,
                        wrap_width=max(100, int(de["wrap_width"])),
                        balance=False,
                        smooth=False,
                    )
                else:
                    # Conservative non-DE defaults
                    result_path = smart_translate_srt(
                        input_path,
                        src_lang=source_lang,
                        tgt_lang=target_lang,
                        provider=provider,
                        wrap_width=120,
                        balance=False,
                        smooth=False,
                    )
                debug_logger.step("OpenAI Translation SUCCESS", {"result_path": result_path})
                debug_logger.file_info(result_path, "OpenAI translated SRT file")
                
                # Parse output SRT to analyze results
                try:
                    output_segments = self.parse_srt(result_path)
                    debug_logger.debug("Output SRT analysis", {
                        "total_segments": len(output_segments),
                        "segment_count_diff": len(output_segments) - len(input_segments),
                        "first_segment": {
                            "index": output_segments[0]['index'] if output_segments else None,
                            "timestamp": output_segments[0]['timestamp'] if output_segments else None,
                            "text_preview": output_segments[0]['text'][:50] + "..." if output_segments and len(output_segments[0]['text']) > 50 else output_segments[0]['text'] if output_segments else None
                        },
                        "last_segment": {
                            "index": output_segments[-1]['index'] if output_segments else None,
                            "timestamp": output_segments[-1]['timestamp'] if output_segments else None,
                            "text_preview": output_segments[-1]['text'][:50] + "..." if output_segments and len(output_segments[-1]['text']) > 50 else output_segments[-1]['text'] if output_segments else None
                        }
                    })
                    
                    # Timing comparison
                    if input_segments and output_segments:
                        debug_logger.debug("Timing comparison", {
                            "input_first_timestamp": input_segments[0]['timestamp'],
                            "output_first_timestamp": output_segments[0]['timestamp'],
                            "input_last_timestamp": input_segments[-1]['timestamp'],
                            "output_last_timestamp": output_segments[-1]['timestamp'],
                            "timestamps_match": (
                                input_segments[0]['timestamp'] == output_segments[0]['timestamp'] and
                                input_segments[-1]['timestamp'] == output_segments[-1]['timestamp']
                            )
                        })
                except (OSError, UnicodeError, ValueError) as e:
                    debug_logger.error("Failed to analyze output SRT", e)
                
                return result_path
            except Exception as e:
                debug_logger.error("OpenAI Translation FAILED", e)
                # If user explicitly requested OpenAI, do not silently fall back
                if method == "openai":
                    raise
                # Auto mode: try graceful fallbacks
                # Prefer Google translators backend if available
                if TRANSLATORS_AVAILABLE:
                    debug_logger.step("FALLBACK: Using Google translators backend", {
                        "src_lang": source_lang,
                        "tgt_lang": target_lang,
                    })
                    return self._translate_srt_google(input_path, source_lang, target_lang)
                # If Whisper is available and target is English and video is provided, use Whisper
                if self.has_whisper and video_path and target_lang == "en":
                    debug_logger.step("FALLBACK: Using Whisper translate (to English)", {
                        "video_path": video_path,
                        "whisper_model": whisper_model,
                    })
                    if self.whisper_translator is None:
                        self.whisper_translator = WhisperTranslator()
                    return self.whisper_translator.translate_via_whisper(
                        video_path, input_path, "en", whisper_model
                    )
                # No viable fallback
                raise

        if method == "whisper" and self.has_whisper and video_path:
            # Whisper-Übersetzung (nur nach Englisch möglich)
            if target_lang != "en":
                raise Exception(f"Whisper kann nur nach Englisch ('en') übersetzen, nicht nach '{target_lang}'. Verwende stattdessen 'google' oder 'openai' Methode.")
            if self.whisper_translator is None:
                self.whisper_translator = WhisperTranslator()
            return self.whisper_translator.translate_via_whisper(
                video_path, input_path, "en", whisper_model  # Force target to English
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
        output_file = translator.translate_srt(input_file, source_lang, target_lang, de_readability_optimization=False)
        print(f"Übersetzung gespeichert: {output_file}")
