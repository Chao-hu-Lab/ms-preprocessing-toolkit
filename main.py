#!/usr/bin/env python
"""
MS Preprocessing Toolkit - Main Entry Point

Run this file to start the application:
    python main.py          # GUI mode
    python main.py --help   # Show help
"""

import sys
from pathlib import Path

# Add src to path for development
src_path = Path(__file__).parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

from ms_preprocessing.main import main

if __name__ == "__main__":
    sys.exit(main())
