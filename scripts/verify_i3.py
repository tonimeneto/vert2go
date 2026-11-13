"""Compatibility entry point; historical I3 evidence remains preserved."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main():
    from scripts.verify_i4 import main as verify_current
    print('Verificacao vigente: I5; evidencias historicas I1-I4 preservadas.')
    return verify_current()

if __name__ == '__main__':
    raise SystemExit(main())
