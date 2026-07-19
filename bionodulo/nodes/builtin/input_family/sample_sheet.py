"""Sample-sheet workflow input node."""

from .adapter import _SampleSheetContract


class SampleSheetNode(_SampleSheetContract):
    """Import a CSV sample sheet."""

    NODE_ID = "input_sample_sheet"
    PRODUCT_SOURCE_COMMIT = "827ffffc57530d60becfc66f190c35e79d2df7fc"
    PRODUCT_SOURCE_PATH = "bionodulo/nodes/builtin/input_family/sample_sheet.py"
    PRODUCT_SOURCE_SYMBOL = "SampleSheetNode"
    GIT_URL = "https://github.com/Classacre/BioNodulo.git"
    GIT_COMMIT = PRODUCT_SOURCE_COMMIT
    SOURCE_URL = (
        f"https://github.com/Classacre/BioNodulo/blob/{PRODUCT_SOURCE_COMMIT}/"
        f"{PRODUCT_SOURCE_PATH}"
    )
    UPSTREAM_SOURCE = f"{PRODUCT_SOURCE_PATH}:{PRODUCT_SOURCE_SYMBOL}"
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/shutil.html#shutil.copy2"
    RUNTIME_DOCUMENTATION_URLS = (
        DOCUMENTATION_URL,
        "https://docs.python.org/3.12/library/urllib.request.html",
        "https://docs.python.org/3.12/library/csv.html",
    )
    SOURCE_AUTHORITIES = {
        "product_contract": SOURCE_URL,
        "python_copy_runtime": RUNTIME_DOCUMENTATION_URLS[0],
        "python_url_runtime": RUNTIME_DOCUMENTATION_URLS[1],
        "python_csv_format": RUNTIME_DOCUMENTATION_URLS[2],
    }
    EXIT_SEMANTICS = (
        "This in-process node has no subprocess exit code; missing or non-file inputs and URL, "
        "download, validation, or copy failures raise before the staged sample sheet is returned."
    )
