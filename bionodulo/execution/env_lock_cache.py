"""Shared Pixi environment-lock cache.

Cloud workers refuse to solve environments at run time, so every run needs an
exact ``pixi.toml``/``pixi.lock`` pair. Committing one bundle per environment
(``bionodulo/environments/locks/<id>/``) only covers the curated templates: the
moment a user edits a workflow into a different package set the environment id
is unknown, and the run dies *after* a VM is provisioned and a credit is spent.

This is the second source of locks. A bundle is solved ONCE (at submit time, off
the worker) and published here content-addressed by environment id; every later
run of that same package set — any user, any VM — reads it back. The worker's
rule is unchanged: it still never solves, it only installs a lock it was handed,
and the bundle is validated against the expected manifest before use.

Keys carry the platform. The environment id deliberately does not hash it, and
ARM workers are real (linux-aarch64 with x86 fallback), so an aarch64-solved
lock must never be served to a linux-64 run.

Config (env, from the worker contract):
  ENV_LOCK_CACHE_BUCKET   object-storage bucket for lock bundles (unset = disabled)
  ENV_LOCK_CACHE_PREFIX   key prefix (default "envlocks")

Everything degrades to "no cache": a miss or any storage error returns None and
the caller falls back to the committed bundle, or fails closed as before.
"""
from __future__ import annotations

import os
import sys
from typing import Optional

MANIFEST_NAME = "pixi.toml"
LOCK_NAME = "pixi.lock"


def _eprint(msg: str) -> None:
    print(f"[env_lock_cache] {msg}", file=sys.stderr, flush=True)


def cache_enabled() -> bool:
    return bool(os.environ.get("ENV_LOCK_CACHE_BUCKET", "").strip())


def cache_key(env_id: str, platform: str, name: str) -> str:
    """Object key for one file of a bundle.

    Platform is a path segment rather than part of ``env_id`` so the committed
    on-disk layout (``locks/<env_id>/``) stays untouched while the cache can
    still hold a bundle per platform.
    """
    prefix = os.environ.get("ENV_LOCK_CACHE_PREFIX", "envlocks").strip().strip("/")
    safe_env = "".join(c if (c.isalnum() or c in "-._") else "-" for c in env_id)
    safe_platform = "".join(c if (c.isalnum() or c in "-._") else "-" for c in platform)
    return f"{prefix}/{safe_platform}/{safe_env}/{name}"


def _s3():
    import boto3
    from botocore.config import Config

    # R2/B2 need path-style addressing; boto3 defaults to virtual-host style,
    # which R2 rejects. Mirrors reference_cache._s3().
    endpoint = (
        os.environ.get("AWS_ENDPOINT_URL_S3") or os.environ.get("S3_ENDPOINT_URL") or ""
    ).strip()
    if endpoint:
        return boto3.client("s3", config=Config(s3={"addressing_style": "path"}))
    return boto3.client("s3")


def fetch(env_id: str, platform: str) -> Optional[tuple[str, bytes]]:
    """Return ``(manifest_text, lock_bytes)`` for a cached bundle, else None.

    Shaped for ``bionodulo.environments.manifest.set_lock_cache``. A miss and a
    storage failure are both None: the caller then falls back to the committed
    bundle, and a run never fails *because of* the cache.
    """
    if not cache_enabled():
        return None
    bucket = os.environ["ENV_LOCK_CACHE_BUCKET"].strip()
    try:
        s3 = _s3()
        manifest = s3.get_object(
            Bucket=bucket, Key=cache_key(env_id, platform, MANIFEST_NAME)
        )["Body"].read()
        lock = s3.get_object(Bucket=bucket, Key=cache_key(env_id, platform, LOCK_NAME))[
            "Body"
        ].read()
    except Exception as error:  # noqa: BLE001 - a cache must never break a run
        _eprint(f"miss for {env_id} ({platform}): {type(error).__name__}")
        return None
    if not lock:
        _eprint(f"ignoring empty lock for {env_id} ({platform})")
        return None
    _eprint(f"hit for {env_id} ({platform})")
    return manifest.decode("utf-8"), lock


def publish(env_id: str, platform: str, manifest_text: str, lock_bytes: bytes) -> bool:
    """Store a solved bundle. Returns whether it was written.

    Called by the solver, never by the worker — the worker does not solve, so it
    has nothing to publish.
    """
    if not cache_enabled():
        return False
    if not manifest_text.strip() or not lock_bytes:
        raise ValueError("refusing to publish an empty environment bundle")
    bucket = os.environ["ENV_LOCK_CACHE_BUCKET"].strip()
    try:
        s3 = _s3()
        s3.put_object(
            Bucket=bucket,
            Key=cache_key(env_id, platform, MANIFEST_NAME),
            Body=manifest_text.encode("utf-8"),
        )
        # Lock last: fetch() reads the manifest first, so a torn write surfaces
        # as a miss rather than a mismatched pair.
        s3.put_object(
            Bucket=bucket, Key=cache_key(env_id, platform, LOCK_NAME), Body=lock_bytes
        )
    except Exception as error:  # noqa: BLE001
        _eprint(f"publish failed for {env_id} ({platform}): {type(error).__name__}")
        return False
    _eprint(f"published {env_id} ({platform})")
    return True


def install() -> bool:
    """Register this module as the fallback lock source. Returns whether active."""
    from bionodulo.environments.manifest import set_lock_cache

    if not cache_enabled():
        set_lock_cache(None)
        return False
    set_lock_cache(fetch)
    return True
