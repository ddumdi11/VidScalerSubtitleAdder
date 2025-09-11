"""
Debug Logger - Comprehensive logging system for VidScaler translation pipeline
"""

import logging
import os
import tempfile
import datetime
from pathlib import Path
from typing import Any, Dict, Optional

class TranslationDebugLogger:
    """Dedicated logger for translation debugging"""
    
    def __init__(self):
        # Create log directory in temp folder
        self.log_dir = Path(tempfile.gettempdir()) / "VidScaler_Debug"
        self.log_dir.mkdir(exist_ok=True)
        
        # Create timestamped log file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"translation_debug_{timestamp}.log"
        
        # Setup logger
        self.logger = logging.getLogger("TranslationDebug")
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # File handler
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler (for immediate feedback)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Log initialization
        self.logger.info("="*60)
        self.logger.info(f"VidScaler Translation Debug Log - {timestamp}")
        self.logger.info(f"Log file: {self.log_file}")
        self.logger.info("="*60)
    
    def step(self, step_name: str, details: Dict[str, Any] = None):
        """Log a major step in the translation process"""
        self.logger.info(f"STEP: {step_name}")
        if details:
            for key, value in details.items():
                self.logger.info(f"  {key}: {value}")
    
    def debug(self, message: str, data: Any = None):
        """Log debug information"""
        self.logger.debug(f"DEBUG: {message}")
        if data is not None:
            self.logger.debug(f"  Data: {data}")
    
    def error(self, message: str, exception: Exception = None):
        """Log error information"""
        self.logger.error(f"ERROR: {message}")
        if exception:
            self.logger.error(f"  Exception: {exception}")
            self.logger.error(f"  Type: {type(exception).__name__}")
    
    def file_info(self, file_path: str, description: str = ""):
        """Log file information"""
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            self.logger.info(f"FILE: {description} - {file_path}")
            self.logger.info(f"  Size: {size} bytes")
            
            # Sample content for SRT files
            if file_path.endswith('.srt'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')[:10]  # First 10 lines
                        self.logger.info(f"  Sample content:")
                        for i, line in enumerate(lines, 1):
                            if line.strip():
                                self.logger.info(f"    {i}: {line[:100]}...")
                except Exception as e:
                    self.logger.error(f"  Could not read file: {e}")
        else:
            self.logger.error(f"FILE NOT FOUND: {description} - {file_path}")
    
    def test_imports(self):
        """Test and log all translation-related imports"""
        self.step("Testing Translation Dependencies")
        
        # Test smart-srt-translator
        try:
            from smart_srt_translator import translate_srt_smart
            self.logger.info("✅ smart-srt-translator: Available")
            self.logger.info(f"  Function: {translate_srt_smart}")
            
            # Test function signature
            import inspect
            sig = inspect.signature(translate_srt_smart)
            self.logger.info(f"  Signature: {sig}")
            
        except Exception as e:
            self.logger.error("❌ smart-srt-translator: Failed")
            self.error("smart-srt-translator import failed", e)
        
        # Test other dependencies
        try:
            import translators as ts
            self.logger.info("✅ translators: Available")
        except Exception as e:
            self.logger.error("❌ translators: Failed")
            self.error("translators import failed", e)
        
        try:
            import whisper
            self.logger.info("✅ whisper: Available")
        except Exception as e:
            self.logger.error("❌ whisper: Failed")
            self.error("whisper import failed", e)
    
    def get_log_path(self) -> str:
        """Return the path to the log file"""
        return str(self.log_file)

# Global logger instance
debug_logger = TranslationDebugLogger()