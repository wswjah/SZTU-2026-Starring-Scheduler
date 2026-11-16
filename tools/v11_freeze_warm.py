"""Freeze a more expensive comparison before reading either fresh outcome."""
from pathlib import Path
from v11_scan_make import apply
from v11_freeze import freeze

ROOT = Path(__file__).resolve().parent.parent
source = (ROOT / "candidates/v11_combinations/warm_pen075.cpp").read_text(encoding="utf8")
source = apply(source)
path = ROOT / "candidates/v11_final/warm_pen_scan.cpp"
assert not path.exists()
path.write_bytes(source.encode("utf8"))
freeze("v11_warm_pen_scan", path,
       "Warm-aware rack ranking+PEN.75 improved old development80 total0.178pct,40up39down1equal; retain equivalent scanner and8MiB fix. More expensive comparison, frozen before reading either finalist fresh40 profits. Frontier variants negative, not added.")
