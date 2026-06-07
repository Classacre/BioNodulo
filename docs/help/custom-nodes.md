# Custom Nodes

Custom nodes let a workspace add reusable analysis steps without changing the
BioNodulo application code. Use them for lab-specific wrappers, prototype
tools, or commands that are not part of the built-in node library yet.

## Node Package Location

BioNodulo loads custom nodes from the configured `custom_nodes` directory under
the active workspace. Keep each package in its own folder so Python modules,
templates, helper scripts, and test data stay together.

## Minimal Node Shape

A custom node module should expose a class derived from the node base used by
the built-in registry. Set `CUSTOM_NODE_CLASS` when the package needs to point
BioNodulo at a specific class.

```python
CUSTOM_NODE_CLASS = "MyToolNode"
```

Define stable input names, output names, display metadata, and required
executables. Clear metadata makes the node easier to find in the library and
lets the help panel render useful node documentation.

## Practical Checks

- Keep command construction deterministic and validate required inputs before
  launching external tools.
- Prefer explicit output paths so downstream nodes can connect to predictable
  files.
- Include a short description, search aliases, and documentation URL when the
  wrapped tool has external reference material.
- Test the node with a small fixture workflow before sharing it with other
  users.
