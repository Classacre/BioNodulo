# Custom Nodes

Put Python files in `custom_nodes/`.

BioNodulo can load classic `BaseNode` classes and standalone schema-style classes with `define_schema()` / `execute()`. The schema style is inspired by ComfyUI's modern node API, but it imports only BioNodulo modules and does not require ComfyUI:

```python
from bionodulo.nodes.schema_api import BioNoduloExtension, io


class FastqSummaryNode(io.SchemaNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="fastq_summary",
            display_name="FASTQ Summary",
            category="example",
            is_output_node=True,
            inputs=[
                io.String.Input("reads", multiline=True, default="", description="FASTQ paths, one per line."),
                io.Int.Input("max_records", default=100000, min=1, max=10000000, step=1000, display_mode=io.NumberDisplay.slider),
            ],
            outputs=[io.String.Output("report"), io.Int.Output("read_count")],
        )

    @classmethod
    def execute(cls, reads, max_records):
        return io.NodeOutput(report="summary.txt", read_count=0)


class Extension(BioNoduloExtension):
    async def get_node_list(self):
        return [FastqSummaryNode]
```

Restart the server after adding a custom node.

Custom nodes execute as normal Python imports. Treat them as trusted local code.

The full `custom_nodes/example_node.py.example` file includes a more complete standalone BioNodulo schema-style FASTQ summary implementation with file validation, gzip streaming, multiple outputs, and text preview UI metadata.
