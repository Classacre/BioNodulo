"""Stable owner for the Tools-IUC ``cactus_export`` contract."""

from .legacy import _CactusExportContract


class CactusExportNode(_CactusExportContract):
    NODE_ID = "cactus_export"
    OUTPUT_NAME_BY_BASENAME = {
        "alignment.maf": "out_maf",
        "alignment.pg": "out_vg",
        "assemblyhub.tar": "out_ah",
    }
