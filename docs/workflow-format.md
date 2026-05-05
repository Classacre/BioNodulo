# Workflow Format

Workflows are JSON documents with:

- `version`
- `app`
- `name`
- `description`
- `nodes`
- `edges`
- `outputs`
- `environment`
- `dependencies`

Each node has:

- `id`
- `type`
- `position`
- `params`
- `node_info`

`node_info` records the node metadata needed for reproducibility and portability, including display name, category, node version, documentation URL, custom node package details, GitHub URL when known, required executables, and environment metadata.

Each edge connects a source output socket to a target input socket:

```json
{
  "id": "edge-1",
  "from": { "node": "input-fastq-1", "output": "reads" },
  "to": { "node": "fastqc-1", "input": "reads" }
}
```

`outputs` lists the terminal nodes to execute. If omitted, all nodes are executed.

`environment` describes the preferred runtime for the workflow, such as Conda/Mamba, Docker, or Apptainer. `dependencies` summarizes the node types, custom node packages, and external tools needed by the workflow so BioNodulo can warn about missing tools or help create a matching environment.
