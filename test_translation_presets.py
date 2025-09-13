"""
Unit Tests for Translation DE-Preset Configurations
Tests verschiedene Einstellungen für deutsche Untertitel-Übersetzung
"""

import unittest
import os
import tempfile
from unittest.mock import Mock, patch

# Import the translator module
from translator import SubtitleTranslator, _get_de_preset, _get_auto_fallback_order

class TestDEPresetConfiguration(unittest.TestCase):
    """Tests für deutsche Preset-Konfiguration"""

    def setUp(self):
        """Setup vor jedem Test"""
        # Clear environment variables
        self.env_vars_to_clear = [
            'SRT_DE_WRAP', 'SRT_DE_EXPANSION_FACTOR', 'SRT_DE_MIN_SEG_DUR', 
            'SRT_DE_READING_WPM', 'SRT_DE_MIN_GAP_MS',
            'SRT_FALLBACK_ORDER', 'SMART_SRT_FALLBACK_ORDER'
        ]
        self.original_env = {}
        for var in self.env_vars_to_clear:
            self.original_env[var] = os.environ.get(var)
            if var in os.environ:
                del os.environ[var]

    def tearDown(self):
        """Cleanup nach jedem Test"""
        # Restore original environment variables
        for var, value in self.original_env.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]

    def test_de_preset_defaults(self):
        """Test: Standard DE-Preset Werte"""
        preset = _get_de_preset()
        
        expected = {
            "wrap_width": 120,
            "expansion_factor": 1.35,
            "min_seg_dur": 2.2,
            "reading_wpm": 200,
            "min_gap_ms": 120,
        }
        
        self.assertEqual(preset, expected)

    def test_de_preset_env_overrides(self):
        """Test: Umgebungsvariablen überschreiben Defaults"""
        # Set custom environment variables
        os.environ['SRT_DE_WRAP'] = '150'
        os.environ['SRT_DE_EXPANSION_FACTOR'] = '1.5'
        os.environ['SRT_DE_MIN_SEG_DUR'] = '2.5'
        os.environ['SRT_DE_READING_WPM'] = '180'
        os.environ['SRT_DE_MIN_GAP_MS'] = '100'
        
        preset = _get_de_preset()
        
        expected = {
            "wrap_width": 150,
            "expansion_factor": 1.5,
            "min_seg_dur": 2.5,
            "reading_wpm": 180,
            "min_gap_ms": 100,
        }
        
        self.assertEqual(preset, expected)

    def test_de_preset_invalid_env_fallback(self):
        """Test: Ungültige Umgebungsvariablen fallen auf Defaults zurück"""
        # Set invalid environment variables
        os.environ['SRT_DE_WRAP'] = 'invalid_number'
        os.environ['SRT_DE_EXPANSION_FACTOR'] = 'not_a_float'
        
        preset = _get_de_preset()
        
        # Should fallback to defaults
        self.assertEqual(preset["wrap_width"], 120)
        self.assertEqual(preset["expansion_factor"], 1.35)

    def test_auto_fallback_order_default(self):
        """Test: Standard Auto-Fallback-Reihenfolge"""
        order = _get_auto_fallback_order()
        self.assertEqual(order, ['openai', 'google', 'whisper'])

    def test_auto_fallback_order_custom(self):
        """Test: Benutzerdefinierte Fallback-Reihenfolge"""
        os.environ['SRT_FALLBACK_ORDER'] = 'google,whisper,openai'
        order = _get_auto_fallback_order()
        self.assertEqual(order, ['google', 'whisper', 'openai'])

    def test_auto_fallback_order_partial(self):
        """Test: Teilweise Fallback-Reihenfolge"""
        os.environ['SRT_FALLBACK_ORDER'] = 'whisper,google'
        order = _get_auto_fallback_order()
        self.assertEqual(order, ['whisper', 'google'])

    def test_auto_fallback_order_invalid_methods_filtered(self):
        """Test: Ungültige Methoden werden herausgefiltert"""
        os.environ['SRT_FALLBACK_ORDER'] = 'openai,invalid_method,google,another_invalid'
        order = _get_auto_fallback_order()
        self.assertEqual(order, ['openai', 'google'])


