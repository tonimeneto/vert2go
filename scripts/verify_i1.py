"""Historical baseline and compatibility entry point for the current verifier."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
BASELINE={
    'AGENTS.md':'69D4351F033B747645B87CE66CF8D5B552F76628A9EFEF9D552A789BAEE342AE',
    'README.md':'AED7A21F8A13D9C539F4BAE78E92472D591D0123FD05551B68F045992B892EF1',
    'docs/4S_convencao_condominio.md':'F2905F4A28BE0C5674C86E257DDAC70B170F13541F9E90B83A33A328605DAA2D',
    'docs/4S_Regulamento_interno.md':'22EE5C8717BC9D4AD12DE5724B728052CB5E124BDD24F0F219AE550CF8DE4CB7',
    'docs/Alfredo-Especificacao-v018.md':'E34DFF0F13C91EFF2BB910CEA351E8B1E5BB6BE351E61F75C214535D4726DC81',
    'docs/Vert2Go-Plano-Implementacao-Codex-v0.1.1.md':'0260928417EAA2F9E87579CF3FEF1D3B962D123D00E449003F29D2A7AA97CF8E',
    'docs/Vert2Go-PRD-v1.2.0.md':'63583209E7F73A920B485334F7608D48A851AAF1C082DB224DF0E3D322F898DF',
}


class EvidenceResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.passed=[]
    def addSuccess(self,test):
        super().addSuccess(test)
        self.passed.append(test.id())


def main():
    """Compatibility entry point; I1 delivery evidence remains historical."""
    from scripts.verify_i2 import main as verify_current
    print('Verificação vigente: I4; evidências históricas I1/I2/I3 preservadas.')
    return verify_current()


if __name__ == '__main__':
    raise SystemExit(main())
