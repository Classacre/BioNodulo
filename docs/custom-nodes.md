# Custom Nodes

Put Python files in `custom_nodes/`.

Example:

```python
from bionodulo.nodes.base import BaseNode


class MyNode(BaseNode):
    NODE_ID = "my_node"
    DISPLAY_NAME = "My Node"
    CATEGORY = "Custom"
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("file",)

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "optional": {}, "hidden": {}}

    def run(self, context=None):
        path = context.node_dir / "output.txt"
        path.write_text("hello\n", encoding="utf-8")
        return {"file": str(path)}
```

Restart the server after adding a custom node.

Custom nodes execute as normal Python imports. Treat them as trusted local code.
