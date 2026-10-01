<p align="center">
  <img src=".github/assets/logo.svg" alt="BioNodulo logo" width="96" />
</p>

<h1 align="center">BioNodulo</h1>

<p align="center">
  <strong>Build, run and share bioinformatics workflows — node by node.</strong><br />
  Desktop · Cloud · Your AI assistant
</p>

<p align="center">
  <a href="https://github.com/Classacre/BioNodulo/releases"><img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FClassacre%2FBioNodulo%2Fmain%2Fweb%2Fpackage.json&amp;query=%24.version&amp;label=version&amp;color=0d9488&amp;style=flat-square" alt="Current app version" /></a>
  <a href="https://github.com/Classacre/BioNodulo/actions/workflows/ci.yml"><img src="https://github.com/Classacre/BioNodulo/actions/workflows/ci.yml/badge.svg?branch=main" alt="Main branch CI status" /></a>
  <a href="https://github.com/Classacre/BioNodulo/actions/workflows/secret-scan.yml"><img src="https://github.com/Classacre/BioNodulo/actions/workflows/secret-scan.yml/badge.svg?branch=main" alt="Secret scanning status" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Classacre/BioNodulo?color=2563eb&amp;style=flat-square" alt="GPL-3.0 license" /></a>
  <a href="desktop/README.md"><img src="https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux-475569?style=flat-square" alt="Desktop platforms: Windows, macOS and Linux" /></a>
</p>

<p align="center">
  <a href="https://cloud.bionodulo.com/build/"><img src="https://img.shields.io/badge/Open_Cloud_App-0d9488?style=for-the-badge" alt="Open the cloud app" /></a>
  <a href="https://bionodulo.com/download"><img src="https://img.shields.io/badge/Download_Desktop-2563eb?style=for-the-badge" alt="Download the desktop app" /></a>
  <a href="https://docs.bionodulo.com"><img src="https://img.shields.io/badge/Read_the_Docs-475569?style=for-the-badge" alt="Read the documentation" /></a>
  <a href="https://docs.bionodulo.com/mcp/clients"><img src="https://img.shields.io/badge/Connect_Your_AI-7c3aed?style=for-the-badge" alt="Connect your AI assistant" /></a>
</p>

BioNodulo is an open-source visual workflow editor for bioinformatics. Connect
tools on a canvas, explore their relationships, manage inputs and references,
and follow execution through node status, logs and outputs. Work in the desktop
app, the hosted cloud editor, or a supported AI client's embedded cloud app.

<p align="center">
  <img src=".github/assets/screenshots/cloud-app-mcp.png" alt="BioNodulo full cloud editor with a sample counts workflow, cloud account controls and console" width="900" /><br />
  <em>The shared cloud editor, shown with sample data in an MCP test host.</em>
</p>

## What you can do

| | Capability |
| --- | --- |
| **Build visually** | Connect typed inputs and outputs, organize workflow tabs, and start from bundled templates. |
| **Explore tools** | Search the node library and use [Tool Atlas](docs/tool-atlas.md) to inspect related tools, format matches and recorded evidence. |
| **Run where you work** | Use desktop/local and HPC integrations, or cloud compute with an account and team credit balance. |
| **Work with your AI** | Let an authorized assistant inspect the catalog, edit workflows, manage cloud files and monitor runs through MCP. |
| **Track results** | Follow node status and logs, then retrieve verified cloud outputs and reported run usage. |
| **Share and reproduce** | Collaborate on workflows, export supported formats, and collect tool references with the reference manager/exporter. |

The catalog distinguishes executable nodes from **reference-only bio.tools
entries**. Tool Atlas relationships are discovery aids, not proof of scientific
compatibility. See [tool integration profiles](docs/tool-integration.md) and
the [template catalog](docs/templates.md) for coverage and execution requirements.

## BioNodulo inside your AI client

Connect your client to the remote MCP endpoint:

```text
https://bionodulo.com/api/mcp
```

Sign in to BioNodulo, authorize the account/team permissions you need, then ask
your assistant: **“Open BioNodulo.”** In ChatGPT and Claude hosts that support
MCP Apps, this opens the **same full cloud app**: canvas, workflow tabs, toolbox,
templates, cloud Workspace, settings and run history. Its AI panel sends your
request to the host assistant; saved workflow changes appear in the editor.

<p align="center">
  <a href="https://docs.bionodulo.com/mcp/clients#chatgpt"><img src="https://img.shields.io/badge/ChatGPT-Connect-0d9488?style=for-the-badge" alt="ChatGPT connection guide" /></a>
  <a href="https://docs.bionodulo.com/mcp/clients#claude"><img src="https://img.shields.io/badge/Claude-Connect-D97757?style=for-the-badge&amp;logo=claude&amp;logoColor=white" alt="Claude connection guide" /></a>
  <a href="https://docs.bionodulo.com/mcp/clients#codex"><img src="https://img.shields.io/badge/Codex-Connect-475569?style=for-the-badge" alt="Codex connection guide" /></a>
  <a href="https://docs.bionodulo.com/mcp/clients#claude-code"><img src="https://img.shields.io/badge/Claude_Code-Connect-7c3aed?style=for-the-badge" alt="Claude Code connection guide" /></a>
