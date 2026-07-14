"""One-tool-per-file node extractor (robust, over-inclusive).

Splits builtin node modules into ``bionodulo/nodes/builtin/<category>/<tool>.py``,
one file per TOOL (node classes sharing a NODE_ID prefix). Correctness-first:
each generated tool file carries the FULL set of its source file's imports and
module-level helpers/consts, so a class can never lose a dependency. The cost is
duplicated helper code across tools from the same origin — acceptable (unused
defs are free; ruff/dedup can follow). This trades tidy-shared-modules for
"never breaks", which is what a 943-node mechanical migration needs.

Category = the node's declared CATEGORY, falling back to the source filename when
blank/general/misc. Collisions with a PRE-EXISTING package dir (e.g. builtin/api/
holds infra) or a same-name file are avoided by suffixing the tool file.

Run gen_node_index.py after. Usage:
    python extract_nodes.py <src.py> [...]        # extract
    python extract_nodes.py --verify <category>   # import+render check a dir
"""
from __future__ import annotations

import ast
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILTIN = ROOT / "bionodulo" / "nodes" / "builtin"

# Category dirs that already exist as hand-maintained packages — never write
# extracted tool files directly into them (suffix by origin instead).
RESERVED_DIRS = {"api"}


def _tool_slug(node_id: str) -> str:
    s = str(node_id).strip().lower().replace(" ", "_").replace("-", "_")
    s = "".join(c for c in s if c.isalnum() or c == "_")
    return s.split("_")[0] or "misc"


def _class_attr(cls: ast.ClassDef, name: str) -> str | None:
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name) and t.id == name and isinstance(stmt.value, ast.Constant):
                    return str(stmt.value.value)
    return None


def _is_node(cls: ast.ClassDef) -> bool:
    return _class_attr(cls, "NODE_ID") is not None


def extract(source: Path) -> list[Path]:
    src = source.read_text()
    tree = ast.parse(src)
    origin = source.stem

    # Everything that is NOT a node class = the shared "preamble" carried into
    # every tool file from this origin: imports, module consts, helper funcs,
    # and non-node helper classes — in original source order.
    preamble_stmts: list[ast.stmt] = []
    node_classes: list[ast.ClassDef] = []
    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef) and _is_node(stmt):
            node_classes.append(stmt)
        elif isinstance(stmt, ast.Expr) and isinstance(getattr(stmt, "value", None), ast.Constant) \
                and stmt is tree.body[0]:
            # module docstring — skip (each file gets its own)
            continue
        else:
            preamble_stmts.append(stmt)

    preamble = "\n".join(ast.unparse(s) for s in preamble_stmts)

    # bucket node classes by (category, tool)
    def cat_of(c: ast.ClassDef) -> str:
        cat = _class_attr(c, "CATEGORY")
        if not cat or cat.lower() in ("misc", "general", "", "?"):
            return origin
        return cat

    buckets: dict[tuple[str, str], list[ast.ClassDef]] = defaultdict(list)
    for c in node_classes:
        nid = _class_attr(c, "NODE_ID") or c.name
        buckets[(cat_of(c), _tool_slug(nid))].append(c)

    written: list[Path] = []
    for (cat, tool), cls_list in buckets.items():
        cat_dir = BUILTIN / cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        init = cat_dir / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")
        class_body = "\n\n\n".join(ast.unparse(c) for c in cls_list)
        target = cat_dir / f"{tool}.py"
        # collision handling
        if cat in RESERVED_DIRS or (target.exists() and target not in written):
            target = cat_dir / f"{tool}__{origin}.py"
        if target.exists() and target in written:
            # same (cat,tool) from a 2nd source file this run → append classes
            target.write_text(target.read_text().rstrip() + "\n\n\n" + class_body + "\n", encoding="utf-8")
        else:
            doc = f'"""{tool} — {cat} node(s). One tool per file (extracted from {origin}.py)."""'
            target.write_text(f"{doc}\n{preamble}\n\n\n{class_body}\n", encoding="utf-8")
        written.append(target)
    return written


def verify_dir(category: str) -> tuple[int, list[str]]:
    """Import every extracted tool file in a category dir; return (ok, errors)."""
    import importlib
    cat_dir = BUILTIN / category
    ok, errors = 0, []
    for f in sorted(cat_dir.glob("*.py")):
        if f.name.startswith("__"):
            continue
        mod = f"bionodulo.nodes.builtin.{category}.{f.stem}"
        try:
            importlib.import_module(mod)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{mod}: {type(exc).__name__}: {exc}")
    return ok, errors


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--verify":
        ok, errs = verify_dir(sys.argv[2])
        print(f"{sys.argv[2]}: {ok} files import OK, {len(errs)} errors")
        for e in errs:
            print("  ERR", e)
        return 1 if errs else 0
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    for arg in sys.argv[1:]:
        p = Path(arg)
        if not p.is_absolute() and not p.exists():
            p = BUILTIN / arg
        w = extract(p)
        print(f"{p.name}: {len(w)} tool file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
