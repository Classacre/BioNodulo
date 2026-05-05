# Workflow Format

Workflows are JSON documents with:

- `version`
- `app`
- `name`
- `description`
- `nodes`
- `edges`
- `outputs`

Each node has:

- `id`
- `type`
- `position`
- `params`

Each edge connects a source output socket to a target input socket:

```json
{
  "id": "edge-1",
  "from": { "node": "input-fastq-1", "output": "reads" },
  "to": { "node": "fastqc-1", "input": "reads" }
}
```

`outputs` lists the terminal nodes to execute. If omitted, all nodes are executed.
