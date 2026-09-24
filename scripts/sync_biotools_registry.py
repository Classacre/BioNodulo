#!/usr/bin/env python
"""Download every bio.tools record into a verified, searchable metadata snapshot.

This produces discovery metadata, never executable nodes. Memory is bounded by
one API page per worker; SQLite orders the final JSONL without loading the full
registry into RAM. A failed/inconsistent crawl never replaces a valid snapshot.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.request

API = "https://bio.tools/api/tool/"
PAGE_SIZE = 100  # API caps per_page at 100, even when a larger size is requested.


def page_url(page: int) -> str:
    return f"{API}?format=json&per_page={PAGE_SIZE}&sort=name&ord=asc&page={page}"


def fetch_page(page: int) -> dict:
    request = urllib.request.Request(page_url(page), headers={
        "User-Agent": "BioNodulo-registry-discovery/1.0",
        "Accept": "application/json",
    })
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.load(response)
            if not isinstance(data.get("count"), int) or not isinstance(data.get("list"), list):
                raise ValueError(f"Invalid registry page {page}")
            return data
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 5:
                raise
            time.sleep(min(30, 2 ** attempt))
    raise AssertionError("unreachable")


def ingest_page(db: sqlite3.Connection, data: dict, expected: int, page: int) -> int:
    if data["count"] != expected:
        raise ValueError(f"Registry count changed on page {page}: {expected} -> {data['count']}")
    expected_length = min(PAGE_SIZE, expected - (page - 1) * PAGE_SIZE)
    if len(data["list"]) != expected_length:
        raise ValueError(f"Incomplete page {page}: {len(data['list'])}, expected {expected_length}")
    for record in data["list"]:
        identifier = record.get("biotoolsID")
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f"Missing bio.tools ID on page {page}")
        # Case-insensitive uniqueness matches registry accession identity.
        payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        db.execute("INSERT INTO tools VALUES (?, ?, ?, ?, ?)", (
            identifier.lower(), identifier, record.get("name") or identifier,
            record.get("description") or "", payload,
        ))
    db.commit()
    return len(data["list"])


def sync(output_dir: Path, workers: int = 2) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    staged_db = output_dir / "registry.partial.sqlite"
    staged_jsonl = output_dir / "registry.partial.jsonl"
    # These exact staging files are owned by this command, never an input cache.
    staged_db.unlink(missing_ok=True)
    staged_jsonl.unlink(missing_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    first = fetch_page(1)
    expected = first["count"]
    pages = math.ceil(expected / PAGE_SIZE)
    print(f"Registry reports {expected} records across {pages} pages", flush=True)
    db = sqlite3.connect(staged_db)
    try:
        db.execute("CREATE TABLE tools (id_key TEXT PRIMARY KEY, biotools_id TEXT, name TEXT, description TEXT, record_json TEXT NOT NULL)")
        count = ingest_page(db, first, expected, 1)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            # Bounded batches: Executor.map alone eagerly queues every page and
            # can retain large responses while an earlier request retries.
            for start in range(2, pages + 1, workers):
                batch = list(range(start, min(start + workers, pages + 1)))
                for page, data in zip(batch, pool.map(fetch_page, batch)):
                    count += ingest_page(db, data, expected, page)
                print(f"{count}/{expected} records", flush=True)
                time.sleep(0.2)
        last = fetch_page(1)
        if last["count"] != expected or count != expected:
            raise ValueError("Registry changed during crawl; retry to obtain a complete snapshot")
        first_ids = [r["biotoolsID"] for r in first["list"]]
        if first_ids != [r["biotoolsID"] for r in last["list"]]:
            raise ValueError("Registry ordering changed during crawl; retry")
        db.execute("CREATE VIRTUAL TABLE search USING fts5(biotools_id, name, description)")
        db.execute("INSERT INTO search SELECT biotools_id, name, description FROM tools")
        db.commit()
        digest = hashlib.sha256()
        with staged_jsonl.open("wb") as handle:
            for (payload,) in db.execute("SELECT record_json FROM tools ORDER BY id_key"):
                line = (payload + "\n").encode("utf-8")
                handle.write(line)
                digest.update(line)
    finally:
        db.close()
    manifest = {
        "schema_version": "1.0", "source": API,
        "source_documentation": "https://biotools.readthedocs.io/en/latest/api_reference.html",
        "license": "CC-BY-4.0", "attribution": "bio.tools registry contributors",
        "started_at": started, "completed_at": datetime.now(timezone.utc).isoformat(),
        "reported_count_start": expected, "reported_count_end": last["count"],
        "records": count, "unique_casefold_ids": count, "pages": pages,
        "page_size": PAGE_SIZE, "ordering": "name asc (API); lowercase ID asc (snapshot)",
        "sha256": digest.hexdigest(), "snapshot": "registry.jsonl", "database": "registry.sqlite",
        "complete": True,
        "consistency": "Non-transactional API crawl; counts, page lengths, unique IDs and first-page ordering verified. Metadata may change within the recorded time window.",
        "execution_status": "metadata_only; no installation, wrapper execution or scientific validation implied",
    }
    staged_jsonl.replace(output_dir / "registry.jsonl")
    staged_db.replace(output_dir / "registry.sqlite")
    manifest_temp = output_dir / "manifest.partial.json"
    manifest_temp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    manifest_temp.replace(output_dir / "manifest.json")
    print(json.dumps(manifest, indent=2), flush=True)
    return manifest


def search(database: Path, query: str, limit: int = 20) -> list[dict]:
    # Quote user tokens so punctuation is not interpreted as FTS syntax.
    tokens = ['"' + token.replace('"', '""') + '"' for token in query.split()]
    if not tokens:
        return []
    with sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True) as db:
        rows = db.execute(
            "SELECT biotools_id, name, snippet(search, 2, '', '', '…', 28) FROM search WHERE search MATCH ? ORDER BY rank LIMIT ?",
            (" AND ".join(tokens), limit),
        )
        return [{"biotools_id": row[0], "name": row[1], "description": row[2],
                 "url": f"https://bio.tools/{row[0]}", "execution_status": "metadata_only"} for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/biotools_registry/current"))
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--search", help="Search an existing complete metadata snapshot without downloading")
    args = parser.parse_args()
    if args.search is not None:
        print(json.dumps(search(args.output_dir / "registry.sqlite", args.search), indent=2, ensure_ascii=False))
    else:
        sync(args.output_dir, args.workers)


if __name__ == "__main__":
    main()
