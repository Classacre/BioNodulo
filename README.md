# BioNodulo Alpha 1.0

**Visual bioinformatics pipelines, node by node.**

BioNodulo is a professional-grade visual workflow workbench for bioinformatics. Build, execute, and share complex bioinformatics pipelines using an intuitive node-based graph editor inspired by ComfyUI.

## Features

- **Visual Node Editor** — Drag-and-drop canvas for building workflows with ~90 built-in bioinformatics nodes
- **90+ Bioinformatics Nodes** — Covering QC, alignment, variant calling, assembly, RNA-Seq, metagenomics, phylogenetics, ChIP-Seq, single-cell analysis, BioPython integration, R scripting, and more
- **10 Pre-built Templates** — FASTQ QC, RNA-Seq, Variant Calling, Metagenomics, Assembly, Phylogenetics, ChIP-Seq, Differential Expression, WGS Variant, Single Cell
- **HPC Integration** — Submit workflows to SLURM, PBS/Torque, or SGE clusters with a single toggle
- **Workflow Converters** — Import and export workflows between SnakeMake, NextFlow, CWL, Galaxy, and BioNodulo JSON formats
- **Settings System** — ComfyUI-inspired per-user settings with categories (Appearance, Canvas, Execution, LLM, Files)
- **Help / Wiki System** — Built-in searchable documentation panel (Ctrl+6)
- **AI Assistant** — Chat-based workflow builder assistant
- **Environment Manager** — Conda, Mamba, Micromamba, Docker, and Apptainer support
- **Custom Nodes** — Extensible plugin system for adding new tools
- **Dark/Light Theme** — Full theme support with system detection
- **Multi-tab Workflows** — Work on multiple workflows simultaneously with top tabs
- **Undo/Redo** — Full history support

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+ (for frontend development only — pre-built frontend included)

### Installation

```bash
# Clone or extract the project
cd bionodulo-v2

# Install Python dependencies
pip install -r requirements.txt

# The frontend is pre-built in web/dist/
# To rebuild it (optional):
cd web && npm install && npm run build
```

### Running

```bash
# Start the server
python main.py

# Or with options
python main.py --host 0.0.0.0 --port 8000 --project-root ./workspace

# Development mode with auto-reload
python main.py --dev

# Safe mode (mock tool execution)
python main.py --mock-tools

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
3. Restart BioNodulo — your node appears in the palette automatically

## Project Structure

```
bionodulo-v2/
├── main.py                    # Entry point
├── server.py                  # FastAPI app
├── pyproject.toml             # Package metadata
├── requirements.txt           # Python dependencies
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
│   │   ├── schema_api.py      # Node schema definitions
│   │   └── comfy_v3_adapter.py # ComfyUI compatibility
│   ├── execution/             # Execution engine
│   ├── workflow/              # Workflow validation, serialization
│   ├── converter/             # SnakeMake, NextFlow, CWL, Galaxy
│   ├── hpc/                   # SLURM, PBS, SGE backends
│   ├── environments/          # Conda, Docker, Apptainer
│   ├── manager/               # Custom nodes, diagnostics
│   ├── provenance/            # Workflow embedding, reports
│   └── ai/                    # AI assistant
├── custom_nodes/              # Your custom nodes
├── templates/                 # 10 pre-built workflow templates
├── envs/                      # Environment YAML specs
├── examples/workflows/        # Example workflows
├── cache/                     # Runtime cache
├── runs/                      # Execution outputs
└── web/                       # Frontend (React + Vite)
    ├── dist/                  # Pre-built frontend
    └── src/                   # Source code
```

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
  mock_tools_default: false
  stop_on_error: true
  max_parallel_jobs: 4

# Security
api_secrets: {}
```

## License

BioNodulo is an independent bioinformatics workflow platform inspired by the excellent work of the ComfyUI team. It is not a fork of ComfyUI but shares architectural patterns and design philosophy.
