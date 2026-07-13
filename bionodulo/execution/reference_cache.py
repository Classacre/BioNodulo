"""Shared reference-data cache (perf §15 #3).

Heavy workflows re-fetch/rebuild huge references every run (STAR human index
~30 GB, kraken2 DBs tens of GB). This module lets a workflow declare the
references it needs; each is fetched ONCE into a shared object-storage bucket
(content-addressed by reference id), then staged to LOCAL NVMe per job so
random-access reads don't fight over a shared filesystem (a known bottleneck
under parallelism).

The reference id is a stable slug (e.g. "star-grch38-ens110", "kraken2-standard-8g").
On a shared-store hit the archive is downloaded + extracted to local scratch and
the local path is returned; the node then points its tool at that path instead
of rebuilding. On a miss the caller builds/downloads the reference, then calls
`publish()` so every later run (any user/VM) reuses it.

Config (env, from the worker contract):
  REFERENCE_CACHE_BUCKET   object-storage bucket for references (unset = disabled)
  REFERENCE_CACHE_PREFIX   key prefix (default "refcache")
  REFERENCE_LOCAL_DIR      local NVMe stage dir (default "$TEMP_DIR/refs")

Everything degrades gracefully to "no cache" so a run never fails on cache issues.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


def _eprint(msg: str) -> None:
    print(f"[reference_cache] {msg}", file=sys.stderr, flush=True)


def cache_enabled() -> bool:
    return bool(os.environ.get("REFERENCE_CACHE_BUCKET", "").strip())


def file_identity(path: object) -> str:
    """Cheap stable identity for a (possibly multi-GB) reference file: name+size.

    Avoids hashing gigabytes — for a public reference genome, name+size is a
    reliable key (the same GRCh38 FASTA is byte-identical everywhere). A missing
    file falls back to the basename so callers still get a deterministic id.
    """
    p = Path(str(path))
    try:
        return f"{p.name}:{p.stat().st_size}"
    except OSError:
        return p.name


def compute_ref_id(kind: str, parts: list[object]) -> str:
    """Stable content-addressed id for a reference from its identifying parts.

    `kind` is a readable prefix (e.g. "star"); `parts` define the reference — for
    a STAR index that's the FASTA identity, GTF identity, tool version and index
    params. Same inputs anywhere → same id → shared cache hit across all users.
    """
    canonical = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in kind)
    return f"{safe}-{digest}"


def _key(ref_id: str) -> str:
    prefix = os.environ.get("REFERENCE_CACHE_PREFIX", "refcache").strip().strip("/")
    safe = "".join(c if (c.isalnum() or c in "-._") else "-" for c in ref_id)
    return f"{prefix}/{safe}.tar.zst"


def _local_dir() -> Path:
    base = os.environ.get("REFERENCE_LOCAL_DIR", "").strip()
    if not base:
        base = str(Path(os.environ.get("TEMP_DIR", "/tmp")) / "refs")
    return Path(base)


def _s3():
    import boto3
    from botocore.config import Config

    # R2/B2 need path-style addressing; boto3 honors AWS_ENDPOINT_URL_S3 for the
    # endpoint but defaults to virtual-host style, which R2 rejects. Force
    # path-style whenever a custom endpoint is configured. No endpoint set (plain
    # AWS S3) → default addressing, unchanged.
    endpoint = (
        os.environ.get("AWS_ENDPOINT_URL_S3")
        or os.environ.get("S3_ENDPOINT_URL")
        or ""
    ).strip()
    if endpoint:
        return boto3.client(
            "s3", config=Config(s3={"addressing_style": "path"})
        )
    return boto3.client("s3")


def stage(ref_id: str) -> Optional[Path]:
    """Return a local path to the staged reference, or None on miss/disabled.

    On a shared-store hit: download the archive → extract to local NVMe → return
    the extracted dir. Idempotent: if already staged locally, returns it without
    re-downloading.
    """
    if not cache_enabled():
        return None
    local = _local_dir() / ref_id
    marker = local / ".staged"
    if marker.exists():
        _eprint(f"reference already staged: {local}")
        return local
    bucket = os.environ["REFERENCE_CACHE_BUCKET"].strip()
    key = _key(ref_id)
    archive = _local_dir() / f"{ref_id}.tar.zst"
    try:
        s3 = _s3()
        try:
            s3.head_object(Bucket=bucket, Key=key)
        except Exception:  # noqa: BLE001 — miss → caller builds it
            _eprint(f"reference miss: {key}")
            return None
        local.mkdir(parents=True, exist_ok=True)
        _eprint(f"reference HIT {key} — staging to {local}")
        s3.download_file(bucket, key, str(archive))
        # zstd extract to local NVMe (fast sequential read of one big archive).
        proc = subprocess.run(
            ["tar", "--use-compress-program=unzstd", "-xf", str(archive), "-C", str(local)],
            capture_output=True, text=True, timeout=3600,
        )
        if proc.returncode != 0:
            _eprint(f"extract failed: {proc.stderr[-300:]}")
            return None
        marker.touch()
        return local
    except Exception as exc:  # noqa: BLE001
        _eprint(f"stage error (miss): {exc}")
        return None
    finally:
        with __import__("contextlib").suppress(OSError):
            archive.unlink()


def publish(ref_id: str, local_path: Path) -> None:
    """Pack a freshly-built reference dir and upload to the shared store."""
    if not cache_enabled():
        return
    bucket = os.environ["REFERENCE_CACHE_BUCKET"].strip()
    key = _key(ref_id)
    archive = _local_dir() / f"{ref_id}.publish.tar.zst"
    try:
        archive.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            ["tar", "--use-compress-program=zstd -T0", "-cf", str(archive),
             "-C", str(local_path), "."],
            capture_output=True, text=True, timeout=7200,
        )
        if proc.returncode != 0 or not archive.exists():
            _eprint(f"pack failed: {proc.stderr[-300:]}")
            return
        _s3().upload_file(str(archive), bucket, key)
        _eprint(f"published reference {ref_id} → s3://{bucket}/{key}")
    except Exception as exc:  # noqa: BLE001
        _eprint(f"publish error (ignored): {exc}")
    finally:
        with __import__("contextlib").suppress(OSError):
            archive.unlink()
