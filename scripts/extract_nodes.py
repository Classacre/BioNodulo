"""One-tool-per-file node extractor (dependency-aware, AST-based).

Splits a builtin node module into per-tool files under
``bionodulo/nodes/builtin/<category>/<tool>.py``. A "tool" = the set of node
classes sharing a NODE_ID prefix (bedtools_*, samtools_*, or a standalone id).

For each source module it:
  1. Parses all top-level statements (imports, module consts, helper funcs,
     node classes).
  2. Buckets node classes by (category, tool-slug).
  3. For each bucket, computes the transitive set of module-level names
     (helpers, consts) the bucket's classes reference, and emits a file with:
       - the module docstring's `from __future__` + original imports
       - the referenced module-level consts + helper funcs (in original order)
       - the class(es)
  4. Writes a per-category ``_shared.py`` for module-level names referenced by
     classes in MORE THAN ONE tool of that category, and imports it.

Idempotent-ish: writes into a fresh <category>/ dir. The original file is left
in place (caller deletes after verifying). Run ``gen_node_index.py`` after.

Usage: python extract_nodes.py <source_module.py> [<source2.py> ...]
"""
from __future__ import annotations

import ast
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILTIN = ROOT / "bionodulo" / "nodes" / "builtin"


def _tool_slug(node_id: str) -> str:
    s = str(node_id).strip().lower().replace(" ", "_").replace("-", "_")
    # keep alnum/underscore
    s = "".join(c for c in s if c.isalnum() or c == "_")
    return s.split("_")[0] or "misc"


def _node_id_of(cls: ast.ClassDef) -> str | None:
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name) and t.id == "NODE_ID" and isinstance(stmt.value, ast.Constant):
                    return str(stmt.value.value)
    return None


def _category_of(cls: ast.ClassDef) -> str:
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name) and t.id == "CATEGORY" and isinstance(stmt.value, ast.Constant):
                    return str(stmt.value.value)
    return "misc"


def _names_used(node: ast.AST) -> set[str]:
    used: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            used.add(n.id)
        elif isinstance(n, ast.Attribute):
            # capture the root name of an attribute chain
            base = n
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                used.add(base.id)
    return used


def extract(source: Path) -> list[Path]:
    src = source.read_text()
    tree = ast.parse(src)

    imports: list[ast.stmt] = []
    module_defs: dict[str, ast.stmt] = {}     # name -> def/assign stmt (helpers + consts)
    module_def_order: list[str] = []
    classes: list[ast.ClassDef] = []

    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            imports.append(stmt)
        elif isinstance(stmt, ast.FunctionDef) and not stmt.name.startswith("__"):
            module_defs[stmt.name] = stmt
            module_def_order.append(stmt.name)
        elif isinstance(stmt, ast.AsyncFunctionDef):
            module_defs[stmt.name] = stmt
            module_def_order.append(stmt.name)
        elif isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    module_defs[t.id] = stmt
                    module_def_order.append(t.id)
        elif isinstance(stmt, ast.ClassDef):
            if _node_id_of(stmt):
                classes.append(stmt)
            else:
                # non-node helper class — treat as a module def
                module_defs[stmt.name] = stmt
                module_def_order.append(stmt.name)

    # transitive closure of module-level names a class needs
    def closure(seed_names: set[str]) -> set[str]:
        need: set[str] = set()
        frontier = set(seed_names)
        while frontier:
            nm = frontier.pop()
            if nm in need or nm not in module_defs:
                continue
            need.add(nm)
            frontier |= (_names_used(module_defs[nm]) & set(module_defs))
        return need

    # bucket classes by (category, tool)
    buckets: dict[tuple[str, str], list[ast.ClassDef]] = defaultdict(list)
    for c in classes:
        nid = _node_id_of(c) or c.name
        buckets[(_category_of(c), _tool_slug(nid))].append(c)

    # which module defs are needed by each bucket
    bucket_needs: dict[tuple[str, str], set[str]] = {}
    for key, cls_list in buckets.items():
        seed: set[str] = set()
        for c in cls_list:
            seed |= (_names_used(c) & set(module_defs))
        bucket_needs[key] = closure(seed)

    # a module def used by >1 bucket within the SAME category -> shared
    cat_usage: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for (cat, tool), needs in bucket_needs.items():
        for nm in needs:
            cat_usage[cat][nm] += 1
    shared_by_cat: dict[str, set[str]] = {
        cat: {nm for nm, cnt in usage.items() if cnt > 1}
        for cat, usage in cat_usage.items()
    }

    import_src = "\n".join(ast.unparse(i) for i in imports)
    written: list[Path] = []

    # write per-category _shared.py
    for cat, shared_names in shared_by_cat.items():
        if not shared_names:
            continue
        cat_dir = BUILTIN / cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        (cat_dir / "__init__.py").touch()
        ordered = [n for n in module_def_order if n in shared_names]
        body = "\n\n".join(ast.unparse(module_defs[n]) for n in ordered)
        (cat_dir / "_shared.py").write_text(
            f'"""Shared helpers for the {cat} category (extracted).', encoding="utf-8"
        )
        (cat_dir / "_shared.py").write_text(
            f'"""Shared helpers/constants for the {cat} node category."""\n'
            f"from __future__ import annotations\n\n{import_src}\n\n\n{body}\n",
            encoding="utf-8",
        )
        written.append(cat_dir / "_shared.py")

    # write per-tool files
    for (cat, tool), cls_list in buckets.items():
        cat_dir = BUILTIN / cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        (cat_dir / "__init__.py").touch()
        needs = bucket_needs[(cat, tool)]
        shared = shared_by_cat.get(cat, set())
        local = needs - shared
        local_ordered = [n for n in module_def_order if n in local]
        local_body = "\n\n".join(ast.unparse(module_defs[n]) for n in local_ordered)
        class_body = "\n\n\n".join(ast.unparse(c) for c in cls_list)
        shared_import = ""
        used_shared = needs & shared
        if used_shared:
            shared_import = (
                f"from bionodulo.nodes.builtin.{cat}._shared import "
                + ", ".join(sorted(used_shared)) + "\n"
            )
        parts = [
            f'"""{tool} node(s) — {cat} category (extracted, one tool per file)."""',
            "from __future__ import annotations",
            "",
            import_src,
            shared_import,
        ]
        if local_body:
            parts += ["", local_body]
        parts += ["", "", class_body, ""]
        out = cat_dir / f"{tool}.py"
        out.write_text("\n".join(parts), encoding="utf-8")
        written.append(out)

    return written


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    for arg in sys.argv[1:]:
        p = Path(arg)
        if not p.is_absolute():
            p = BUILTIN / p if (BUILTIN / p).exists() else Path(arg)
        written = extract(p)
        print(f"{p.name}: wrote {len(written)} files")
        for w in written:
            print(f"  {w.relative_to(BUILTIN)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
