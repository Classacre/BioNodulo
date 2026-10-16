from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from bionodulo.nodes.builtin.r_family.pheatmap import _ANNOTATION_LEGEND_PADDING_R


def _existing_rscript() -> str | None:
    executable = shutil.which("Rscript")
    if executable:
        return executable
    if os.name == "nt":
        root = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "R"
        return next((str(path) for path in sorted(root.glob("R-*/bin/Rscript.exe"), reverse=True)), None)
    return None


def test_legend_padding_separates_headings_without_changing_entries(tmp_path: Path) -> None:
    """Exercise actual base-R grid bounds; no pheatmap/package install is needed."""
    rscript = _existing_rscript()
    if rscript is None:
        pytest.skip("An existing Rscript runtime is required for the grid geometry regression")
    script = tmp_path / "legend.R"
    output = (tmp_path / "legend.png").as_posix()
    script.write_text(
        'library(grid)\n' + _ANNOTATION_LEGEND_PADDING_R + f'''\n
png("{output}", width = 900, height = 700, res = 100)
items <- gList()
for (name in c("geo_id", "condition")) {{
    top <- unit(ifelse(name == "geo_id", 0.95, 0.55), "npc")
    yy <- top - unit(c(10, 25), "bigpts")
    items[[name]] <- textGrob(name, x = 0.1, y = top, hjust = 0, vjust = 1,
        gp = gpar(fontsize = 10, fontface = "bold"))
    items[[paste0(name, " r")]] <- rectGrob(x = 0.1, y = yy, hjust = 0,
        height = unit(10, "bigpts"), width = unit(10, "bigpts"),
        gp = gpar(fill = c("#112233", "#445566")))
    if (name == "condition") {{
        items[["condition r2"]] <- rectGrob(x = 0.1, y = yy,
            height = unit(10, "bigpts"), width = unit(10, "bigpts"))
    }}
    items[[paste0(name, " t")]] <- textGrob(c("first", "second"), x = 0.2,
        y = yy, hjust = 0, gp = gpar(fontsize = 10))
}}
original <- gTree(children = items)
padded <- pad_annotation_legend(original, c("condition", "geo_id"), 10)
without_y <- function(grob) {{ grob$y <- NULL; grob }}
stopifnot(identical(lapply(original$children, without_y), lapply(padded$children, without_y)))
gap <- function(legend, heading, body) {{
    first_entry <- legend$children[[body]]
    first_entry$label <- first_entry$label[1]
    first_entry$y <- first_entry$y[1]
    convertY(grobY(legend$children[[heading]], 270), "bigpts", valueOnly = TRUE) -
        convertY(grobY(first_entry, 90), "bigpts", valueOnly = TRUE)
}}
for (pair in list(c(1, 3), c(4, 7))) {{
    stopifnot(gap(original, pair[1], pair[2]) < 0, gap(padded, pair[1], pair[2]) > 0)
}}
for (child in padded$children) {{
    for (index in seq_along(child$y)) {{
        entry <- child
        entry$y <- child$y[index]
        if (inherits(child, "text")) entry$label <- child$label[min(index, length(child$label))]
        stopifnot(convertY(grobY(entry, 270), "npc", valueOnly = TRUE) >= 0)
        stopifnot(convertY(grobY(entry, 90), "npc", valueOnly = TRUE) <= 1)
    }}
}}
grid.draw(padded)
dev.off()
''', encoding="utf-8",
    )
    result = subprocess.run([rscript, "--vanilla", str(script)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr[-2000:]
    assert Path(output).stat().st_size > 0
