# Development

Use Python 3.11 or newer and the Node.js version in [`.nvmrc`](../.nvmrc).
Run commands from the repository root unless a step says otherwise.

## Install

Create and activate a virtual environment, then install the development tools:

```sh
python -m venv .venv
# PowerShell: .venv\Scripts\Activate.ps1
# POSIX shell: source .venv/bin/activate
python -m pip install -e ".[dev]"
cd web
npm ci
```

Alternatively, `uv sync --locked` installs the same development dependencies
from `uv.lock`. The `dev` group reuses the package's `dev` extra.

## Run

Use two terminals, with the Python environment activated in the first:

```sh
python main.py --dev --port 8765 --project-root workspace
```

```sh
cd web
npm run dev
```

Open the Vite URL printed in the second terminal (normally port 5173).
Its API proxy targets the backend on port 8765. To serve a production frontend
from the backend, run `npm run build` in `web/`, then `python main.py` from the
repository root and open port 8000.

The [Makefile](../Makefile) provides equivalent commands for a POSIX shell:
`make dev`, `make lint`, `make test`, `make build` and `make verify`.

## Checks

| Area | Command | Directory |
| --- | --- | --- |
| Python tests | `python -m pytest tests/ -q --tb=short` | repository root |
| Python lint | `python -m ruff check bionodulo tests` | repository root |
| Python type-check baseline | `python scripts/mypy_ratchet.py` | repository root |
| Frontend tests | `npm test` | `web/` |
| Frontend lint | `npm run lint` | `web/` |
| Frontend types and build | `npm run build` | `web/` |
| Browser tests | `npm run test:e2e` | `web/` |
| Desktop packaging inputs | `node --test desktop/scripts/backend-files.test.mjs` | repository root |

The type-check ratchet updates `.mypy-baseline` when the error count decreases.
CI pins lint/type-check tool versions in
[its workflow](../.github/workflows/ci.yml); use those versions when reproducing
a CI failure. Limit pytest workers on machines with little available memory.

For a node change, run the affected node-family tests and follow the
[verification guide](testing/node-verification.md). A unit-test pass alone does
not establish that an external biological tool produces correct results.

## Repository hygiene

Put maintained guides under `docs/` and reusable utilities under `scripts/`.
Use ignored `artifacts/` for local screenshots and QA output, and `workspace/`
or `runs/` for execution results. Keep credentials in local environment/config
files. Do not commit caches, temporary plans, copied source trees or build output.

Generated runtime catalogs, environment locks, small test fixtures and dated
scientific receipts are intentional tracked artifacts. See the
[script index](../scripts/README.md) and [report index](../reports/README.md)
before regenerating or removing them.
