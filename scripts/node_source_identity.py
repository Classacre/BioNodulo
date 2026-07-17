"""Dependency-free source identity rules shared by ledger emitters and validators."""

from __future__ import annotations


def module_name(source_path: str) -> str:
    """Derive the import module recorded for one repository-relative Python source."""

    module = source_path.removesuffix(".py").replace("/", ".")
    if module.endswith(".__init__"):
        module = module[: -len(".__init__")]
    return module


def qualified_class(module: str, qualified_name: str) -> str:
    """Combine a module and emitter-qualified lexical class name."""

    if not module or not qualified_name:
        raise ValueError("module and qualified_name must be nonempty")
    return f"{module}.{qualified_name}"


def qualified_name_suffix(module: str, value: str) -> str:
    """Return the lexical class-name suffix from a fully qualified class identity."""

    prefix = f"{module}."
    if not module or not value.startswith(prefix) or len(value) == len(prefix):
        raise ValueError("qualified class does not belong to module")
    return value[len(prefix) :]
