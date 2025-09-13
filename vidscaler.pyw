"""
VidScaler - GUI-Anwendung zum Skalieren von Videos mit FFmpeg 
(.pyw Version ohne Konsole - für direkten Doppelklick-Start)
"""

import os
import sys

# Ensure we're in the right directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Add project directory to Python path
sys.path.insert(0, script_dir)

# Import the main vidscaler module and run it
if __name__ == "__main__":
    try:
        # Import here to ensure proper path setup
        import vidscaler
        vidscaler.main()
    except Exception as e:
        import logging
        import traceback
        import tkinter.messagebox
        
        # Setup basic logging to file
        logging.basicConfig(
            filename=os.path.join(script_dir, 'vidscaler_error.log'),
            level=logging.ERROR,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Log the full traceback
        logging.exception("VidScaler startup failed")
        
        # Show user-friendly error dialog
        try:
            tkinter.messagebox.showerror(
                "VidScaler - Fehler",
                f"Fehler beim Starten von VidScaler:\n\n{str(e)}\n\nDetails wurden in 'vidscaler_error.log' gespeichert."
            )
        except Exception:
            # Fallback if tkinter fails
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, 
                f"VidScaler Fehler: {str(e)}\n\nSiehe vidscaler_error.log für Details.",
                "VidScaler - Kritischer Fehler",
                0x10  # MB_ICONERROR
            )
        
        # Exit with error code
        sys.exit(1)