"""R language integration nodes for BioNodulo.

Provides nodes to run R scripts and generate plot previews on the canvas.
"""
from __future__ import annotations

import csv
import textwrap
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


class DataFrameBuilderNode(BaseNode):
    """Build a CSV data frame from inputs, useful for preparing data for R plots."""

    NODE_ID = "r_dataframe_builder"
    DISPLAY_NAME = "R DataFrame Builder"
    CATEGORY = "r"
    DESCRIPTION = "Build a CSV data frame with named columns for R plotting"
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("csv",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "x_column": ("STRING", {"default": "x", "label": "X Column Name"}),
                "x_values": ("STRING", {"default": "1,2,3,4,5", "multiline": True, "label": "X Values (comma-separated)"}),
                "y_column": ("STRING", {"default": "y", "label": "Y Column Name"}),
                "y_values": ("STRING", {"default": "2,4,6,8,10", "multiline": True, "label": "Y Values (comma-separated)"}),
            },
            "optional": {
                "group_column": ("STRING", {"default": "", "label": "Group Column Name (optional)", "advanced": True}),
                "group_values": ("STRING", {"default": "", "multiline": True, "label": "Group Values (optional)", "advanced": True}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop("context", None)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_path = output_dir / self.NODE_ID / "data.csv"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        x_col = kwargs.get("x_column", "x")
        y_col = kwargs.get("y_column", "y")
        x_vals = [v.strip() for v in str(kwargs.get("x_values", "")).split(",") if v.strip()]
        y_vals = [v.strip() for v in str(kwargs.get("y_values", "")).split(",") if v.strip()]
        g_col = str(kwargs.get("group_column", "")).strip()
        g_vals = [v.strip() for v in str(kwargs.get("group_values", "")).split(",") if v.strip()]

        min_len = min(len(x_vals), len(y_vals))
        if g_vals:
            min_len = min(min_len, len(g_vals))

        with open(out_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            header = [x_col, y_col]
            if g_col:
                header.append(g_col)
            writer.writerow(header)
            for i in range(min_len):
                row = [x_vals[i], y_vals[i]]
                if g_col and i < len(g_vals):
                    row.append(g_vals[i])
                writer.writerow(row)

        return (str(out_path),)


class RPlotNode(BaseNode):
    """Run an R script to generate a plot image, with built-in ggplot2 templates."""

    NODE_ID = "r_plot"
    DISPLAY_NAME = "R Plot"
    CATEGORY = "r"
    DESCRIPTION = "Generate plots in R (ggplot2) with live preview"
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("plot_png",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = ['r-base']
    REQUIRED_R_PACKAGES = ["ggplot2", "readr"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data_csv": ("FILE", {"label": "Data CSV"}),
                "plot_type": ("STRING", {
                    "default": "scatter",
                    "options": ["scatter", "line", "bar", "histogram", "boxplot", "density", "heatmap", "custom"],
                    "label": "Plot Type",
                }),
                "x_axis": ("STRING", {"default": "x", "label": "X Axis Column"}),
                "y_axis": ("STRING", {"default": "y", "label": "Y Axis Column"}),
            },
            "optional": {
                "color_column": ("STRING", {"default": "", "label": "Color/Fill Column", "advanced": True}),
                "title": ("STRING", {"default": "", "label": "Plot Title", "advanced": True}),
                "x_label": ("STRING", {"default": "", "label": "X Axis Label", "advanced": True}),
                "y_label": ("STRING", {"default": "", "label": "Y Axis Label", "advanced": True}),
                "width": ("INT", {"default": 800, "min": 200, "max": 4000, "step": 50, "display": "slider", "label": "Width (px)", "advanced": True}),
                "height": ("INT", {"default": 600, "min": 200, "max": 4000, "step": 50, "display": "slider", "label": "Height (px)", "advanced": True}),
                "custom_script": ("STRING", {"default": "", "multiline": True, "label": "Custom R Script (overrides template)", "advanced": True}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop("context", None)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        png_path = out_dir / "plot.png"
        script_path = out_dir / "plot.R"

        data_csv = kwargs["data_csv"]
        plot_type = kwargs.get("plot_type", "scatter")
        x_axis = kwargs.get("x_axis", "x")
        y_axis = kwargs.get("y_axis", "y")
        color_col = kwargs.get("color_column", "") or ""
        title = kwargs.get("title", "") or ""
        x_label = kwargs.get("x_label", "") or ""
        y_label = kwargs.get("y_label", "") or ""
        width = kwargs.get("width", 800)
        height = kwargs.get("height", 600)
        custom_script = kwargs.get("custom_script", "") or ""

        # Validate that configured columns exist in the CSV
        if not custom_script.strip() and data_csv:
            try:
                import csv
                with open(data_csv, newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    header = next(reader, [])
                missing = []
                for col in [x_axis, y_axis, color_col]:
                    if col and col not in header:
                        missing.append(col)
                if missing:
                    available = ", ".join(header) if header else "(no columns found)"
                    raise ValueError(
                        f"Column(s) not found in data: {', '.join(missing)}. "
                        f"Available columns: {available}"
                    )
            except ValueError:
                raise
            except Exception:
                pass  # If we can't read the CSV, let R handle the error

        if custom_script.strip():
            script = custom_script
        else:
            script = self._build_ggplot_script(
                data_csv, plot_type, x_axis, y_axis, color_col,
                title, x_label, y_label, width, height, png_path,
            )

        script_path.write_text(script, encoding="utf-8")

        cmd = ["Rscript", str(script_path)]

        if context is not None and hasattr(context, "run_command"):
            result = await context.run_command(cmd, cwd=str(out_dir))
        else:
            import asyncio
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()
            result = {"returncode": proc.returncode}

        if result.get("returncode", 0) != 0:
            raise RuntimeError(f"R plot script failed: {result.get('stderr', '')}")

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(png_path, label=f"R {plot_type} plot")

        return (str(png_path),)

    @staticmethod
    def _build_ggplot_script(
        data_csv: str,
        plot_type: str,
        x_axis: str,
        y_axis: str,
        color_col: str,
        title: str,
        x_label: str,
        y_label: str,
        width: int,
        height: int,
        png_path: Path,
    ) -> str:
        def r_name(name: str) -> str:
            """Quote column names for R so non-syntactic names (spaces, dashes) work."""
            return f"`{name}`" if name and not name.isidentifier() else name

        safe_title = title.replace('"', '\\"')
        safe_x = x_label.replace('"', '\\"') or x_axis
        safe_y = y_label.replace('"', '\\"') or y_axis
        rx = r_name(x_axis)
        ry = r_name(y_axis)
        rc = r_name(color_col) if color_col else ""

        # Plot types that only need an x aesthetic
        x_only_types = {"histogram", "density"}

        if plot_type in x_only_types:
            base_aes = f"aes(x = {rx})"
        elif plot_type == "heatmap":
            base_aes = f"aes(x = {rx}, y = {ry}, fill = {rc})" if rc else f"aes(x = {rx}, y = {ry})"
        else:
            base_aes = f"aes(x = {rx}, y = {ry})"

        if plot_type == "scatter":
            layer = f"geom_point({f'aes(color = {rc})' if rc else ''})"
        elif plot_type == "line":
            layer = f"geom_line({f'aes(color = {rc})' if rc else ''}) + geom_point()"
        elif plot_type == "bar":
            layer = f"geom_bar(stat = 'identity'{f', aes(fill = {rc})' if rc else ''})"
        elif plot_type == "histogram":
            layer = f"geom_histogram(bins = 30{f', aes(fill = {rc})' if rc else ''})"
        elif plot_type == "boxplot":
            layer = f"geom_boxplot({f'aes(fill = {rc})' if rc else ''})"
        elif plot_type == "density":
            layer = f"geom_density({f'aes(color = {rc})' if rc else ''})"
        elif plot_type == "heatmap":
            layer = "geom_tile()"
        else:
            layer = "geom_point()"

        script = textwrap.dedent(f"""\
            if (!requireNamespace("ggplot2", quietly = TRUE)) stop("Package 'ggplot2' is required but not installed. Install it with: install.packages('ggplot2')")
            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed. Install it with: install.packages('readr')")
            library(ggplot2)
            library(readr)
            data <- read_csv("{Path(data_csv).as_posix()}")
            p <- ggplot(data, {base_aes}) + {layer} +
                labs(title = "{safe_title}", x = "{safe_x}", y = "{safe_y}") +
                theme_minimal() + theme(plot.title = element_text(hjust = 0.5))
            ggsave("{png_path.as_posix()}", plot = p, width = {width / 100}, height = {height / 100}, dpi = 100, units = "in")
        """)
        return script


class RScriptNode(BaseNode):
    """Run an arbitrary R script file."""

    NODE_ID = "r_script"
    DISPLAY_NAME = "R Script"
    REQUIRED_CONDA_PACKAGES = ['r-base']
    CATEGORY = "r"
    DESCRIPTION = "Execute an arbitrary R script"
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_dir",)
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_R_PACKAGES = []

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "script": ("FILE", {"label": "R Script File"}),
            },
            "optional": {
                "args": ("STRING", {"default": "", "label": "Arguments", "advanced": True}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop("context", None)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)

        script = kwargs["script"]
        args = str(kwargs.get("args", "")).strip()

        cmd = ["Rscript", str(script)]
        if args:
            cmd.extend(args.split())

        if context is not None and hasattr(context, "run_command"):
            result = await context.run_command(cmd, cwd=str(out_dir))
        else:
            import asyncio
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()
            result = {"returncode": proc.returncode}

        if result.get("returncode", 0) != 0:
            raise RuntimeError(f"R script failed: {result.get('stderr', '')}")

        return (str(out_dir),)
