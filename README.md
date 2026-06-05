# BioNodulo 2.0

**Visual bioinformatics pipelines, node by node.**

BioNodulo is a professional-grade visual workflow workbench for bioinformatics. Build, execute, and share complex bioinformatics pipelines using an intuitive node-based graph editor.

[![Version](https://img.shields.io/badge/version-2.0-0d9488?logo=github)](pyproject.toml)
[![Discord](https://img.shields.io/badge/Discord-Join%20BioNodulo-5865F2?logo=discord&logoColor=white)](https://discord.gg/baNKVhZq6k)
[![License](https://img.shields.io/badge/license-Closed%20Alpha%20Commercial-f59e0b)](LICENSE)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Classacre/BioNodulo/blob/protobionodulo/notebooks/BioNodulo_Colab.ipynb)

## Features

- **Visual Node Editor** — Drag-and-drop canvas for building workflows with ~90 built-in bioinformatics nodes
- **90+ Bioinformatics Nodes** — Covering QC, alignment, variant calling, assembly, RNA-Seq, metagenomics, phylogenetics, ChIP-Seq, single-cell analysis, BioPython integration, R scripting, and more
- **10 Pre-built Templates** — FASTQ QC, RNA-Seq, Variant Calling, Metagenomics, Assembly, Phylogenetics, ChIP-Seq, Differential Expression, WGS Variant, Single Cell
- **HPC Integration** — Submit workflows to SLURM, PBS/Torque, or SGE clusters with a single toggle
- **Workflow Converters** — Import and export workflows between SnakeMake, NextFlow, CWL, Galaxy, and BioNodulo JSON formats
- **Settings System** — Per-user settings with categories for appearance, canvas, execution, LLM, and files
- **Help / Wiki System** — Built-in searchable documentation panel (Ctrl+6)
- **AI Assistant** — Chat-based workflow builder assistant
- **Environment Manager** — Auto-detect missing dependencies, one-click install, Conda/Mamba/Micromamba env CRUD, Docker/Apptainer support, per-workflow isolation
- **Dependency Resolution** — Scans workflows on open for missing nodes, executables, and Python packages with a top-center banner + Auto Install
- **Custom Nodes** — Extensible plugin system; nodes declare `GIT_URL` for automatic source discovery and installation
- **Dark/Light Theme** — Full theme support with system detection
- **Multi-tab Workflows** — Work on multiple workflows simultaneously with top tabs
- **Undo/Redo** — Full history support

## Quick Start

### Google Colab

For an ephemeral notebook-based trial, launch the Colab notebook:

[Open BioNodulo in Google Colab](https://colab.research.google.com/github/Classacre/BioNodulo/blob/protobionodulo/notebooks/BioNodulo_Colab.ipynb)

The notebook checks out `origin/protobionodulo`, prints the active branch and commit with `git status -sb` and `git log -1 --oneline --decorate`, installs the backend dependencies, builds the web frontend, starts BioNodulo in the Colab runtime, and prints a temporary Cloudflare Tunnel URL while the launch cell keeps running.

If Colab still shows an older BioNodulo version, restart or delete the Colab runtime and rerun the setup cell. The printed Git commit should match the latest `protobionodulo` commit in this repository.

### Prerequisites

**Required on host PATH:**
- **Python 3.11+** — runs the FastAPI backend
- **micromamba** — creates isolated per-category conda environments for bioinformatics tools (auto-installed on first startup if missing)

**Required to build or develop the frontend:**
- **Node.js 20+ + npm** — builds the React/Vite frontend into `web/dist/`

**Required only for R-based workflows:**
- **Rscript** — needed by nodes such as DESeq2, ggplot2, pheatmap, edgeR, etc.

### Installation

```bash
# Clone or extract the project
cd bionodulo-v2

# Install Python dependencies
pip install -e .

# Build the frontend
cd web && npm install && npm run build
cd ..
```

### Running

```bash
# Start the server
python main.py

# Or with options
python main.py --host 0.0.0.0 --port 8000 --project-root ./workspace

# Development mode with auto-reload
python main.py --dev

# With custom config
python main.py --config bionodulo.yaml
```

Then open http://localhost:8000 in your browser.

### Using HPC Mode

1. Click the **HPC** toggle in the top bar
2. Open the HPC panel (Ctrl+5) and configure your scheduler
3. Set partition, account, resources, and modules
4. Click **Test Connection** to verify
5. Run your workflow — it will be submitted as a batch job

### Importing Workflows

Click the **Import** button in the top bar (Ctrl+I) and paste workflow code from:
- SnakeMake (.smk)
- NextFlow (.nf)
- CWL (.cwl)
- Galaxy (.ga)
- BioNodulo JSON (.json)

### Creating Custom Nodes

1. Copy `custom_nodes/example_node.py.example` to `custom_nodes/my_node.py`
2. Edit the node class with your tool's parameters
3. Set `GIT_URL` (and optionally `GIT_COMMIT`) so BioNodulo can auto-install your node when it's missing
4. Restart BioNodulo — your node appears in the palette automatically

### Managing Environments

BioNodulo automatically checks for missing dependencies every time you open or load a workflow:

1. **Auto-detect** — Open any template or workflow. If nodes or tools are missing, a top-center banner appears
2. **Auto Install** — Click **Auto Install** in the banner to clone custom nodes and `conda install` missing executables automatically
3. **Environment Panel** (Ctrl+4) — Browse existing Conda environments, create new ones, delete old ones, and view installed packages
4. **Dependency Tree** — See per-workflow dependency status (installed / missing / available in which env)
5. **Isolate Workflow** — Create a dedicated Conda environment containing only the tools your current workflow needs

## Project Structure

```
bionodulo-v2/
├── main.py                    # Entry point
├── server.py                  # FastAPI app
├── pyproject.toml             # Package metadata
├── bionodulo.yaml.example     # Configuration template
├── Dockerfile                 # Container build
├── SPEC.md                    # Technical specification
├── bionodulo/                 # Backend package
│   ├── core/                  # Config, events, paths
│   ├── api/                   # REST API routes, WebSocket
│   ├── nodes/                 # Node system
│   │   ├── builtin/           # 90+ bioinformatics nodes
│   │   ├── base.py            # BaseNode class
│   │   ├── command_node.py    # External tool wrapper
│   │   ├── registry.py        # Node discovery & loading
│   │   └── schema_api.py      # Node schema definitions
│   ├── execution/             # Execution engine
│   ├── workflow/              # Workflow validation, serialization
│   ├── converter/             # SnakeMake, NextFlow, CWL, Galaxy
│   ├── hpc/                   # SLURM, PBS, SGE backends
│   ├── environments/          # Conda, Docker, Apptainer, env CRUD
│   │   ├── conda.py
│   │   ├── containers.py
│   │   ├── model.py
│   │   └── manager.py         # Environment lifecycle management
│   ├── manager/               # Custom nodes, diagnostics, dependency resolution
│   │   ├── resolver.py        # Workflow dependency resolution engine
│   │   ├── installer.py       # Async install jobs with progress tracking
│   │   ├── custom_nodes.py
│   │   └── diagnostics.py
│   ├── provenance/            # Workflow embedding, reports
│   └── ai/                    # AI assistant
├── custom_nodes/              # Your custom nodes
├── templates/                 # 10 pre-built workflow templates
├── envs/                      # Generated per-workflow environments (ignored)
├── examples/workflows/        # Example workflows
├── cache/                     # Runtime cache
├── runs/                      # Execution outputs
└── web/                       # Frontend (React + Vite)
    ├── dist/                  # Generated frontend build output
    └── src/                   # Source code
```

## Optional Production Integrations

BioNodulo runs locally with no external services. For larger deployments you can opt into battle-tested infrastructure:

- **Redis** — set `BIONODULO_REDIS_URL` to replicate Yjs document updates and awareness across multiple backend instances.
- **OIDC / Keycloak / SuperTokens** — set `BIONODULO_OIDC_ISSUER`, `BIONODULO_OIDC_AUDIENCE`, and optionally `BIONODULO_OIDC_JWKS_URL` to accept externally issued JWTs.
- **LiteLLM Proxy** — choose the `litellm` AI provider and set `BIONODULO_LITELLM_BASE_URL` plus `LITELLM_API_KEY` to route models through a provider gateway.
- **SlowAPI** — REST rate limiting is enabled by default; set `BIONODULO_RATE_LIMIT_REDIS_URL` or `BIONODULO_REDIS_URL` to share rate-limit state between instances.

## Node Categories

| Category | Nodes | Description |
|----------|-------|-------------|
| Input | FASTQ, FASTA, VCF, GFF, File, Directory, Sample Sheet | Data loading nodes |
| Quality Control | FastQC, MultiQC, QualiMap | Sequence quality assessment |
| Read Preprocessing | fastp, Trimmomatic, Cutadapt | Adapter trimming and filtering |
| Alignment | BWA, Bowtie2, Minimap2, STAR, HISAT2 | Read alignment (including index builders) |
| SAM/BAM Processing | samtools sort, index, flagstat, view, merge, stats | Alignment processing |
| Variant Calling | GATK, bcftools, FreeBayes, VCFtools | SNP/indel detection |
| Assembly | SPAdes, MEGAHIT, Flye, Canu, Unicycler, QUAST | Genome assembly |
| Annotation | Prokka, Bakta, eggNOG | Genome annotation |
| Phylogenetics | MAFFT, ClustalΩ, IQ-TREE, FastTree, RAxML | Tree construction |
| RNA-Seq | Salmon, Kallisto, featureCounts, StringTie | Expression analysis |
| Metagenomics | Kraken2, Bracken, MetaPhlAn, HUMAnN, MaxBin, CheckM | Microbial profiling |
| ChIP-Seq | MACS2, BEDTools, deepTools | Peak calling and coverage |
| Single Cell | Cell Ranger | scRNA-seq analysis |
| HPC | Job Submit, Status Check | Cluster job submission |
| BioPython | SeqIO, BLAST, MSA, Sequence Stats | Python bioinformatics tools |
| R Integration | R Script, R Plot, DataFrame Builder | R statistical computing |
| Utility | Generic Command, View Text, Collect Files, Merge VCF, Note, Reroute | Helper nodes |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+F | Open node palette |
| Ctrl+R | Run workflow |
| Ctrl+E | Export workflow |
| Ctrl+I | Import workflow |
| Ctrl+Z | Undo |
| Ctrl+Y / Ctrl+Shift+Z | Redo |
| Ctrl+A | Select all nodes |
| Ctrl+G | Group selected nodes |
| Alt+C | Collapse/expand selected nodes |
| Delete | Delete selected nodes |
| Ctrl+1–7 | Toggle left rail panels |
| Ctrl+6 | Open Help / Wiki |
| Ctrl+, | Open Settings |
| Ctrl+` | Toggle bottom console |
| Middle-click drag | Pan canvas |
| Alt+click drag | Pan canvas |
| Double-click node | Edit node parameters |
| Right-click canvas | Open node palette |

## Configuration

Copy `bionodulo.yaml.example` to `bionodulo.yaml` and customize:

```yaml
project_root: ./bionodulo_workspace
runs_dir: ./runs
cache_dir: ./cache
custom_nodes_dir: ./custom_nodes
data_roots: ["./data"]

# External tool paths (leave empty to use PATH)
tool_paths:
  bwa: /usr/bin/bwa
  samtools: /usr/bin/samtools
  fastqc: /usr/bin/fastqc
  multiqc: /usr/bin/multiqc
  gatk: /opt/gatk/gatk
  bcftools: /usr/bin/bcftools
  bowtie2: /usr/bin/bowtie2
  minimap2: /usr/bin/minimap2
  star: /usr/bin/STAR
  hisat2: /usr/bin/hisat2
  spades: /usr/bin/spades.py
  megahit: /usr/bin/megahit
  kraken2: /usr/bin/kraken2
  macs2: /usr/bin/macs2
  cellranger: /opt/cellranger/cellranger

# Conda/Mamba configuration
conda:
  executable: micromamba  # conda, mamba, or micromamba
  channels: [bioconda, conda-forge]

# Container configuration
containers:
  default_runtime: apptainer  # docker or apptainer
  default_image: null

# HPC configuration
hpc:
  enabled: false
  backend: slurm  # slurm, pbs, sge
  partition: normal
  account: null
  walltime: "01:00:00"
  cpus_per_task: 4
  mem_per_cpu: "4G"
  modules: []
  extra_args: ""

# API configuration
api:
  host: "127.0.0.1"
  port: 8000

# LLM configuration
llm:
  provider: openai
  model: gpt-4.1-mini
  base_url: ""
  api_key: ""
  temperature: 0.2

# Execution settings
execution:
  stop_on_error: true
  max_parallel_jobs: 4

# Security
api_secrets: {}
```

## License

BioNodulo is paid software distributed under the [BioNodulo Closed Alpha Commercial License](LICENSE).

Access during the current closed-alpha development phase is limited to authorized users and institutions with a written license, trial agreement, or closed-alpha invitation. BioNodulo may not be freely redistributed, mirrored, sublicensed, hosted for third parties, or used outside the licensed scope.

Third-party open-source and proprietary dependencies, command-line tools, datasets, containers, models, APIs, and services remain subject to their own license terms. See [Third-Party Notices](THIRD_PARTY_NOTICES.md) for the current compliance summary. Institutions can contact `nieuwenhuyzemikamartin@gmail.com` to discuss licensing and pricing.

BioNodulo is an independent bioinformatics workflow platform built specifically for bioinformatics pipeline design, execution, and sharing.
