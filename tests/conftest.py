"""Test-suite-wide guarantees.

Keep the suite hermetic: no test may reach out for a vendor binary. Dorado's
tarball is ~4 GB, so a single unguarded node execution turns a 90-second suite
into a stalled download. `tests/test_external_binary.py` unsets this variable
for the cases that deliberately exercise provisioning.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_vendor_binary_downloads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIONODULO_EXTERNAL_BINARY_OFFLINE", "1")
