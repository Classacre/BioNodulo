#!/usr/bin/env bash
set -euo pipefail

echo "=== BioNodulo devcontainer setup ==="

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Install R
echo "Installing R..."
sudo apt-get update
sudo apt-get install -y --no-install-recommends r-base r-base-dev

# Install project Python deps
echo "Installing Python dependencies..."
uv sync --frozen

# Install frontend deps
echo "Installing frontend dependencies..."
cd web && npm ci

echo "=== Setup complete ==="
echo "From the repository root, run 'make dev' to start the API and frontend."
