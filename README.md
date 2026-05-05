# BioNodulo

Visual bioinformatics pipelines, node by node.

BioNodulo is a Python-first, browser-based workflow workbench for bioinformatics pipelines. It takes architectural inspiration from ComfyUI's node graph, dynamic node metadata, queue model, WebSocket updates, custom-node extensibility, workflow JSON, and cache-aware execution, but it is not an AI image generation app and does not copy ComfyUI source code.

The MVP is aimed at scientists, students, research assistants, educators, and bioinformaticians who want a fast visual prototyping layer without immediately writing Snakemake, Nextflow, CWL, or WDL.

## What It Is

- A local FastAPI app launched with `python main.py`
- A visual graph UI served by the Python backend
- Python node classes with metadata exposed through `/object_info`
- Workflow JSON for saving, loading, sharing, and running graphs
- Async run queue with REST and WebSocket status updates
- Mock execution mode that works without bioinformatics tools installed
- Real subprocess mode that uses tools found on local `PATH`
- Run directories with workflow snapshots, logs, metadata, commands, outputs, and cache keys

## What It Is Not

BioNodulo does not include diffusion models, PyTorch model loading, image generation, CLIP, VAE, checkpoints, LoRAs, schedulers, prompt weighting, or anything specific to generative AI.

Compared with Snakemake and Nextflow, BioNodulo is a visual prototyping and teaching workbench first. Compared with Galaxy, it is intentionally lightweight, local-first, Python-first, and plugin-oriented. Future export to mature workflow systems is a goal, not an MVP dependency.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS/Linux, activate with `source .venv/bin/activate`.

## Run

```bash
python main.py
```

The app starts at `http://127.0.0.1:8000`. Mock mode is enabled by default. You can also make that explicit:

```bash
python main.py --mock-tools
```

Use real local command execution by turning off Mock mode in the UI. If a required executable such as `fastqc`, `fastp`, or `multiqc` is missing, the run fails with a clear validation error.

## Demo Workflow

In the UI, click `Sample`, then `Run`.

The sample workflow is:

```text
Input FASTQ -> FastQC -> fastp -> FastQC -> Collect Files -> MultiQC
```

Mock mode creates placeholder outputs under `runs/<run-id>/nodes/...`. Run the same workflow again and unchanged nodes should report as cached.

## Node API Sketch

```python
from bionodulo.nodes.base import BaseNode


class FastQCNode(BaseNode):
    NODE_ID = "fastqc"
    DISPLAY_NAME = "FastQC"
    CATEGORY = "Quality Control"
    RETURN_TYPES = ("QC_REPORT_DIR", "FASTQ_LIST")
    RETURN_NAMES = ("report_dir", "reads")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"reads": ("FASTQ_LIST", {"description": "FASTQ files"})},
            "optional": {"threads": ("INT", {"default": 4, "min": 1, "max": 64})},
            "hidden": {},
        }

    def run(self, reads, threads=4, context=None):
        ...
```

Custom nodes can be placed in `custom_nodes/` as Python files. Import failures are stored as warnings so one broken custom node does not prevent startup.

## API Highlights

- `GET /object_info`
- `GET /object_info/{node_id}`
- `POST /workflow/validate`
- `POST /runs`
- `GET /runs`
- `GET /runs/{run_id}`
- `POST /runs/{run_id}/interrupt`
- `GET /queue`
- `POST /queue/clear`
- `GET /history`
- `GET /ws`
- `POST /prompt` compatibility-style endpoint

## Tests

```bash
pytest
```

## Limitations

- Conda, Docker, Apptainer, HPC/SLURM, Snakemake export, Nextflow export, CWL/WDL export, and public node registries are schema/design placeholders only.
- Real execution currently uses local `PATH`.
- The frontend is a static React Flow app served from CDN for MVP simplicity.
- Cache keys use paths, sizes, modified times, small-file SHA256, params, node versions, command templates, and upstream keys. Large FASTQ/BAM hashing is intentionally avoided by default.
