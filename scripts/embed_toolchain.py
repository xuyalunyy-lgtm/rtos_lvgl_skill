"""Embed a verified portable toolchain ZIP into the full Skill payload."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--platform", default="win-x64")
    parser.add_argument("--manifest", type=Path, default=ROOT / "runtime" / "toolchain" / "manifest.json")
    args = parser.parse_args()

    archive = args.archive.resolve()
    manifest_path = args.manifest.resolve()
    if not archive.is_file():
        raise SystemExit(f"archive not found: {archive}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = manifest.get("platforms", {}).get(args.platform)
    if not isinstance(entry, dict):
        raise SystemExit(f"platform not found in manifest: {args.platform}")
    if archive.name != entry.get("archive"):
        raise SystemExit(f"archive name must be {entry.get('archive')!r}")

    relative = Path("assets") / "toolchains" / args.platform / archive.name
    destination = ROOT / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        shutil.copyfile(archive, temporary)
        checksum = sha256_file(temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)

    sidecar = destination.with_name(destination.name + ".sha256")
    sidecar.write_text(f"{checksum} {destination.name}\n", encoding="ascii", newline="\n")
    entry["bundled_archive"] = relative.as_posix()
    entry["archive_sha256"] = checksum
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"archive": str(destination), "sha256": checksum}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
