"""Merge a downloaded cumulative backup without overwriting frozen snapshots."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screener.tracking import read_archives  # noqa: E402


def restore(source, destination):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("Download the archive to a separate directory first")
    incoming = read_archives(source)
    existing = {record["id"]: record for record in read_archives(destination)}
    if not incoming:
        raise ValueError("The backup contains no validated snapshots")
    for record in incoming:
        if not re.fullmatch(r"[0-9a-f]{24}", record["id"]):
            raise ValueError("Invalid immutable snapshot ID")
        if record["id"] in existing and record != existing[record["id"]]:
            raise ValueError(f"Conflicting immutable snapshot: {record['id']}")
    target = destination / "snapshots"
    target.mkdir(parents=True, exist_ok=True)
    for record in incoming:
        if record["id"] in existing:
            continue
        original = source / "snapshots" / f"{record['id']}.json"
        with (target / original.name).open("xb") as output:
            output.write(original.read_bytes())
    # Price caches and request rotation state are derived, replaceable files.
    derived = list((source / "prices").glob("*.json"))
    if (source / "fetch_attempts.json").exists():
        derived.append(source / "fetch_attempts.json")
    for file in derived:
        json.loads(file.read_text(encoding="utf-8"))
        path = destination / file.relative_to(source)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, path)
    return len(read_archives(destination))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    print("Restored validated snapshots:", restore(args.source, args.destination))
