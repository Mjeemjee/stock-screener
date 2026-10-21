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
    # Laboratory definitions, decisions and immutable paired runs are cumulative too.
    if (source / "lab/state.json").exists():
        from screener.research_lab import load_state
        incoming_state = load_state(source)
        if (destination / "lab/state.json").exists():
            current_state = load_state(destination)
            incoming_trials = {trial["id"]: trial for trial in incoming_state["trials"]}
            if (not {trial["id"] for trial in current_state["trials"]} <= incoming_trials.keys()
                    or any(incoming_trials.get(trial["id"], {}).get("definition_hash") != trial["definition_hash"]
                           for trial in current_state["trials"])
                    or incoming_state["events"][:len(current_state["events"])] != current_state["events"]
                    or any(incoming_state["processed_sources"].get(key) != value
                           for key, value in current_state["processed_sources"].items())):
                raise ValueError("Lab backup would roll back the trial budget or decision history")
        read_archives(source / "lab")
        for file in sorted((source / "lab").rglob("*.json")):
            if file.is_symlink():
                raise ValueError("Lab backup symlinks are not accepted")
            path = destination / file.relative_to(source)
            path.parent.mkdir(parents=True, exist_ok=True)
            if file.parent.name in ("snapshots", "evidence") and path.exists():
                if json.loads(file.read_text(encoding="utf-8")) != json.loads(path.read_text(encoding="utf-8")):
                    raise ValueError("Conflicting immutable lab snapshot")
                continue
            shutil.copy2(file, path)
    if (source / "research/state.json").exists():
        from screener.factor_research import load_state, read_sealed
        incoming_state = load_state(source)
        if (destination / "research/state.json").exists():
            current = load_state(destination)
            by_id = {p["id"]: p for p in incoming_state["programs"]}
            if (any(by_id.get(p["id"], {}).get("definition_hash") != p["definition_hash"] for p in current["programs"])
                    or incoming_state["events"][:len(current["events"])] != current["events"]
                    or incoming_state["searches"][:len(current["searches"])] != current["searches"]
                    or any(incoming_state["inputs"].get(k) != v for k, v in current["inputs"].items())
                    or any(incoming_state["universes"].get(k) != v for k, v in current["universes"].items())):
                raise ValueError("Research backup would roll back or redefine the study")
        read_archives(source / "research/runs")
        for file in (destination / "research/ai_requests").glob("*.json"):
            if not (source / file.relative_to(destination)).exists():
                raise ValueError("Research backup would roll back model request budget")
        files = sorted((source / "research").rglob("*.json"))
        for file in files:
            if file.is_symlink():
                raise ValueError("Research backup symlinks are not accepted")
            path = destination / file.relative_to(source)
            if file.parent.name not in ("research", "prices", "snapshots"):
                read_sealed(file)
            if file.parent.name not in ("research", "prices") and path.exists():
                if json.loads(file.read_text(encoding="utf-8")) != json.loads(path.read_text(encoding="utf-8")):
                    raise ValueError("Conflicting immutable research evidence")
        for file in files:
            path = destination / file.relative_to(source)
            if path.exists() and file.parent.name not in ("research", "prices"):
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, path)
    long_source, long_target = source / 'long_study', destination / 'long_study'
    if (long_target / 'definition.json').exists() and not (long_source / 'definition.json').exists():
        raise ValueError('Backup would remove the long-horizon study')
    if (long_source / 'definition.json').exists():
        from screener.factor_research import read_sealed
        read_sealed(long_source / 'definition.json')
        read_archives(long_source)
        for existing_file in long_target.rglob('*.json'):
            if existing_file.parent.name != 'prices' and not (long_source / existing_file.relative_to(long_target)).exists():
                raise ValueError('Backup would roll back long-horizon evidence')
        files = sorted(long_source.rglob('*.json'))
        for file in files:
            if file.is_symlink():
                raise ValueError('Long-horizon symlink is not accepted')
            target_file = long_target / file.relative_to(long_source)
            if file.parent.name not in ('prices', 'snapshots'):
                read_sealed(file)
            if file.parent.name != 'prices' and target_file.exists():
                if json.loads(target_file.read_text(encoding='utf-8')) != json.loads(file.read_text(encoding='utf-8')):
                    raise ValueError('Conflicting immutable long-horizon evidence')
        for file in files:
            target_file = long_target / file.relative_to(long_source)
            target_file.parent.mkdir(parents=True, exist_ok=True)
            if not target_file.exists() or file.parent.name == 'prices':
                shutil.copy2(file, target_file)
    return len(read_archives(destination))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    print("Restored validated snapshots:", restore(args.source, args.destination))
