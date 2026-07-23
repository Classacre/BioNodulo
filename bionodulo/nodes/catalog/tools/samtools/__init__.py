"""Samtools 1.23.1 typed catalog nodes.

Each operation lives in its own module so that catalog resolution can import a
single node without importing the whole builtin node index.  ``SPECS`` is a
stable convenience projection for tests and catalog tooling; the forensic
baseline ledger remains unchanged until runtime evidence is collected.
"""

from . import collate, fixmate, flagstat, index, markdup, sort, view

SPECS = (
    collate.SPEC,
    fixmate.SPEC,
    flagstat.SPEC,
    index.SPEC,
    markdup.SPEC,
    sort.SPEC,
    view.SPEC,
)

__all__ = ["SPECS", "collate", "fixmate", "flagstat", "index", "markdup", "sort", "view"]