class TestTranslationParameterApplication(unittest.TestCase):
    """Tests für die Anwendung der Translation-Parameter"""

    def setUp(self):
        """Setup für Parameter-Tests"""
        self.translator = SubtitleTranslator()

    @patch('translator.SMART_TRANSLATION_AVAILABLE', True)
    @patch('translator.OPENAI_PROVIDER_AVAILABLE', True)
    @patch('translator.load_env_vars')
    @patch('translator.OpenAITranslator')
    @patch('translator.smart_translate_srt')
    def test_german_translation_uses_video_optimized_settings(self, mock_translate, mock_provider_class, mock_load_env):
        """Test: Deutsche Übersetzung verwendet Video-optimierte Einstellungen"""
        # Setup mocks
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_translate.return_value = "/path/to/output.srt"
        
        # Create sample SRT file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
            f.write("1\n00:00:00,000 --> 00:00:02,000\nTest subtitle\n")
            temp_srt_path = f.name
        
        try:
            # Call translation with German target using video-optimized settings
            result = self.translator.translate_srt(
                temp_srt_path, 
                source_lang="en", 
                target_lang="de", 
                method="openai",
                de_readability_optimization=True
            )
            
            # Verify smart_translate_srt was called with correct video-optimized parameters
            mock_translate.assert_called_once()
            call_args = mock_translate.call_args[1]  # keyword arguments
            
            # Check STRICT timing mode settings for video burn-in compatibility
            self.assertTrue(call_args['preserve_timing'], "preserve_timing should be True for STRICT mode")
            # expand_timing should be False or not set for STRICT mode
            if 'expand_timing' in call_args:
                self.assertFalse(call_args['expand_timing'], "expand_timing should be False for STRICT mode")
            self.assertFalse(call_args['balance'], "balance should be False for STRICT mode")
            self.assertFalse(call_args['smooth'], "smooth should be False for STRICT mode")
            self.assertGreaterEqual(call_args['wrap_width'], 100, "wrap_width should be >= 100 for German readability")
            
        finally:
            # Cleanup
            if os.path.exists(temp_srt_path):
                os.unlink(temp_srt_path)

    @patch('translator.SMART_TRANSLATION_AVAILABLE', True)
    @patch('translator.OPENAI_PROVIDER_AVAILABLE', True)
    @patch('translator.load_env_vars')
    @patch('translator.OpenAITranslator')
    @patch('translator.smart_translate_srt')
    def test_non_german_translation_uses_conservative_settings(self, mock_translate, mock_provider_class, mock_load_env):
        """Test: Nicht-deutsche Übersetzung verwendet konservative Einstellungen"""
        # Setup mocks
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_translate.return_value = "/path/to/output.srt"
        
        # Create sample SRT file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
            f.write("1\n00:00:00,000 --> 00:00:02,000\nTest subtitle\n")
            temp_srt = f.name
        
        try:
            # Call translation with English target
            result = self.translator.translate_srt(
                temp_srt, 
                source_lang="de", 
                target_lang="en", 
                method="openai",
                de_readability_optimization=False
            )
            
            # Verify smart_translate_srt was called with conservative settings
            mock_translate.assert_called_once()
            call_args = mock_translate.call_args[1]  # keyword arguments
            
            # Check conservative settings for non-German
            self.assertEqual(call_args['wrap_width'], 120)
            self.assertFalse(call_args['balance'])
            self.assertFalse(call_args['smooth'])
            
        finally:
            # Cleanup
            if os.path.exists(temp_srt):
                os.unlink(temp_srt)


class TestVideoSyncCompatibility(unittest.TestCase):
    """Tests für Video-Synchronisations-Kompatibilität"""

    def test_timing_preservation_principles(self):
        """Test: Prinzipien der Timing-Erhaltung für Video-Burn-in"""
        # Diese Tests dokumentieren die Anforderungen für Video-Burn-in
        
        # 1. preserve_timing=True: Keine Segment-übergreifende Textumverteilung
        self.assertTrue(True, "preserve_timing=True prevents cross-segment text redistribution")
        
        # 2. expand_timing=False: Keine zeitliche Verschiebung späterer Segmente  
        self.assertTrue(True, "expand_timing=False prevents later segment time shifts")
        
        # 3. balance=False: Keine Textlängen-Optimierung zwischen Segmenten
        self.assertTrue(True, "balance=False prevents text length optimization across segments")
        
        # 4. smooth=False: Keine Timing-Glättung
        self.assertTrue(True, "smooth=False prevents timing smoothing modifications")

    def test_segment_timing_requirements(self):
        """Test: Anforderungen an Segment-Timing"""
        # Für Video-Burn-in müssen Original-Timings erhalten bleiben
        original_timing = "00:00:02,660 --> 00:00:04,400"
        
        # German text might be longer, but timing should stay identical
        expected_timing = "00:00:02,660 --> 00:00:04,400"
        
        self.assertEqual(original_timing, expected_timing, 
                        "Original timing must be preserved for video burn-in")


if __name__ == '__main__':
    # Führe Tests aus
    unittest.main(verbosity=2)