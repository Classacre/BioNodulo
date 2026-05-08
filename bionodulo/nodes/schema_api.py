from __future__ import annotations

from bionodulo.nodes.comfy_v3_adapter import ComfyExtension as BioNoduloExtension
from bionodulo.nodes.comfy_v3_adapter import io, ui

SchemaExtension = BioNoduloExtension

__all__ = ["BioNoduloExtension", "SchemaExtension", "io", "ui"]
