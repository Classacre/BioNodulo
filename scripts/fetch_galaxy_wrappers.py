#!/usr/bin/env python
"""Extract Galaxy tool XML wrappers from a cloned tool repository.

Galaxy's tool count comes from hand-curated XML wrappers, not from generated
stubs. This fetches those wrappers so they can be converted into BioNodulo nodes.

Why not just ``git checkout``: Galaxy test-data filenames legitimately contain
``:`` and ``?`` (for example ``input.chrM:4000-8300.bam``). Those are invalid on
Windows, so a working-tree checkout aborts and leaves nothing. This reads the
tree and pulls only the XML blobs, so the hostile paths are never materialised.

The clone must exist already and may be blobless (``--filter=blob:none``); blobs
are fetched on demand through a single ``git cat-file --batch`` process rather
than one subprocess per file.

Usage:
    python scripts/fetch_galaxy_wrappers.py \
        --repo artifacts/galaxy-tools-iuc \
        --output-dir artifacts/galaxy-wrappers \
        --manifest artifacts/galaxy-wrappers-manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, check=True, timeout=600).stdout


def list_wrappers(repo: Path, prefix: str) -> list[tuple[str, str]]:
    """Return (sha, path) for every tool XML outside test-data."""
    out = git(repo, "ls-tree", "-r", "HEAD")
    entries: list[tuple[str, str]] = []
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        if not path:
            continue
        parts = meta.split()
        if len(parts) < 3 or parts[1] != "blob":
            continue
        if not path.startswith(prefix) or not path.endswith(".xml"):
            continue
        if "/test-data/" in path or "/test_data/" in path:
            continue
        entries.append((parts[2], path))
    return entries


def fetch_blobs(repo: Path, shas: list[str], chunk: int = 64) -> dict[str, str]:
    """Batch-fetch blob contents keyed by sha.

    Requests are written and responses read in small chunks. Writing every
    request before reading any response deadlocks: git blocks once its stdout
    pipe buffer fills (~64 KiB), and this process blocks writing into a stdin
    pipe nobody is draining. Chunking keeps both sides moving.
    """
    payload: dict[str, str] = {}
    for start in range(0, len(shas), chunk):
        batch = shas[start:start + chunk]
        proc = subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        assert proc.stdin and proc.stdout
        proc.stdin.write(("\n".join(batch) + "\n").encode())
        proc.stdin.flush()
        for _ in batch:
            header = proc.stdout.readline().decode("utf-8", errors="replace").strip()
            if not header or header.endswith("missing"):
                continue
            parts = header.split()
            sha, size = parts[0], int(parts[2])
            content = proc.stdout.read(size)
            proc.stdout.read(1)  # trailing newline
            payload[sha] = content.decode("utf-8", errors="replace")
        proc.stdin.close()
        proc.stdout.close()
        proc.wait(timeout=120)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--prefix", default="tools/")
    args = parser.parse_args()

    commit = git(args.repo, "rev-parse", "HEAD").strip()
    entries = list_wrappers(args.repo, args.prefix)
    print(f"{len(entries)} candidate XML wrappers at {commit[:12]}", flush=True)

    shas = [sha for sha, _ in entries]
    blobs = fetch_blobs(args.repo, shas)
    print(f"fetched {len(blobs)} blobs", flush=True)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    seen: dict[str, int] = {}
    for sha, path in entries:
        text = blobs.get(sha)
        if text is None:
            continue
        base = SAFE.sub("_", path[len(args.prefix):].replace("/", "__"))
        count = seen.get(base, 0)
        seen[base] = count + 1
        name = base if count == 0 else f"{base}.{count}"
        target = args.output_dir / name
        target.write_text(text, encoding="utf-8", newline="\n")
        manifest.append({
            "wrapper_path": path,
            "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "bytes": len(text.encode("utf-8")),
            "local_file": name,
        })

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps({
        "schema_version": 1,
        "repository": "https://github.com/galaxyproject/tools-iuc",
        "commit": commit,
        "prefix": args.prefix,
        "candidates": len(entries),
        "extracted": len(manifest),
        "wrappers": manifest,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(manifest)} wrappers to {args.output_dir}")
    print(f"manifest: {args.manifest}")


if __name__ == "__main__":
    main()
