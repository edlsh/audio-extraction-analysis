#!/usr/bin/env python3
"""Quick script to test the TUI launch."""

import sys
from src.cli import main

# Override sys.argv to simulate running "audio-extraction-analysis tui"
sys.argv = ["audio-extraction-analysis", "tui"]

# Run the main CLI function
sys.exit(main())
