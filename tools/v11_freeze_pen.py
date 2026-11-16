"""Freeze the prior-development-positive parameter with the verified scanner."""
from pathlib import Path
import re
from v11_scan_make import apply
from v11_freeze import freeze

ROOT = Path(__file__).resolve().parent.parent
source = (ROOT / "versions/v10_input_fix/main.cpp").read_text(encoding="utf8")
source = apply(source)
source, count = re.subn(r"PRM\(PEN,\s*[^)]+\)", "PRM(PEN, 0.75)", source)
assert count == 1
path = ROOT / "candidates/v11_final/pen_scan.cpp"
path.parent.mkdir(parents=True, exist_ok=True)
assert not path.exists()
path.write_bytes(source.encode("utf8"))
freeze("v11_pen_scan", path,
       "PEN.75 alone improved old development80 total0.212pct/41up38down1equal; buffer8MiB and output-equivalent direct integer scanner retained. Frozen before its fresh40 outcomes; heavier alternatives not yet selected.")
