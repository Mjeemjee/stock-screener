"""Stage only built assets and the existing explicit public-data allowlist.

Local public/ may contain private account files. Do not copy the entire build.
"""
import argparse
from pathlib import Path
import shutil

from scripts.verify_public_build import PUBLIC_DATA, verify


def prepare(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source.is_relative_to(output) or output.is_relative_to(source):
        raise ValueError("Public staging directory must be separate from the source build")
    if not (source / "index.html").is_file():
        raise ValueError("Missing built index.html")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "index.html", output / "index.html")
    for file in (source / "assets").rglob("*"):
        if file.is_symlink():
            raise ValueError("Symlinks are not accepted in public build assets")
        if file.is_file():
            target = output / file.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
    for name in sorted(PUBLIC_DATA):
        file = source / "data" / name
        if file.is_symlink():
            raise ValueError("Symlinks are not accepted in public data")
        if file.is_file():
            target = output / "data" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
    return verify(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args()
    print("Public staging verified:", ", ".join(prepare(args.source, args.output)))
