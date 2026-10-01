# BioNodulo native plugins

`bionodulo/` is a portable Agent Plugins package for the authenticated remote MCP endpoint at `https://bionodulo.com/api/mcp`. It includes a Claude Code manifest and MCP config in the same folder. The repo has install catalogs at `.agents/plugins/marketplace.json` for Codex/ChatGPT and `.claude-plugin/marketplace.json` for Claude Code. Installing the plugin lets the host handle user OAuth; no API token or Clerk backend credential belongs in these manifests.

After connecting, ask ChatGPT or Claude to **open BioNodulo**. The `open_bionodulo` tool loads the full cloud app through MCP Apps when the host renders interactive connector UI. It uses the same editor, navigation, workflow tabs, toolbox, cloud workspace, templates, settings and run history as the hosted app. An MCP adapter connects these shared components to the authorized cloud account; cloud files replace local filesystem access. The shared AI panel sends messages to the host assistant, and saved workflow changes made by the assistant appear in the editor.

The same account-scoped workflow, catalog, validation, file, and run tools remain available in clients without embedded UI. The cloud connector cannot control local files, the desktop app, HPC jobs, or administrator settings. Starting a paid cloud run still requires the user's explicit authorization of the team, workflow, and compute credits; `submit_run` requires `bionodulo:run` and literal `confirm_credit_use: true`. The embedded app separately reviews the live balance and matching CPU/GPU estimate before each submission.

From this repository, validate the Claude Code package and marketplace with:

```sh
claude plugin validate ./integrations/bionodulo --strict
claude plugin validate . --strict
```

Register the public repository as a marketplace with `claude plugin marketplace add Classacre/BioNodulo`, then install `bionodulo@bionodulo-repo` with `claude plugin install bionodulo@bionodulo-repo`. For Codex, run `codex plugin marketplace add Classacre/BioNodulo`, then choose the `bionodulo-repo` source in the Plugins Directory. These repository marketplaces are separate from any public directory listing. The [portable plugin ZIP](https://github.com/Classacre/BioNodulo/releases/download/plugin-v0.1.1/bionodulo-plugin-0.1.1.zip) is also available as a release asset. An authenticated end-to-end test still requires the OAuth service to be live.

`claude-desktop/` is a separate MCPB for the **running local BioNodulo desktop app**. It packages the project MCP implementation in desktop-only mode. The extension exposes only `desktop_*` tools on the fixed loopback address `127.0.0.1:8765` and has no cloud account access. Download the [Claude Desktop extension (.mcpb)](https://github.com/Classacre/BioNodulo/releases/download/plugin-v0.1.0/bionodulo-desktop-0.1.0.mcpb) and install it in Claude Desktop **Settings → Extensions**. UV downloads the pinned Python dependencies on first launch; the desktop app must be running for the tools to work. For cloud account tools in Claude Desktop, use its remote custom connector to `https://bionodulo.com/api/mcp`.

Build the updated portable plugin without changing the released desktop extension:

```sh
python mcp/scripts/build_native_plugins.py --plugin-only
```

The reproducible ZIP and MCPB are written to ignored `integrations/dist/`. Running the script without `--plugin-only` builds both archives when issuing a new desktop extension. The portable plugin and desktop extension have independent versions (currently 0.1.1 and 0.1.0). An existing archive is retained if identical and rejected if its contents differ, so a released version is never silently replaced. The build checks manifest identity, URL, marketplace paths, desktop-only mode, and source availability. `python mcp/scripts/build_native_plugins.py --check` validates without writing. Run `python -m pytest mcp/tests/test_native_plugins.py -q` for packaging tests. For host validation, `npx @anthropic-ai/mcpb validate integrations/claude-desktop/manifest.json` and `npx @anthropic-ai/mcpb info integrations/dist/bionodulo-desktop-0.1.0.mcpb` inspect the Claude Desktop bundle.

References: [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins), [OpenAI MCP Apps UI](https://developers.openai.com/plugins/build/chatgpt-ui), [Claude interactive connectors](https://support.claude.com/en/articles/13454812-use-interactive-connectors-in-claude), [Claude Code plugin manifests](https://code.claude.com/docs/en/plugins-reference), [Claude Code marketplaces](https://code.claude.com/docs/en/plugin-marketplaces), and [MCPB format](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md).
