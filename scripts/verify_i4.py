"""Compatibility entry point; preserves historical I4 evidence."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    from scripts.verify_i5 import main as verify_current
    print('Verifica??o vigente: I5; evid?ncias hist?ricas I1?I4 preservadas.')
    return verify_current()

if __name__ == '__main__':
    raise SystemExit(main())
