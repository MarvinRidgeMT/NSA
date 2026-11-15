#!/usr/bin/env bash
set -euo pipefail

repro_root="$(cd "$(dirname "$0")/.." && pwd)"
repro_python="$repro_root/.venv/bin/python"
repro_committed="$repro_root/data/bundles/site04_roi3_2026-11-14_14d_mast1m.json"
repro_tmp="$(mktemp -d /tmp/polaris-repro-hash.XXXXXX)"
repro_generated="$repro_tmp/site04_roi3_2026-11-14_14d_mast1m.json"
trap 'rm -rf "$repro_tmp"' EXIT

if [[ ! -x "$repro_python" ]]; then
  echo "missing science environment: $repro_python" >&2
  exit 2
fi
if [[ ! -f "$repro_committed" ]]; then
  echo "missing committed reference: $repro_committed" >&2
  exit 2
fi

cd "$repro_root"
echo "Regenerating Site04 ROI3, 1 m mast, 14–28 Nov 2026 into $repro_generated"
"$repro_python" - "$repro_generated" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

from science import bundle
from science import horizons

output = Path(sys.argv[1])
manifest = {item["path"]: item for item in json.loads((horizons.RAW_DIR / "MANIFEST.json").read_text())}


def archived_fetch(params, tag, raw_dir=horizons.RAW_DIR, retries=0):
    del retries
    path = Path(raw_dir) / f"{tag}.txt"
    relative = path.relative_to(horizons.ROOT).as_posix()
    if relative not in manifest or not path.is_file():
        raise FileNotFoundError(f"archived Horizons response missing: {relative}")
    expected_params = {key: value for key, value in params.items() if key != "TLIST"}
    if "TLIST" in params:
        expected_params["TLIST_count"] = params["TLIST"].count("'") // 2
    if manifest[relative]["params"] != expected_params:
        raise ValueError(f"archived Horizons query does not match requested parameters: {relative}")
    body = path.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    if digest != manifest[relative]["sha256"]:
        raise ValueError(f"archived Horizons hash mismatch: {relative}")
    return body.decode("utf-8"), digest, relative


horizons.fetch = archived_fetch
bundle.main(
    [
        "--site", "site04_roi3",
        "--start", "2026-11-14 00:00",
        "--days", "14",
        "--step-h", "1",
        "--mast", "1",
        "--out", str(output),
    ]
)
PY

"$repro_python" - "$repro_generated" "$repro_committed" <<'PY'
import copy
import hashlib
import json
import sys
from pathlib import Path

generated_path = Path(sys.argv[1])
committed_path = Path(sys.argv[2])


def canonical_bytes(path: Path) -> bytes:
    value = copy.deepcopy(json.loads(path.read_text()))
    value.pop("generated_utc", None)
    generator = value.get("generator", {})
    generator.pop("git_commit", None)
    generator.pop("command", None)
    value.pop("derived", None)
    for layer in value.get("skyline", {}).get("dem_layers", []):
        layer.pop("transport", None)
    def normalize(item):
        if isinstance(item, dict):
            return {key: normalize(child) for key, child in item.items()}
        if isinstance(item, list):
            return [normalize(child) for child in item]
        if isinstance(item, float):
            return round(item, 12)
        return item
    value = normalize(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


generated = canonical_bytes(generated_path)
committed = canonical_bytes(committed_path)
generated_hash = hashlib.sha256(generated).hexdigest()
committed_hash = hashlib.sha256(committed).hexdigest()

print("Canonicalization: UTF-8 JSON, sorted keys, compact separators, floats normalized to 12 decimal places")
print("Excluded volatile fields: generated_utc, generator.git_commit, generator.command")
print("Excluded environment-only field: skyline.dem_layers[*].transport")
print("Excluded extension scope: derived (A1–A4 and stretch blocks are separate post-build steps)")
print("Hostname fields: none present")
print(f"generated canonical SHA-256: {generated_hash}")
print(f"committed canonical SHA-256: {committed_hash}")
if generated_hash != committed_hash:
    print("REPRO_HASH_MISMATCH", file=sys.stderr)
    raise SystemExit(1)
print("REPRO_HASH_MATCH")
PY
