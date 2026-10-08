"""Write FROZEN_MANIFEST_3.json: SHA-256 of protocol 3 and every file that runs
or analyses the robust confirmatory study. Commit the protocol and this manifest
together, publicly, before running the study."""
import hashlib
import json
from pathlib import Path

from confirm_analysis_robust import MANIFEST_FILES

root = Path(__file__).resolve().parents[1]
manifest = {rel: hashlib.sha256((root / rel).read_bytes()).hexdigest() for rel in MANIFEST_FILES}
(root / "FROZEN_MANIFEST_3.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
