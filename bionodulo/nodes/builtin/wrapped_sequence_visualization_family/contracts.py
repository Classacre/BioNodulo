"""Compatibility proxy for relocated wrapper evidence."""

from bionodulo.nodes.builtin.sequence_visualization_family import contracts as _contracts


def __getattr__(name: str):
    return getattr(_contracts, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_contracts)))
