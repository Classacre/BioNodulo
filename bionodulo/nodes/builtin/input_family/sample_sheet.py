"""Sample-sheet workflow input node."""

from .adapter import _SampleSheetContract


class SampleSheetNode(_SampleSheetContract):
    """Import a CSV sample sheet."""

    NODE_ID = "input_sample_sheet"
    PRODUCT_SOURCE_COMMIT = _SampleSheetContract.FOCUSED_OWNERSHIP_COMMIT
    PRODUCT_SOURCE_PATH = "bionodulo/nodes/builtin/input_family/sample_sheet.py"
    PRODUCT_SOURCE_SYMBOL = "SampleSheetNode"
    GIT_URL = "https://github.com/Classacre/BioNodulo.git"
    GIT_COMMIT = PRODUCT_SOURCE_COMMIT
    SOURCE_URL = (
        f"https://github.com/Classacre/BioNodulo/blob/{PRODUCT_SOURCE_COMMIT}/"
        f"{PRODUCT_SOURCE_PATH}"
    )
    UPSTREAM_SOURCE = f"{PRODUCT_SOURCE_PATH}:{PRODUCT_SOURCE_SYMBOL}"
    DOCUMENTATION_URL = (
        "https://github.com/python/cpython/blob/"
        f"{_SampleSheetContract.PYTHON_SOURCE_COMMIT}/Lib/shutil.py"
    )
    RUNTIME_DOCUMENTATION_URLS = (
        DOCUMENTATION_URL,
        "https://github.com/python/cpython/blob/"
        f"{_SampleSheetContract.PYTHON_SOURCE_COMMIT}/Lib/urllib/request.py",
        "https://github.com/python/cpython/blob/"
        f"{_SampleSheetContract.PYTHON_SOURCE_COMMIT}/Lib/csv.py",
    )
    SOURCE_AUTHORITIES = {
        **_SampleSheetContract.SOURCE_AUTHORITIES,
        "product_contract": SOURCE_URL,
        "python_csv_format": RUNTIME_DOCUMENTATION_URLS[2],
    }
    EXIT_SEMANTICS = _SampleSheetContract.EXIT_SEMANTICS
