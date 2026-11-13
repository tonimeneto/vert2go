"""Windows shortcut entry point; uses pythonw, not VS Code."""
from pathlib import Path
import sys
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from app.desktop.panel import main as panel_main

def main(argv=None):
    parser=argparse.ArgumentParser(description='Controle local do Alfredo')
    parser.add_argument('--start',action='store_true',help='Solicitação manual de abrir e ligar o controle existente')
    args=parser.parse_args(argv)
    return panel_main(start=args.start)

if __name__ == '__main__':
    raise SystemExit(main())
