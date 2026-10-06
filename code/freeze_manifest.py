"""Write FROZEN_MANIFEST.json: SHA-256 of the protocol and every file that
runs or analyses the confirmatory study. Commit the protocol and this manifest
together, publicly, before running the study. confirm_analysis.py refuses
confirmatory mode if any listed file has changed since."""
import hashlib, json
from pathlib import Path
from confirm_analysis import MANIFEST_FILES

root = Path(__file__).resolve().parents[1]
manifest = {rel: hashlib.sha256((root / rel).read_bytes()).hexdigest() for rel in MANIFEST_FILES}
(root / "FROZEN_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
