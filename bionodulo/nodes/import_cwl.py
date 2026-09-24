"""Import an upstream CWL tool into a data-only BioNodulo catalog.

Example: python -m bionodulo.nodes.import_cwl tool.cwl --environment lock.json
    --node-id imported_tool --tool-id tool --tool-version 1.0 --output catalog.json

Importing does not run the tool, install dependencies, or certify its semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

import yaml
from pydantic import TypeAdapter

from bionodulo.nodes.contract.compiler import CatalogCompiler
from bionodulo.nodes.contract.cwl import import_cwl
from bionodulo.nodes.contract.environments import EnvironmentSpec
from bionodulo.nodes.contract.model import NodeSpec


class _UniqueKeyLoader(yaml.SafeLoader):
    """Reject ambiguous descriptors rather than silently keeping the last key."""

    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                if key in mapping:
                    raise yaml.constructor.ConstructorError(
                        "while parsing a CWL descriptor", node.start_mark,
                        f"duplicate mapping key: {key!r}", key_node.start_mark,
                    )
                mapping[key] = self.construct_object(value_node, deep=deep)
            except TypeError as error:
                raise yaml.constructor.ConstructorError(
                    "while parsing a CWL descriptor", node.start_mark,
                    "mapping keys must be scalar", key_node.start_mark,
                ) from error
        return mapping


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("descriptor", type=Path)
    parser.add_argument("--environment", type=Path, required=True, help="Existing locked EnvironmentSpec JSON")
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--tool-id", required=True)
    parser.add_argument("--tool-version", required=True)
    parser.add_argument("--source-uri", help="Pinned upstream source URL; defaults to descriptor file URI")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--append", action="store_true", help="Append to an existing catalog, rejecting duplicate IDs")
    args = parser.parse_args(argv)
    try:
        if args.descriptor.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("descriptor exceeds the 4 MiB limit")
        raw_source = args.descriptor.read_bytes()
        if len(raw_source) > 4 * 1024 * 1024:
            raise ValueError("descriptor exceeds the 4 MiB limit")
        document = yaml.load(raw_source.decode("utf-8"), Loader=_UniqueKeyLoader)
        environment = TypeAdapter(EnvironmentSpec).validate_json(args.environment.read_bytes())
        spec = import_cwl(
            document, node_id=args.node_id, environment=environment,
            tool_id=args.tool_id, tool_version=args.tool_version,
            source_uri=args.source_uri or args.descriptor.resolve().as_uri(),
            source_content_sha256="sha256:" + hashlib.sha256(raw_source).hexdigest(),
            source_size_bytes=len(raw_source),
        )
        specs = []
        if args.output.exists():
            if not args.append:
                raise ValueError("output already exists; use --append to add a different tool")
            existing = json.loads(args.output.read_text(encoding="utf-8"))
            if (
                not isinstance(existing, dict)
                or set(existing) != {"schema_version", "specs"}
                or type(existing["schema_version"]) is not int
                or existing["schema_version"] != 1
                or not isinstance(existing["specs"], list)
            ):
                raise ValueError("existing output is not a version 1 declarative catalog")
            specs = [NodeSpec.model_validate_json(json.dumps(item)) for item in existing["specs"]]
        specs.append(spec)
        compiled = CatalogCompiler().compile(specs)
        payload = {"schema_version": 1, "specs": [item.model_dump(mode="json") for item in compiled.specs]}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".cwl-catalog-", suffix=".json", dir=args.output.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, indent=2, allow_nan=False)
                handle.write("\n")
            os.replace(temporary, args.output)
        finally:
            Path(temporary).unlink(missing_ok=True)
        print(json.dumps({"catalog": str(args.output.resolve()), "nodes": len(specs),
                          "catalog_digest": compiled.catalog_digest, "verification": "unverified"}))
        return 0
    except (ValueError, OSError, yaml.YAMLError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
