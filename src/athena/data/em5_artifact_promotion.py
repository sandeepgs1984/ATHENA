"""EM-5: promotes the approved EM-4B/EM-4D/EM-3 research artifacts into
a committed, versioned, read-only location EM-5's live path depends on.

`artifacts/research/` is git-ignored research scratch space -- not
appropriate for a live system to depend on directly (nothing guarantees
it survives a clean checkout or isn't silently regenerated). This
script never re-serializes, re-formats, or otherwise touches the
content of any source artifact -- Blocker 3's constraint (EM-4B/EM-4D/
EM-3 source artifacts remain byte-for-byte immutable) is structural
here: every promoted file is `shutil.copyfile`-identical to its source,
verified by an explicit SHA256 equality check, not assumed.

Promotion is versioned (`config/emr/frozen_models/v{N}/`) -- a future
re-promotion (a new EM-4 cycle) is a new directory, never an in-place
overwrite, so an EM-5 run's `frozen_model_version` stays replayable
against the exact artifacts it used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

EM5_FROZEN_MODEL_MANIFEST_VERSION = "em5-frozen-model-manifest-v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _promote_directory(
    source_dir: Path, dest_dir: Path, *, filenames: tuple[str, ...] | None = None,
) -> dict[str, str]:
    """Copies files from `source_dir` byte-identically into `dest_dir`,
    verifying each copy's hash against the source. `filenames` restricts
    which files to promote (only what live inference actually reads --
    e.g. EM-3's five purely-descriptive analysis reports are never
    consumed by any inference code and are deliberately excluded, not
    committed as multi-megabyte dead weight); `None` promotes every
    `*.json` file in the directory. Returns {relative_filename: sha256}."""

    dest_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    sources = (
        sorted(source_dir.glob("*.json")) if filenames is None
        else [source_dir / name for name in filenames]
    )
    for source_path in sources:
        if not source_path.is_file():
            raise RuntimeError(f"expected source artifact not found: {source_path}")
        dest_path = dest_dir / source_path.name
        source_hash = _sha256(source_path)
        shutil.copyfile(source_path, dest_path)
        dest_hash = _sha256(dest_path)
        if dest_hash != source_hash:
            raise RuntimeError(
                f"promotion verification failed for {source_path.name}: "
                f"source sha256={source_hash} != promoted-copy sha256={dest_hash}"
            )
        hashes[source_path.name] = source_hash
    return hashes


def promote(*, research_root: Path, config_dir: Path, version: str) -> dict:
    dest_root = config_dir / "emr" / "frozen_models" / version
    if dest_root.exists() and any(dest_root.iterdir()):
        raise RuntimeError(
            f"{dest_root} already exists and is non-empty -- promotion is versioned, "
            f"never an in-place overwrite; use a new version directory"
        )

    manifest = {
        "contract_version": EM5_FROZEN_MODEL_MANIFEST_VERSION,
        "version": version,
        "sources": {},
    }
    # em4b/em4d: every file (all 18 combos + SUMMARY.json) -- all small,
    # all genuinely consumed by live inference (coefficients/preprocessing/
    # calibration). em3: ONLY the register + manifest EM-4A's deterministic
    # score actually reads -- the other 4 EM-3 files (B/C/D/E) are purely
    # descriptive analysis reports, tens of megabytes combined, never
    # imported by any inference code.
    components = (
        ("em4b", "em4b", None),
        ("em4d", "em4d", None),
        ("em3", "em3", ("F_exploratory_candidate_register.json", "manifest.json")),
    )
    for component, subdir, filenames in components:
        source_dir = research_root / subdir
        dest_dir = dest_root / component
        hashes = _promote_directory(source_dir, dest_dir, filenames=filenames)
        manifest["sources"][component] = {
            "source_dir": str(source_dir), "file_count": len(hashes), "sha256": hashes,
        }

    content_for_fingerprint = {k: v for k, v in manifest.items()}
    fingerprint = hashlib.sha256(
        json.dumps(content_for_fingerprint, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest["manifest_id"] = f"em5-frozen-models-{version}-{fingerprint}"

    (dest_root / "FROZEN_MODEL_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote approved EM-4B/EM-4D/EM-3 artifacts for EM-5 live use.")
    parser.add_argument("--research-root", type=Path, default=Path("artifacts/research"))
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--version", type=str, default="v1")
    args = parser.parse_args()

    manifest = promote(research_root=args.research_root, config_dir=args.config_dir, version=args.version)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
