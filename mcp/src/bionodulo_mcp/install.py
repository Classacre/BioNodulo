"""Register the BioNodulo MCP server with local MCP clients.

Writes/merges client configuration for:

- **Codex CLI / Codex IDE / ChatGPT desktop** — ``~/.codex/config.toml``
- **Claude Desktop** — ``claude_desktop_config.json``
- **Claude Code** — via the ``claude mcp add`` CLI when available

Remote clients (ChatGPT web, Claude.ai web) cannot read local config — they
need this server exposed over HTTPS (see README, "Remote access").
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2].as_posix()

PLACEHOLDER_SECRET = "PASTE_SK_LIVE_KEY_HERE"
PLACEHOLDER_EMAIL = "you@example.com"


def _uv_command() -> tuple[str, list[str]]:
    """Resolve the uv executable and the args that launch the server."""
    uv = shutil.which("uv") or shutil.which("uv.exe")
    if uv:
        # Use the absolute path so clients that don't inherit a full shell
        # PATH (e.g. Claude Desktop) can still find it.
        return uv, ["--directory", PROJECT_DIR, "run", "bionodulo-mcp"]
    # Fall back to running the module with the current interpreter.
    return sys.executable, ["-m", "bionodulo_mcp.server"]


def _env_block(clerk_secret_key: str | None, user_email: str | None) -> dict[str, str]:
    return {
        "CLERK_SECRET_KEY": clerk_secret_key or PLACEHOLDER_SECRET,
        "BIONODULO_USER_EMAIL": user_email or PLACEHOLDER_EMAIL,
    }


def _warn_if_placeholders(env: dict[str, str]) -> None:
    missing = [k for k, v in env.items() if v in (PLACEHOLDER_SECRET, PLACEHOLDER_EMAIL)]
    if missing:
        print(
            f"WARNING: {', '.join(missing)} written as placeholders — "
            "edit the generated config to fill in real values, or re-run with "
            "--clerk-secret-key / --user-email."
        )


# ---------------------------------------------------------------------------
# Codex CLI (~/.codex/config.toml)
# ---------------------------------------------------------------------------


def _codex_config_path() -> Path:
    return Path.home() / ".codex" / "config.toml"


def install_codex(env: dict[str, str]) -> None:
    path = _codex_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""

    # Strip any previous [mcp_servers.bionodulo] sections (and subsections).
    kept: list[str] = []
    skipping = False
    for line in existing.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            skipping = stripped.startswith("[mcp_servers.bionodulo")
        if not skipping:
            kept.append(line)
    body = "\n".join(kept).rstrip() + "\n" if kept else ""

    command, args = _uv_command()
    args_toml = ", ".join(json.dumps(a) for a in args)
    env_toml = "\n".join(f'{k} = {json.dumps(v)}' for k, v in env.items())
    block = (
        "\n[mcp_servers.bionodulo]\n"
        f"command = {json.dumps(command)}\n"
        f"args = [{args_toml}]\n"
        "startup_timeout_sec = 30\n"
        "tool_timeout_sec = 120\n"
        "\n[mcp_servers.bionodulo.env]\n"
        f"{env_toml}\n"
    )
    path.write_text(body + block, encoding="utf-8")
    print(f"Codex CLI: wrote [mcp_servers.bionodulo] to {path}")
    print("  Verify with: codex mcp list")


# ---------------------------------------------------------------------------
# Claude Desktop (claude_desktop_config.json)
# ---------------------------------------------------------------------------


def _claude_desktop_config_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "Claude" / "claude_desktop_config.json"


def install_claude_desktop(env: dict[str, str]) -> None:
    path = _claude_desktop_config_path()
    config: dict = {}
    if path.exists():
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = path.with_suffix(".json.bak")
            shutil.copy2(path, backup)
            print(f"  Existing config was not valid JSON; backed up to {backup}")
            config = {}
    command, args = _uv_command()
    config.setdefault("mcpServers", {})["bionodulo"] = {
        "command": command,
        "args": args,
        "env": env,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"Claude Desktop: wrote mcpServers.bionodulo to {path}")
    print("  Restart Claude Desktop to pick it up.")


# ---------------------------------------------------------------------------
# Claude Code (claude mcp add)
# ---------------------------------------------------------------------------


def install_claude_code(env: dict[str, str]) -> None:
    claude = shutil.which("claude")
    command, args = _uv_command()
    if not claude:
        print("Claude Code: 'claude' CLI not found on PATH. Add manually:")
        print(
            "  claude mcp add bionodulo --scope user "
            + " ".join(f"--env {k}={v}" for k, v in env.items())
            + f" -- {command} " + " ".join(args)
        )
        return
    subprocess.run([claude, "mcp", "remove", "bionodulo", "--scope", "user"],
                   capture_output=True)
    cmd = [claude, "mcp", "add", "bionodulo", "--scope", "user"]
    for k, v in env.items():
        cmd += ["--env", f"{k}={v}"]
    cmd += ["--", command, *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("Claude Code: registered 'bionodulo' (user scope)")
        print("  Verify with: claude mcp list")
    else:
        print(f"Claude Code: 'claude mcp add' failed: {result.stderr.strip()}")
        print("  Add manually: " + " ".join(cmd))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def install_clients(
    client: str = "all",
    clerk_secret_key: str | None = None,
    user_email: str | None = None,
) -> None:
    env = _env_block(clerk_secret_key, user_email)
    if client in ("codex", "all"):
        install_codex(env)
    if client in ("claude-desktop", "all"):
        install_claude_desktop(env)
    if client in ("claude-code", "all"):
        install_claude_code(env)
    _warn_if_placeholders(env)
    print()
    print("Remote clients (ChatGPT web, Claude.ai web) need this server over HTTPS:")
    print("  1. uv run bionodulo-mcp serve --transport http --host 0.0.0.0 --port 8787")
    print("  2. Expose it (cloudflared tunnel / ngrok / deploy) at https://<host>/mcp")
    print("  3. Set BIONODULO_MCP_TOKEN to require a bearer token on the endpoint")
    print("  4. ChatGPT: Settings > Apps > Create app (Developer Mode) — paste the /mcp URL")
    print("     Claude.ai: Customize > Connectors > Add custom connector — same URL")
