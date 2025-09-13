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
    # Import here to ensure proper path setup
    import vidscaler
    vidscaler.main()