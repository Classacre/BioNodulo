# BioNodulo native plugins

`bionodulo/` is a portable Agent Plugins package for the authenticated remote MCP endpoint at `https://bionodulo.com/api/mcp`. It includes a Claude Code manifest and MCP config in the same folder. The repo has install catalogs at `.agents/plugins/marketplace.json` for Codex/ChatGPT and `.claude-plugin/marketplace.json` for Claude Code. Installing the plugin lets the host handle user OAuth; no API token or Clerk backend credential belongs in these manifests.

From this repository, validate the Claude Code package and marketplace with:

```sh
claude plugin validate ./integrations/bionodulo --strict
claude plugin validate . --strict
```

Register the public repository as a marketplace with `claude plugin marketplace add Classacre/BioNodulo`, then install `bionodulo@bionodulo-repo` with `claude plugin install bionodulo@bionodulo-repo`. For Codex, run `codex plugin marketplace add Classacre/BioNodulo`, then choose the `bionodulo-repo` source in the Plugins Directory. These repository marketplaces are separate from any public directory listing. The [portable plugin ZIP](https://github.com/Classacre/BioNodulo/releases/download/plugin-v0.1.0/bionodulo-plugin-0.1.0.zip) is also available as a release asset. An authenticated end-to-end test still requires the OAuth service to be live.

`claude-desktop/` is a separate MCPB for the **running local BioNodulo desktop app**. It packages the project MCP implementation in desktop-only mode. The extension exposes only `desktop_*` tools on the fixed loopback address `127.0.0.1:8765` and has no cloud account access. Download the [Claude Desktop extension (.mcpb)](https://github.com/Classacre/BioNodulo/releases/download/plugin-v0.1.0/bionodulo-desktop-0.1.0.mcpb) and install it in Claude Desktop **Settings → Extensions**. UV downloads the pinned Python dependencies on first launch; the desktop app must be running for the tools to work. For cloud account tools in Claude Desktop, use its remote custom connector to `https://bionodulo.com/api/mcp`.

Build inspectable archives with:

```sh
python mcp/scripts/build_native_plugins.py
```

The reproducible ZIP and MCPB are written to ignored `integrations/dist/`. The build checks manifest identity, URL, marketplace paths, desktop-only mode, and source availability. `python mcp/scripts/build_native_plugins.py --check` validates without writing. Run `python -m pytest mcp/tests/test_native_plugins.py -q` for packaging tests. For host validation, `npx @anthropic-ai/mcpb validate integrations/claude-desktop/manifest.json` and `npx @anthropic-ai/mcpb info integrations/dist/bionodulo-desktop-0.1.0.mcpb` inspect the Claude Desktop bundle.

References: [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins), [Claude Code plugin manifests](https://code.claude.com/docs/en/plugins-reference), [Claude Code marketplaces](https://code.claude.com/docs/en/plugin-marketplaces), and [MCPB format](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md).
