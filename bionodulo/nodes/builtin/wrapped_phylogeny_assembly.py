"""Compatibility facade for relocated phylogeny and assembly nodes."""

from __future__ import annotations

from bionodulo.nodes.builtin import wrapped_phylogeny_assembly_family as _family


__all__ = _family.__all__


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)
    value = getattr(_family, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
