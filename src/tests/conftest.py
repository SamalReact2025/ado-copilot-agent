"""pytest configuration — ensure src/ is on sys.path."""

import sys
from pathlib import Path

# Make all src packages importable without installation
sys.path.insert(0, str(Path(__file__).parent.parent))
