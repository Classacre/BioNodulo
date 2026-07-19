"""Sample-sheet workflow input node."""

from .adapter import _SampleSheetContract


class SampleSheetNode(_SampleSheetContract):
    """Import a CSV sample sheet."""

    NODE_ID = "input_sample_sheet"
