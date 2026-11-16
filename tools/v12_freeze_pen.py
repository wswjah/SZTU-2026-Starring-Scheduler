"""Freeze the predeclared gentler routing coefficient selected on old worlds."""
from pathlib import Path
import re
from v11_scan_make import apply
from v11_freeze import freeze

ROOT = Path(__file__).resolve().parent.parent
source = (ROOT / "versions/v10_input_fix/main.cpp").read_text(encoding="utf8")
source = apply(source)
source, count = re.subn(r"PRM\(PEN,\s*[^)]+\)", "PRM(PEN, 0.875)", source)
assert count == 1
path = ROOT / "candidates/v12_final/pen0875_scan.cpp"
path.parent.mkdir(parents=True, exist_ok=True)
assert not path.exists()
path.write_bytes(source.encode("utf8"))
freeze("v12_pen0875_scan", path,
       "Fixed12-axis coarse search;PEN.875 selected after oldV8development80 aggregate+0.277pct,39up39down2equal,worst-10.30pct. Scanner and8MiB fix retained. No V12candidate fresh outcomes used.",
       "cases/v12_holdout/manifest.json")
