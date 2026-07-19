"""Paths for helper scripts vendored from the pinned wrapper revision."""

from pathlib import Path


ASSET_DIR = Path(__file__).with_name("assets")


def asset_path(name: str) -> str:
    """Return an absolute path to a family-owned helper asset."""

    return str(ASSET_DIR / name)


__all__ = ["ASSET_DIR", "asset_path"]
