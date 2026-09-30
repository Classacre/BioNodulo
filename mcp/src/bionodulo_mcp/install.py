"""Register the hosted OAuth endpoint or an explicit personal stdio server."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

PROJECT_DIR = Path(__file__).resolve().parents[2].as_posix()
DEFAULT_REMOTE_URL = "https://bionodulo.com/api/mcp"


def _uv_command() -> tuple[str, list[str]]:
    uv = shutil.which("uv") or shutil.which("uv.exe")
    if uv:
        return uv, ["--directory", PROJECT_DIR, "run", "bionodulo-mcp"]
    return sys.executable, ["-m", "bionodulo_mcp.server"]


def _remote_url(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Remote MCP URL must be HTTPS without credentials or query parameters")
    return url


def _personal_env(clerk_secret_key: str | None, user_email: str | None) -> dict[str, str]:
    if bool(clerk_secret_key) != bool(user_email):
        raise ValueError("Personal cloud mode requires both Clerk secret and user email")
    if clerk_secret_key:
        return {"CLERK_SECRET_KEY": clerk_secret_key, "BIONODULO_USER_EMAIL": user_email or ""}
    return {"BIONODULO_CLOUD": "0"}


def _codex_config_path() -> Path:
    return Path.home() / ".codex" / "config.toml"


def install_codex(*, mode: str, url: str, env: dict[str, str] | None = None) -> None:
    path = _codex_config_path()
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing.strip():
        tomllib.loads(existing)
    kept: list[str] = []
    skipping = False
    for line in existing.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            skipping = (stripped == "[mcp_servers.bionodulo]"
                        or stripped.startswith("[mcp_servers.bionodulo."))
        if not skipping:
            kept.append(line)
    body = "\n".join(kept).rstrip()
    if mode == "remote":
        block = f'[mcp_servers.bionodulo]\nurl = {json.dumps(url)}\n'
    else:
        command, args = _uv_command()
        block = ("[mcp_servers.bionodulo]\n"
                 f"command = {json.dumps(command)}\n"
                 f"args = {json.dumps(args)}\n"
                 "startup_timeout_sec = 30\ntool_timeout_sec = 120\n\n"
                 "[mcp_servers.bionodulo.env]\n"
                 + "".join(f"{key} = {json.dumps(value)}\n" for key, value in (env or {}).items()))
    updated = (body + "\n\n" if body else "") + block
    tomllib.loads(updated)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8", newline="\n")
    print(f"Codex: registered BioNodulo {mode} MCP in {path}")


def _claude_desktop_config_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "Claude" / "claude_desktop_config.json"


def install_claude_desktop(*, mode: str, url: str, env: dict[str, str] | None = None) -> None:
    if mode == "remote":
        print("Claude Desktop: add a custom connector in Customize > Connectors using:")
        print(f"  {url}")
        print("  Connect and sign in with your own BioNodulo account.")
        return
    path = _claude_desktop_config_path()
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(config, dict) or not isinstance(config.get("mcpServers", {}), dict):
        raise ValueError("Claude Desktop config must contain a JSON object with mcpServers object")
    command, args = _uv_command()
    config.setdefault("mcpServers", {})["bionodulo"] = {
        "command": command, "args": args, "env": env or {},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Claude Desktop: registered personal BioNodulo MCP in {path}")


def install_claude_code(*, mode: str, url: str, env: dict[str, str] | None = None) -> None:
    claude = shutil.which("claude")
    if mode == "remote":
        cmd = ["mcp", "add", "--transport", "http", "--scope", "user", "bionodulo", url]
    else:
        command, args = _uv_command()
        cmd = ["mcp", "add", "--scope", "user", "bionodulo"]
        for key, value in (env or {}).items():
            cmd += ["--env", f"{key}={value}"]
        cmd += ["--", command, *args]
    if not claude:
        print("Claude Code: CLI unavailable; install it and rerun this installer.")
        return
    # Never echo command/error text: personal mode can include a credential.
    subprocess.run([claude, "mcp", "remove", "bionodulo", "--scope", "user"], capture_output=True)
    result = subprocess.run([claude, *cmd], capture_output=True)
    if result.returncode:
        raise RuntimeError("Claude Code MCP registration failed; inspect the CLI locally")
    print(f"Claude Code: registered BioNodulo {mode} MCP")


def install_clients(client: str = "all", clerk_secret_key: str | None = None,
                    user_email: str | None = None, *, mode: str = "remote",
                    url: str = DEFAULT_REMOTE_URL) -> None:
    if client not in {"all", "codex", "claude-code", "claude-desktop"}:
        raise ValueError("Unsupported MCP client")
    if mode not in {"remote", "personal"}:
        raise ValueError("MCP mode must be remote or personal")
    if mode == "remote" and (clerk_secret_key or user_email):
        raise ValueError("Clerk credentials require explicit --mode personal")
    url = _remote_url(url) if mode == "remote" else url
    env = _personal_env(clerk_secret_key, user_email) if mode == "personal" else None
    if client in {"codex", "all"}:
        install_codex(mode=mode, url=url, env=env)
    if client in {"claude-desktop", "all"}:
        install_claude_desktop(mode=mode, url=url, env=env)
    if client in {"claude-code", "all"}:
        install_claude_code(mode=mode, url=url, env=env)
    if mode == "remote":
        print("Complete OAuth sign-in in each client before using BioNodulo tools.")
