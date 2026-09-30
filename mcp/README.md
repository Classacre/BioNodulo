# BioNodulo MCP connections

For normal account access, connect your AI client to BioNodulo's remote MCP server:

```text
https://bionodulo.com/api/mcp
```

The client starts a browser sign-in. Authorize the requested access to your BioNodulo account and team. You do not need to copy a Clerk session token or receive a Clerk backend secret. Read, write, and run actions use separate OAuth permissions, and each request is checked against the account and selected team. A default login may grant read access only; reconnect with `bionodulo:write` or `bionodulo:run` when needed. Starting a run requires the user's authorization to use that team's credits.

See the [client guide](https://docs.bionodulo.com/mcp/clients) for ChatGPT, Claude, Codex, and Claude Code setup. The remote endpoint exposes cloud tools only; it cannot reach a desktop app running on your computer.

## Local desktop connection

The Python package in this directory provides a local MCP server for desktop tools such as node inspection, local queue status, and local runs. It talks to a BioNodulo desktop backend on the same computer (default `http://127.0.0.1:8765`). A local Claude Desktop `.mcpb` extension can be built with:

```bash
python mcp/scripts/build_native_plugins.py
```

The [Claude Desktop extension download](https://github.com/Classacre/BioNodulo/releases/download/plugin-v0.1.0/bionodulo-desktop-0.1.0.mcpb) is the release build. Install it in Claude Desktop **Settings → Extensions**. It exposes only the local `desktop_*` tools; use the remote connector for cloud data. The portable plugin [release ZIP](https://github.com/Classacre/BioNodulo/releases/download/plugin-v0.1.0/bionodulo-plugin-0.1.0.zip) contains the cloud integration for supported plugin hosts. Sources live in `integrations/bionodulo/`; repository marketplace catalogs are under `.agents/plugins/` and `.claude-plugin/`.

For source development, install this Python package with `uv sync` from the `mcp/` directory and use `uv run bionodulo-mcp` for stdio. The desktop app must be running for `desktop_*` tools to work.

## Developer and operator configuration

The legacy Python server can also call BioNodulo cloud APIs. Its `CLERK_SECRET_KEY` plus `BIONODULO_USER_EMAIL` or `BIONODULO_USER_ID` flow uses a **backend administrator secret** to mint session tokens. It is an advanced server-operator path, not user connection setup. Keep that secret in trusted server infrastructure; never put it in AI client configuration, an extension bundle, or documentation examples for end users. A fixed `BIONODULO_AUTH_TOKEN` is short-lived and likewise unsuitable as a general connection method.

For developer reference, the package supports `BIONODULO_API_URL`, `BIONODULO_DESKTOP_URL`, `BIONODULO_DESKTOP`, and `BIONODULO_TEAM_ID`. Its optional HTTP transport can be protected with `BIONODULO_MCP_TOKEN`, but that legacy transport does not replace the public account-based OAuth endpoint above. The legacy package also includes cloud tools, three `bionodulo://` resources, and guided prompts; see its source modules for exact capabilities.

No live client or desktop operation is implied by building the package or installing a connector. Verify the connection and requested tools in the AI client after setup.
