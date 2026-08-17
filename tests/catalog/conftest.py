"""Catalog test collection guards.

`test_ledger.py` imports `scripts.build_catalog_ledger`. On some Python
installs, a pip-installed `scripts` package in site-packages shadows the
repo's own `scripts/` directory (the repo's scripts/ has no __init__.py,
so it's not a regular package). When this happens, the import raises during
collection and no skipif marker can help. We skip the module entirely.
"""

try:
    import scripts.build_catalog_ledger  # noqa: F401
    _ledger_importable = True
except ImportError:
    _ledger_importable = False


def pytest_ignore_collect(collection_path, config):
    if not _ledger_importable and "test_ledger" in str(collection_path):
        return True
    return None
