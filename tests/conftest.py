import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
# Local development: use the sibling option-implied-density checkout if it is not installed.
sib = ROOT.parent / "option-implied-density" / "src"
if sib.exists():
    sys.path.insert(0, str(sib))
