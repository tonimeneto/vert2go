"""Windows shortcut entry point; uses pythonw, not VS Code."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from app.desktop.panel import main

if __name__ == '__main__':
    raise SystemExit(main())
