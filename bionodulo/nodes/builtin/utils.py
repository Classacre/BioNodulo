"""Utility nodes for BioNodulo workflows.

Provides generic command execution, file viewing, file collection,
and VCF merging utilities.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class GenericCommandNode(CommandNode):
    """Execute an arbitrary shell command."""
    NODE_ID = "generic_command"
    DISPLAY_NAME = "Shell Command"
    CATEGORY = "utils"
    DESCRIPTION = "Run any custom shell command"
    SEARCH_ALIASES = ["shell", "command", "bash", "custom", "script"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    REQUIRES_EXTERNAL_TOOLS = False
    SHELL = True
    COMMAND = ["{inputs.command}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "command": ("STRING", {"description": "Shell command to execute", "multiline": True}),
            },
            "optional": {
                "working_dir": ("DIRECTORY", {"description": "Working directory"}),
                "timeout": ("INT", {"default": 3600, "min": 1, "description": "Timeout in seconds"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        # Return as a plain string so the shell receives the command
        # unquoted and can interpret redirects, pipes, etc.
        return str(inputs.get("command", ""))


class ViewTextFileNode(CommandNode):
    """Mark a text file as a workflow output for viewing."""
    NODE_ID = "view_text_file"
    DISPLAY_NAME = "View Text File"
    CATEGORY = "utils"
    DESCRIPTION = "Display a text file as a workflow output"
    SEARCH_ALIASES = ["view", "display", "cat", "text", "output"]
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("content",)
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True
    COMMAND = ["cat", "{inputs.file}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"description": "Text file to display"}),
            },
            "optional": {
                "max_lines": ("INT", {"default": 1000, "min": 1, "description": "Maximum lines to display"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple:
        """Override to read and return file contents directly."""
        file_path = kwargs.get("file")
        max_lines = kwargs.get("max_lines", 1000)
        if not file_path:
            return ("No file provided",)
        try:
            with open(file_path) as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"... ({max_lines} lines shown)")
                        break
                    lines.append(line.rstrip())
                return ("\n".join(lines),)
        except Exception as exc:
            return (f"Error reading file: {exc}",)


class CollectFilesNode(CommandNode):
    """Collect multiple files/directories into a single directory."""
    NODE_ID = "collect_files"
    DISPLAY_NAME = "Collect Files"
    CATEGORY = "utils"
    DESCRIPTION = "Gather multiple files or directories into a single output directory"
    SEARCH_ALIASES = ["collect", "gather", "merge", "directory"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("output_dir",)
    REQUIRES_EXTERNAL_TOOLS = False
    COMMAND = []

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "files": ("FILE", {"description": "Files or directories to collect"}),
            },
            "optional": {
                "output_name": ("STRING", {"default": "collected"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return ["echo", "collect_files: no external command needed"]

    async def run(self, **kwargs: Any) -> tuple:
        """Override to handle file collection in Python."""
        import shutil
        files = kwargs.get("files", [])
        output_name = kwargs.get("output_name", "collected")
        context = kwargs.pop("context", None)
        output_dir = getattr(context, "node_dir", ".") if context else "."
        out = Path(output_dir) / output_name
        out.mkdir(parents=True, exist_ok=True)
        if isinstance(files, str):
            files = [files]
        for f in files:
            src = Path(f)
            if src.is_dir():
                dst = out / src.name
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            elif src.is_file():
                shutil.copy2(src, out / src.name)
        return (str(out),)


class MergeVCFNode(CommandNode):
    """Merge multiple VCF files with bcftools."""
    NODE_ID = "merge_vcf"
    DISPLAY_NAME = "Merge VCF"
    REQUIRED_CONDA_PACKAGES = ['bcftools']
    CATEGORY = "utils"
    DESCRIPTION = "Merge multiple VCF/BCF files into one"
    SEARCH_ALIASES = ["merge", "vcf", "combine", "bcftools merge"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("merged_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html"
    VERSION = "1.20"
    COMMAND = [
        "bcftools", "merge",
        "-Oz",
        "-o", "{output}/merged.vcf.gz",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcfs": ("VCF_GZ", {"description": "List of VCF.gz files to merge"}),
            },
            "optional": {
                "force_samples": ("BOOLEAN", {"default": True}),
                "merge": ("STRING", {"default": "both", "description": "snps, indels, both, all, none"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        vcfs = inputs.get("vcfs", [])
        if isinstance(vcfs, str):
            vcfs = [vcfs]
        cmd = [
            "bcftools", "merge",
            "-Oz",
            "-o", f"{inputs.get('output', '.')}/merged.vcf.gz",
        ]
        if inputs.get("force_samples"):
            cmd.append("--force-samples")
        if inputs.get("merge"):
            cmd.extend(["-m", str(inputs["merge"])])
        cmd.extend(list(vcfs))
        return cmd


class RerouteNode(CommandNode):
    """A pass-through node for routing connections cleanly."""
    NODE_ID = "reroute"
    DISPLAY_NAME = "Reroute"
    CATEGORY = "Utility"
    DESCRIPTION = "Pass a connection through a routing point"
    SEARCH_ALIASES = ["reroute", "pass", "through", "junction", "connection"]
    RETURN_TYPES = ("ANY",)
    RETURN_NAMES = ("output",)
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = False
    COMMAND = []

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("*", {"description": "Any input type"}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple:
        return (kwargs.get("input"),)


class NoteNode(CommandNode):
    """A text note node for workflow annotations."""
    NODE_ID = "note"
    DISPLAY_NAME = "Notes"
    CATEGORY = "Utility"
    DESCRIPTION = "Add a text note or annotation to the workflow"
    SEARCH_ALIASES = ["notes", "note", "text", "comment", "description", "annotation"]
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = False
    VISUAL_ONLY = True
    COMMAND = []

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "text": ("STRING", {"default": "", "multiline": True, "description": "Note text content"}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple:
        return ()


class ImagePreviewNode(CommandNode):
    """Display an image file inline in the canvas — a visual sink node."""
    NODE_ID = "image_preview"
    DISPLAY_NAME = "Image Preview"
    CATEGORY = "Utility"
    DESCRIPTION = "Preview an image file directly in the workflow canvas"
    SEARCH_ALIASES = ["image", "preview", "plot", "png", "jpg", "display"]
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True
    COMMAND = []

    _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"label": "Image File", "description": "Path to an image file"}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        file_path = inputs.get("file")
        if not file_path:
            return "Required input 'file' is missing"
        path = Path(str(file_path))
        if path.suffix.lower() not in cls._IMAGE_EXTS:
            return f"File must be an image ({', '.join(cls._IMAGE_EXTS)}), got: {path.suffix}"
        if not path.exists():
            return f"Image file not found: {file_path}"
        return True

    async def run(self, **kwargs: Any) -> tuple:
        file_path = kwargs.get("file")
        context = kwargs.pop("context", None)
        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(Path(str(file_path or ".")), label="Image Preview")
        return ()


class HtmlPreviewNode(CommandNode):
    """Display an HTML report inline in the canvas — a visual sink node."""
    NODE_ID = "html_preview"
    DISPLAY_NAME = "HTML Preview"
    CATEGORY = "Utility"
    DESCRIPTION = "Preview an HTML report directly in the workflow canvas"
    SEARCH_ALIASES = ["html", "report", "preview", "multiqc", "fastqc", "viewer"]
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True
    COMMAND = []

    _HTML_EXTS = {".html", ".htm"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"label": "HTML File", "description": "Path to an HTML report file"}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        file_path = inputs.get("file")
        if not file_path:
            return "Required input 'file' is missing"
        path = Path(str(file_path))
        if path.suffix.lower() not in cls._HTML_EXTS:
            return f"File must be an HTML report ({', '.join(cls._HTML_EXTS)}), got: {path.suffix}"
        if not path.exists():
            return f"HTML file not found: {file_path}"
        return True

    async def run(self, **kwargs: Any) -> tuple:
        file_path = kwargs.get("file")
        context = kwargs.pop("context", None)
        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(Path(str(file_path or ".")), label="HTML Preview")
        return ()


class TablePreviewNode(CommandNode):
    """Render the head of a CSV/TSV as an inline table on the canvas.

    Keeps the iframe lightweight on huge bioinformatics tables by only
    materialising the first N rows — perfect for variant calls, count
    matrices, stats tables, etc. that have millions of rows.
    """

    NODE_ID = "table_preview"
    DISPLAY_NAME = "Table Preview"
    CATEGORY = "Utility"
    DESCRIPTION = "Preview the head of a CSV/TSV table inline on the canvas"
    SEARCH_ALIASES = ["table", "csv", "tsv", "head", "preview", "data"]
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True
    COMMAND = []

    _TABLE_EXTS = {".csv", ".tsv", ".txt", ".tab"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"label": "Table file", "description": "CSV / TSV / TXT"}),
            },
            "optional": {
                "rows": ("INT", {"default": 25, "min": 1, "max": 500, "label": "Head rows"}),
                "delimiter": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": ["auto", ",", "\t", ";", "|", " "],
                        "label": "Delimiter",
                        "advanced": True,
                    },
                ),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        file_path = inputs.get("file")
        if not file_path:
            return "Required input 'file' is missing"
        path = Path(str(file_path))
        if path.suffix.lower() not in cls._TABLE_EXTS:
            return (
                f"File must be a table ({', '.join(sorted(cls._TABLE_EXTS))}), "
                f"got: {path.suffix}"
            )
        if not path.exists():
            return f"Table file not found: {file_path}"
        return True

    @staticmethod
    def _sniff_delimiter(line: str) -> str:
        # Score candidates by count; tie-break by preferring tab > comma > semi > pipe > space.
        for cand in ("\t", ",", ";", "|", " "):
            if cand in line:
                return cand
        return ","

    async def run(self, **kwargs: Any) -> tuple:
        from html import escape

        file_path = kwargs.get("file")
        rows_limit = int(kwargs.get("rows") or 25)
        delim_choice = str(kwargs.get("delimiter") or "auto")
        context = kwargs.pop("context", None)

        node_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = node_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        out_html = out_dir / "table.html"

        if not file_path:
            return ()

        src = Path(str(file_path))
        total_rows = 0
        header: list[str] = []
        body: list[list[str]] = []

        try:
            with src.open("r", encoding="utf-8", errors="replace") as fh:
                first = fh.readline()
                if not first:
                    return ()
                if delim_choice == "auto":
                    delim = self._sniff_delimiter(first.rstrip("\n").rstrip("\r"))
                else:
                    delim = "\t" if delim_choice == "\\t" else delim_choice
                header = first.rstrip("\n").rstrip("\r").split(delim)
                for line in fh:
                    total_rows += 1
                    if len(body) < rows_limit:
                        body.append(line.rstrip("\n").rstrip("\r").split(delim))
        except Exception as exc:  # noqa: BLE001 — surface the parse error inline
            out_html.write_text(
                f"<!doctype html><meta charset=utf-8><body style='font-family:sans-serif;padding:16px;color:#b91c1c'>"
                f"<strong>Table preview failed:</strong> {escape(str(exc))}</body>",
                encoding="utf-8",
            )
            if context is not None and hasattr(context, "register_preview"):
                context.register_preview(out_html, label="Table Preview")
            return ()

        thead = "".join(f"<th>{escape(h)}</th>" for h in header)
        body_html = "".join(
            "<tr>" + "".join(f"<td>{escape(c)}</td>" for c in row) + "</tr>"
            for row in body
        )
        more = f" — {total_rows - rows_limit:,} more rows not shown" if total_rows > rows_limit else ""
        out_html.write_text(
            f"""<!doctype html><meta charset=utf-8><title>{escape(src.name)}</title>
<style>body{{font-family:system-ui,sans-serif;padding:12px;color:#0f172a}}
h1{{font-size:13px;margin:0 0 8px;color:#475569}}
table{{border-collapse:collapse;font-size:12px;width:100%}}
th,td{{border:1px solid #e2e8f0;padding:4px 8px;text-align:left;vertical-align:top}}
th{{background:#f1f5f9;position:sticky;top:0}}
tr:nth-child(even) td{{background:#f8fafc}}</style>
<h1>{escape(src.name)} — head {min(rows_limit, total_rows):,} of {total_rows:,} rows{escape(more)}</h1>
<table><thead><tr>{thead}</tr></thead><tbody>{body_html}</tbody></table>""",
            encoding="utf-8",
        )

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(out_html, label="Table Preview")
        return ()
