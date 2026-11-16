"""Pack without renaming and retain the upstream attribution in the submission."""
from pathlib import Path
import hashlib
import json
from make_attributed96 import ATTRIBUTION, OUT
from pack_submission import pack, lex, significant, splice_lines

source = (OUT / "main.cpp").read_text(encoding="utf8")
packed = ATTRIBUTION + pack(source)
assert significant(lex(splice_lines(source))) == significant(lex(packed))
raw = packed.encode("ascii")
assert len(raw) <= 64000 and b"\r" not in raw
(OUT / "submit.cpp").write_bytes(raw)
manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf8"))
manifest["packed_source"] = {
    "path": str(OUT / "submit.cpp"), "bytes": len(raw),
    "sha256": hashlib.sha256(raw).hexdigest(), "ascii": True,
    "lf_only": True, "tokens_verified": True, "attribution_comment_preserved": True}
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
print(json.dumps(manifest["packed_source"]))
