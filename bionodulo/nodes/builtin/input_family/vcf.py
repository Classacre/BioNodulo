"""VCF workflow input node."""

from .adapter import _InputVCFContract


class InputVCFNode(_InputVCFContract):
    """Import an uncompressed or bgzip-compressed VCF file."""

    NODE_ID = "input_vcf"
