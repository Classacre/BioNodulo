"""Compatibility proxy for relocated shared wrapper contracts."""

from bionodulo.nodes.builtin.sequence_visualization_family import adapter as _adapter


def __getattr__(name: str):
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_adapter)))
