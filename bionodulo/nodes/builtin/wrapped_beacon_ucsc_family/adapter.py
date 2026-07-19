"""Pinned authorities and runtime helpers for the Beacon/UCSC wrapper wave."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode, _shell_join


TOOLS_IUC_GIT_URL = "https://github.com/galaxyproject/tools-iuc.git"
TOOLS_IUC_GIT_COMMIT = "8eb66da1f6f16fde92688ee6c500d2bcdc924a47"

KENT_GIT_URL = "https://github.com/ucscGenomeBrowser/kent.git"
KENT_357_GIT_COMMIT = "ee250cad347b57996f7cc1125d4be37f49c7fd06"
KENT_482_GIT_COMMIT = "e4481bfc920729522f59d98b7fdfd09023e9ce4f"
KENT_490_GIT_COMMIT = "44cb29b33b2a210b5d5128cf6ab922b7dd3e20e6"

BEACON2_RI_GIT_URL = "https://github.com/EGA-archive/beacon2-ri-tools.git"
BEACON2_RI_GIT_COMMIT = "0d367babe07c8d36111777f729951ccf1826edb8"
BEACON2_IMPORT_SDIST_SHA256 = "238fe76cc0a82ff1c3881ea4a376f664885761e0e211477064147209442f7201"

HEINZ_GIT_URL = "https://github.com/ls-cwi/heinz.git"
HEINZ_GIT_COMMIT = "376330755b6d68df1eaa9ef49629641d75d17c1a"
BIONET_GIT_URL = "https://github.com/bionet-r/BioNet.git"
BIONET_GIT_COMMIT = "e1d28cb7ac6fb08b0699744a6e9e3762f3d157b5"
QQMAN_GIT_URL = "https://github.com/stephenturner/qqman.git"
QQMAN_GIT_COMMIT = "b205bdaa4e0c7fd6ab50d86557ee3649a62a643f"
GFFREAD_GIT_URL = "https://github.com/gpertea/gffread.git"
GFFREAD_GIT_COMMIT = "5647f076f616c583ea32fd19629d549d70fc43ea"
GFFCOMPARE_GIT_URL = "https://github.com/gpertea/gffcompare.git"
GFFCOMPARE_GIT_COMMIT = "8f1bca369cdbf8d4a3beca8eea19ef55986f67de"

BREW3R_CONTAINER = "lldelisle/brew3r:v2"
BREW3R_CONTAINER_DIGEST = "sha256:082e656b607680b71078aaee7feb622e5cdbfb4daed294feae1699659f1b4d76"
BREW3R_DOCKERFILE_GIT_COMMIT = "3d98f7c96738925c77cf256682209c0230d23e09"
BREW3R_PLATFORM = "linux/amd64"

ASSET_DIR = Path(__file__).with_name("assets")
PUBLIC_UCSC_DB_CONFIG = ASSET_DIR / "ucsc_db_connection.conf"
ASSET_SHA256 = {
    "manhattan.R": "e8df00a7de5ed30b0709a172f381a8985d46621929a4c61f9f6f1ef8544ebd5e",
    "heinz_visualization.py": "4a2d21327b3afb9fd43b961251e21db139cd511ca69ab60b3d01e88af2d4c679",
    "heinz_scoring.py": "f9005c051eb08633fa3ad190acd4e253ba02f13211eca2195b3a954f5884b843",
    "heinz_bum.R": "64fc20268e208fc7a70f0d71e33111ef62c18ee5c11bfd6e63d60d7fce6536de",
    "brew3r.r_script.R": "0472030823d0617b39a1ef846a16b9e7efa18c6a6142e90f3d2eaa8dd26c40d7",
}


def asset_path(name: str) -> str:
    """Return an absolute path to a vendored wrapper asset."""
    return str(ASSET_DIR / name)


def pin_contract(
    classes: Iterable[type[CommandNode]],
    *,
    runtime_version: str,
    runtime_git_url: str = "",
    runtime_git_commit: str = "",
    package_constraint: str = "",
    source_archive_sha256: str = "",
) -> None:
    """Attach the pinned runtime and Galaxy wrapper evidence to node classes."""
    for node_class in classes:
        node_class.GIT_URL = runtime_git_url or TOOLS_IUC_GIT_URL
        node_class.GIT_COMMIT = runtime_git_commit or TOOLS_IUC_GIT_COMMIT
        node_class.RUNTIME_VERSION = runtime_version
        node_class.RUNTIME_GIT_URL = runtime_git_url
        node_class.RUNTIME_GIT_COMMIT = runtime_git_commit
        node_class.PINNED_RUNTIME_SOURCE_AUTHORITY = (
            f"{runtime_git_url}@{runtime_git_commit}" if runtime_git_url and runtime_git_commit else ""
        )
        node_class.GALAXY_WRAPPER_GIT_URL = TOOLS_IUC_GIT_URL
        node_class.GALAXY_WRAPPER_GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
        documentation_url = str(getattr(node_class, "DOCUMENTATION_URL", ""))
        if "github.com/galaxyproject/tools-iuc/tree/main/" in documentation_url:
            node_class.GALAXY_WRAPPER_SOURCE_URL = documentation_url.replace(
                "/tree/main/", f"/tree/{TOOLS_IUC_GIT_COMMIT}/"
            )
        else:
            node_class.GALAXY_WRAPPER_SOURCE_URL = (
                f"https://github.com/galaxyproject/tools-iuc/tree/{TOOLS_IUC_GIT_COMMIT}/tools"
            )
        node_class.PACKAGE_CONSTRAINT = package_constraint
        node_class.SOURCE_ARCHIVE_SHA256 = source_archive_sha256
        node_class.EXIT_SEMANTICS = (
            "Invalid contracts fail before execution; a non-zero process exit or missing planned output fails the node."
        )


def ucsc_db_config(inputs: dict[str, Any]) -> str:
    """Resolve an explicit UCSC config or the pinned public wrapper default."""
    value = str(inputs.get("ucsc_db_connection", "") or "").strip()
    return value or str(PUBLIC_UCSC_DB_CONFIG)


def ucsc_db_command(inputs: dict[str, Any], command: list[str]) -> str:
    """Run one database-backed Kent tool with an isolated HOME and .hg.conf."""
    output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
    home = output_dir / "ucsc-home"
    config = home / ".hg.conf"
    return " && ".join(
        [
            _shell_join(["mkdir", "-p", str(home)]),
            _shell_join(["cp", ucsc_db_config(inputs), str(config)]),
            _shell_join(["chmod", "600", str(config)]),
            f"HOME={_shell_join([str(home)])} {_shell_join(command)}",
        ]
    )