</p>

Codex, Claude Code and other MCP clients can use the same cloud tools without
embedded UI. Cloud files belong to the authorized account/team; the remote
connector does not access your computer's filesystem. Read, write and run
permissions are separate. Paid cloud runs require explicit credit authorization;
the embedded app checks the current balance and compute estimate before each
submission, then shows progress, logs and verified outputs.

Use the [AI client setup guide](https://docs.bionodulo.com/mcp/clients) for
host-specific installation and permissions. The [portable plugin and repository
marketplaces](integrations/README.md) package the remote connection. A separate
[Claude Desktop extension](mcp/README.md#local-desktop-connection) connects to a
running local BioNodulo desktop app. Embedded UI availability depends on the
host; native ChatGPT/Claude rendering has not yet been verified for this release.

## Get started

| Choose your setup | Start here |
| --- | --- |
| **Cloud editor** | [Open BioNodulo](https://cloud.bionodulo.com/build/) and sign in to your account. |
| **Desktop app** | [Download for Windows, macOS or Linux](https://bionodulo.com/download). See [desktop setup](desktop/README.md). |
| **AI client** | [Connect ChatGPT, Claude, Codex or Claude Code](https://docs.bionodulo.com/mcp/clients). |
| **Notebook trial** | [Open in Colab](https://colab.research.google.com/github/Classacre/BioNodulo/blob/main/notebooks/BioNodulo_Colab.ipynb). |
| **From source** | Follow the commands below and the [development guide](docs/development.md). |

Workflow import/export support varies by format and node. Native Nextflow and
Snakemake conversion currently covers FastQC/MultiQC workflows; unsupported
graphs are rejected explicitly.

### Run from source

Use Python 3.11+ and Node.js 24 (see [`.nvmrc`](.nvmrc)). In an activated
Python virtual environment:

```sh
python -m pip install -e .
cd web
npm ci
npm run build
cd ..
python main.py
```

Open `http://localhost:8000`. Bioinformatics commands need their declared tool
environments; some workflows also need reference datasets or external services.
See [development setup](docs/development.md) for live reload, tests and checks,
and [Windows execution](docs/desktop/windows-local-execution.md) for WSL setup.

## Repository map

| Path | Contents |
| --- | --- |
| `bionodulo/` | Python API, node catalog, workflow engine and integrations |
| `web/` | React/TypeScript editor built with Vite |
| `desktop/` | Tauri desktop app and packaging |
| `mcp/` | MCP server and client installation instructions |
| `templates/` | Bundled workflows, thumbnails and small smoke-test inputs |
| `examples/`, `notebooks/` | Example workflows and Colab launcher |
| `tests/` | Backend tests and fixtures; frontend tests live in `web/` |
| `scripts/` | Catalog generation, validation and maintenance commands |
| `docs/` | Architecture, development and feature guides |
| `reports/` | Dated measurements and reproducible evidence |
| `data/` | Committed research/example datasets |
| `alembic/` | Database migration configuration |

`main.py` starts the application and `server.py` assembles the FastAPI services.
Local runs, workspaces, environments and build output are ignored by Git.
The hosted website, documentation site and cloud infrastructure are maintained
in the separate `bionodulo-website` repository.

## Developer guides

- [Documentation index](docs/README.md)
- [Tool Atlas](docs/tool-atlas.md) and [builtin expansion handbook](docs/builtin-expansion-playbook.md)
- [Architecture](docs/architecture.md)
- [Development and checks](docs/development.md)
- [Maintenance scripts](scripts/README.md)
- [Desktop app](desktop/README.md)
- [MCP connections](mcp/README.md), [native plugins](integrations/README.md) and [cloud app adapter](web/src/mcp/README.md)
- [Custom nodes](docs/help/custom-nodes.md)

## Community

<p align="center">
  <a href="https://discord.gg/baNKVhZq6k"><img src="https://img.shields.io/badge/Discord-Join_the_Community-5865F2?style=for-the-badge&amp;logo=discord&amp;logoColor=white" alt="Join the BioNodulo Discord community" /></a>
  <a href="https://github.com/Classacre/BioNodulo/issues"><img src="https://img.shields.io/badge/GitHub-Report_an_Issue-181717?style=for-the-badge&amp;logo=github&amp;logoColor=white" alt="Report an issue on GitHub" /></a>
  <a href="https://colab.research.google.com/github/Classacre/BioNodulo/blob/main/notebooks/BioNodulo_Colab.ipynb"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open the BioNodulo notebook in Colab" /></a>
</p>

## License

[GNU General Public License v3](LICENSE). Third-party tools, datasets,
containers, models and services retain their own license terms; see
[Third-Party Notices](THIRD_PARTY_NOTICES.md).
