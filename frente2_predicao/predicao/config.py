import os
from pathlib import Path


RAIZ = Path(__file__).resolve().parent.parent

PASTA_MODELO = Path(os.environ.get("DEFECTLENS_MODELO", RAIZ / "modelo"))
ARQUIVO_MANIFESTO = PASTA_MODELO / "manifesto.json"
PASTA_CLONES = Path(os.environ.get("DEFECTLENS_CLONES", RAIZ / "clones"))

JANELAS_DIAS = (30, 90, 180, 365)

PASTAS_FORA_DO_ESCOPO = ("test", "tests", "testing", "docs", "doc", "examples", "benchmarks",
                         "profiling", "vendor", "_vendor", "vendored", "patched", "third_party")
ARQUIVOS_FORA_DO_ESCOPO = ("setup.py", "conftest.py", "_version.py", "versioneer.py")

TAMANHO_MAXIMO_REPO_KB = int(os.environ.get("DEFECTLENS_MAX_KB", 400_000))
SEGUNDOS_MAXIMOS_CLONE = int(os.environ.get("DEFECTLENS_MAX_CLONE_S", 600))
MAXIMO_ARQUIVOS_NA_RESPOSTA = 3000
