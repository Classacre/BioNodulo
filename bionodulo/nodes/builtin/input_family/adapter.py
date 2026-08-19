"""Shared staging, download, and validation for focused workflow input nodes.

Provides nodes for importing bioinformatics data files into workflows.
These nodes serve as workflow entry points for various file formats.

URL-aware: any input that looks like an http(s)/ftp URL is fetched to a
workspace-scoped cache directory on first run; subsequent runs reuse the
cached copy. This replaces the older "Download example data" startup
prompt — templates ship URLs directly in their node params and download on
demand instead of requiring a separate up-front fetch.
"""
from __future__ import annotations

import gzip
import hashlib
import logging
import os
import re
import shutil
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode
from bionodulo import __version__ as _BIONODULO_VERSION

logger = logging.getLogger(__name__)

URL_SCHEMES = {"http", "https", "ftp"}
_DOWNLOAD_CHUNK_BYTES = 1024 * 256

# Version comes from the package: the literal used to say 2.0, a release
# that never existed.
_HTTP_USER_AGENT = (
    f"BioNodulo/{_BIONODULO_VERSION} "
    "(https://github.com/Classacre/BioNodulo; input-node downloader)"
)
_DOWNLOAD_TIMEOUT_S = 300


def _looks_like_url(value: Any) -> bool:
    """Return True when *value* is a plausible http(s)/ftp URL string."""
    if not isinstance(value, str):
        return False
    if "://" not in value:
        return False
    try:
        parsed = urllib.parse.urlparse(value)
    except ValueError:
        return False
    return parsed.scheme.lower() in URL_SCHEMES and bool(parsed.netloc)


# NCBI E-utilities efetch endpoint. Used so a single input node can pull a
# record by accession instead of needing a separate fetch node.
_NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _ncbi_efetch_url(
    accession: str,
    *,
    email: str,
    db: str = "nuccore",
    rettype: str = "fasta",
) -> str:
    """Build an identified NCBI EFetch URL using the audited service adapter."""
    from bionodulo.nodes.builtin.ncbi_family.adapter import identified_params

    ids = ",".join(part.strip() for part in str(accession).split(",") if part.strip())
    query = urllib.parse.urlencode(
        {
            "db": db,
            "id": ids,
            "rettype": rettype,
            "retmode": "text",
            **identified_params(email=email),
        }
    )
    return f"{_NCBI_EFETCH}?{query}"


def _safe_filename(url: str) -> str:
    """Derive a display-safe basename while cache identity remains URL-scoped."""
    parsed = urllib.parse.urlparse(url)
    name = Path(parsed.path).name or "download"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "download"


def _url_cache_key(url: str) -> str:
    """Return a collision-resistant identity for the complete URL."""

    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _source_basename(value: Any) -> str:
    """Return the path basename of a local path or URL, excluding its query."""

    raw = os.fsdecode(os.fspath(value))
    parsed = urllib.parse.urlparse(raw)
    path = parsed.path if parsed.scheme and parsed.netloc else raw
    return Path(path).name


def _is_compressed_vcf(value: Any) -> bool:
    name = _source_basename(value).lower()
    return name.endswith((".vcf.gz", ".vcf.bgz", ".bgz"))


def _vcf_index_suffix(value: Any) -> str:
    name = _source_basename(value).lower()
    for suffix in (".tbi", ".csi"):
        if name.endswith(suffix):
            return suffix
    return ""


def _cache_root(context: Any) -> Path:
    """Workspace-scoped URL download cache root.

    Keeping the cache inside the workspace makes provenance obvious (the
    user can `ls` it) and means moving / archiving the workspace also moves
    the cached inputs. The legacy `manager/example_data.py` path is *not*
    reused because templates may now reference any URL, not just curated
    ones.
    """
    if context is not None:
        workspace = getattr(context, "workspace_dir", None)
        if workspace:
            return Path(workspace) / ".bionodulo" / "url_cache"
    return Path.home() / ".bionodulo" / "url_cache"


def _temporary_path(directory: Path, *, prefix: str, suffix: str) -> Path:
    descriptor, value = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=directory)
    os.close(descriptor)
    return Path(value)


# Emit at most this often, so a fast download cannot flood the event stream.
_PROGRESS_INTERVAL_S = 0.25


def _copy_with_progress(response: Any, fh: Any, context: Any, url: str) -> None:
    """Stream `response` into `fh`, emitting node_download_progress as it goes.

    Downloads were previously a silent `shutil.copyfileobj`, so a node fetching
    a multi-GB reference looked identical to a hung one. The UI renders these
    events as a progress bar on the node itself.

    Emission is throttled and best-effort: a context without `emit` (unit tests,
    the CLI) just copies, and a failing emit must never abort a download that is
    otherwise fine.
    """
    emit = getattr(context, "emit", None)
    node_id = getattr(context, "node_id", None)
    run_id = getattr(context, "run_id", None)

    total = 0
    length = response.headers.get("Content-Length") if hasattr(response, "headers") else None
    try:
        total = int(length) if length else 0
    except (TypeError, ValueError):
        total = 0

    read = 0
    last = 0.0
    while True:
        chunk = response.read(_DOWNLOAD_CHUNK_BYTES)
        if not chunk:
            break
        fh.write(chunk)
        read += len(chunk)
        if emit is None or node_id is None:
            continue
        now = time.monotonic()
        if now - last < _PROGRESS_INTERVAL_S:
            continue
        last = now
        try:
            emit(
                "node_download_progress",
                {
                    "run_id": run_id,
                    "node_id": node_id,
                    "url": url,
                    "downloaded_bytes": read,
                    # 0 when the server sends no Content-Length; the UI shows an
                    # indeterminate bar rather than a wrong percentage.
                    "total_bytes": total,
                },
            )
        except Exception:  # noqa: BLE001 - progress must never fail a download
            logger.debug("download progress emit failed", exc_info=True)

    if emit is not None and node_id is not None:
        try:
            emit(
                "node_download_progress",
                {
                    "run_id": run_id,
                    "node_id": node_id,
                    "url": url,
                    "downloaded_bytes": read,
                    "total_bytes": total or read,
                    "done": True,
                },
            )
        except Exception:  # noqa: BLE001
            logger.debug("final download progress emit failed", exc_info=True)


def _download_to_cache(
    url: str,
    context: Any,
    *,
    decompress_gzip: bool = True,
) -> Path:
    """Download *url* into the workspace cache, returning the local path.

    The complete URL SHA-256 selects an isolated cache directory, so unrelated
    URLs with the same basename cannot alias. Downloaded and decompressed bytes
    are promoted with ``os.replace`` only after the whole operation succeeds.

    When ``decompress_gzip`` is true, URLs ending in ``.gz`` are transparently
    decompressed and the cached filename loses that suffix. Callers such as
    ``InputVCFNode`` disable this to preserve bgzip bytes and sidecar identity.
    """
    cache_dir = _cache_root(context) / _url_cache_key(url)
    cache_dir.mkdir(parents=True, exist_ok=True)
    fname = _safe_filename(url)
    gunzip = decompress_gzip and fname.lower().endswith(".gz")
    if gunzip:
        fname = fname[:-3] or "download"
    dest = cache_dir / fname
    if dest.exists():
        logger.debug("URL cache hit: %s -> %s", url, dest)
        return dest

    logger.info("Downloading URL cache key %s -> %s", _url_cache_key(url)[:12], dest)
    req = urllib.request.Request(url, headers={"User-Agent": _HTTP_USER_AGENT})
    download_path: Path | None = _temporary_path(
        cache_dir,
        prefix=".download-",
        suffix=".part",
    )
    decoded_path: Path | None = None
    try:
        with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT_S) as response:
            with download_path.open("wb") as fh:
                _copy_with_progress(response, fh, context, url)
        if gunzip:
            decoded_path = _temporary_path(cache_dir, prefix=".decoded-", suffix=".part")
            with gzip.open(download_path, "rb") as gz_fh, decoded_path.open("wb") as out_fh:
                shutil.copyfileobj(gz_fh, out_fh)
            os.replace(decoded_path, dest)
            decoded_path = None
        else:
            os.replace(download_path, dest)
            download_path = None
    finally:
        if download_path is not None:
            download_path.unlink(missing_ok=True)
        if decoded_path is not None:
            decoded_path.unlink(missing_ok=True)
    return dest


_ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz", ".tar", ".zip")


def _looks_like_archive(name: str) -> bool:
    return name.lower().endswith(_ARCHIVE_SUFFIXES)


def _safe_extract_members(archive_root: Path, names: list[str]) -> None:
    """Reject any member that would land outside *archive_root*.

    Archive members are attacker-controlled text: an entry named ``../../etc/x``
    or an absolute path escapes the extraction directory (the "tar slip" class).
    Resolve each destination and require it stay inside the root.
    """
    root = archive_root.resolve()
    for name in names:
        target = (root / name).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"Refusing to extract archive member outside the target directory: {name}")


def _extract_archive(archive: Path, destination: Path) -> None:
    """Extract a tar/zip archive into *destination*, refusing unsafe members."""
    destination.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            _safe_extract_members(destination, zf.namelist())
            zf.extractall(destination)
        return
    with tarfile.open(archive) as tf:
        members = tf.getmembers()
        # Symlinks/hardlinks can also point outside the root even when the
        # member name itself looks benign, so check their targets too.
        for member in members:
            if member.issym() or member.islnk():
                link = member.linkname
                resolved = (destination / Path(member.name).parent / link).resolve()
                root = destination.resolve()
                if resolved != root and root not in resolved.parents:
                    raise ValueError(
                        f"Refusing to extract archive link pointing outside the target: {member.name}"
                    )
        _safe_extract_members(destination, [member.name for member in members])
        # `filter="data"` is CPython's own hardening (default from 3.14): it
        # strips absolute paths, ".." components, links escaping the root, and
        # unsafe modes/device files. Belt and braces with the checks above,
        # which give a clearer error and cover older interpreters.
        try:
            tf.extractall(destination, filter="data")
        except TypeError:  # Python < 3.12 has no `filter` argument
            tf.extractall(destination)


def _flatten_single_root(directory: Path) -> Path:
    """Return the real content root of an extracted archive.

    Archives conventionally wrap everything in one top-level directory
    (``k2_viral_20240112/...``), so returning the extraction directory itself
    would hand consumers a folder containing exactly one folder.
    """
    entries = [entry for entry in directory.iterdir() if entry.name not in (".", "..")]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return directory


def _wrap_file_in_directory(downloaded: Path) -> Path:
    """Return a directory containing `downloaded`, for directory inputs.

    Some tools only accept a directory (dorado scans a POD5 *directory*), while
    the public dataset is published as a single file. Without this, pointing a
    directory input at that URL downloads the file and then fails validation
    with "Expected a directory input, got file" -- forcing the file to be
    committed to the repo instead of fetched from its real source.

    Deliberately URL-only: a *local* path that is a file is more likely a
    mistake than an intent, and should keep failing loudly.
    """
    wrapper = downloaded.parent / f"{downloaded.name}.asdir"
    wrapper.mkdir(parents=True, exist_ok=True)
    target = wrapper / downloaded.name
    if not target.exists():
        try:
            os.link(downloaded, target)
        except OSError:
            shutil.copy2(downloaded, target)
    return wrapper


def _download_archive_to_cache(url: str, context: Any) -> Path:
    """Download and extract an archive URL, returning the extracted directory.

    Extraction is atomic: a partially-unpacked tree is never promoted to the
    cache path, so an interrupted download can't be mistaken for a complete
    reference database on the next run.
    """
    cache_dir = _cache_root(context) / _url_cache_key(url)
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / "extracted"
    if dest.exists():
        logger.debug("URL archive cache hit: %s -> %s", url, dest)
        return _flatten_single_root(dest)

    logger.info("Downloading archive %s -> %s", _url_cache_key(url)[:12], dest)
    req = urllib.request.Request(url, headers={"User-Agent": _HTTP_USER_AGENT})
    download_path = _temporary_path(cache_dir, prefix=".archive-", suffix=".part")
    staging = Path(tempfile.mkdtemp(prefix=".extract-", dir=cache_dir))
    try:
        with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT_S) as response:
            with download_path.open("wb") as fh:
                _copy_with_progress(response, fh, context, url)
        _extract_archive(download_path, staging)
        os.replace(staging, dest)
        staging = None  # type: ignore[assignment]
    finally:
        download_path.unlink(missing_ok=True)
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
    return _flatten_single_root(dest)


def _materialise_example_entry(entry: Any, dest: Path, context: Any) -> bool:
    """Download or generate a single manifest entry into *dest*."""
    if dest.exists():
        return True
    if getattr(entry, "url", None):
        try:
            # Use the manifest downloader so the entry's `gunzip` flag is honoured
            # consistently (the generic cache helper decompresses by extension,
            # which is wrong for entries we want to keep gzipped, e.g. *.fastq.gz).
            from bionodulo.manager.example_data import _download_url

            dest.parent.mkdir(parents=True, exist_ok=True)
            _download_url(
                entry.url,
                dest,
                gunzip=getattr(entry, "gunzip", False),
                archive_member=getattr(entry, "archive_member", None),
                rename_columns=getattr(entry, "rename_columns", None),
            )
            return dest.exists()
        except Exception as exc:
            logger.warning(
                "Failed to download example data %s/%s: %s",
                entry.category, entry.filename, exc,
            )
            return False
    generator = getattr(entry, "generator", None)
    if callable(generator):
        try:
            generator(dest)
            return dest.exists()
        except Exception as exc:
            logger.warning(
                "Failed to generate example data %s/%s: %s",
                entry.category, entry.filename, exc,
            )
            return False
    return False


def _resolve_example_data_fallback(source: Any, context: Any) -> Path | None:
    """Materialise an `examples/data/<category>[/file]` path on demand.

    A template that ships synthetic example data (chip-seq, metagenomics,
    single-cell, biopython, phylogenetics) references local paths under
    ``examples/data/<category>/<file>``. Those files used to be created by
    the up-front Example Data download in the start menu; that flow was
    removed when input nodes learned to fetch URLs, so a missing path here
    is the cue to consult the same ``EXAMPLE_DATA_MANIFEST`` and either
    download (URL entries) or run the generator (synthetic entries) into
    the workspace cache.

    Category-level paths (``examples/data/<category>``, no filename)
    materialise *every* manifest entry for that category and return the
    cached directory — this covers `InputDirectoryNode` templates such as
    single-cell which expect a folder of pre-staged FASTQs.
    """
    if not isinstance(source, str):
        return None
    parts = [p for p in source.replace("\\", "/").split("/") if p]
    try:
        idx = parts.index("examples")
    except ValueError:
        return None
    if idx + 2 >= len(parts) or parts[idx + 1] != "data":
        return None
    category = parts[idx + 2]
    filename = parts[-1] if len(parts) > idx + 3 else None
    try:
        from bionodulo.manager.example_data import EXAMPLE_DATA_MANIFEST
    except Exception:
        return None
    cache_dir = _cache_root(context) / "examples_data" / category
    cache_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        entries = [df for df in EXAMPLE_DATA_MANIFEST if df.category == category]
        if not entries:
            return None
        ok_any = False
        for entry in entries:
            dest = cache_dir / entry.filename
            if _materialise_example_entry(entry, dest, context):
                ok_any = True
        return cache_dir if ok_any else None

    entry = next(
        (df for df in EXAMPLE_DATA_MANIFEST if df.category == category and df.filename == filename),
        None,
    )
    if entry is not None:
        dest = cache_dir / filename
        logger.info("Materialising example data: %s/%s -> %s", category, filename, dest)
        return dest if _materialise_example_entry(entry, dest, context) else None

    # Directory reference (e.g. long_read/pod5, spatial_transcriptomics/visium_outs):
    # materialise every manifest entry whose filename lives under that directory.
    prefix = filename + "/"
    sub_entries = [
        df for df in EXAMPLE_DATA_MANIFEST
        if df.category == category and df.filename.startswith(prefix)
    ]
    if not sub_entries:
        return None
    ok_any = False
    for df in sub_entries:
        dest = cache_dir / df.filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        if _materialise_example_entry(df, dest, context):
            ok_any = True
    return (cache_dir / filename) if ok_any else None


class CopyInputNode(CommandNode):
    """Shared copy behavior for workflow input nodes."""

    # Input nodes return the absolute path of the staged copy inside the
    # CURRENT run's directory. Caching that output across runs serves the
    # previous run's path on a cache hit — a directory that has typically been
    # cleaned up — so input nodes are always re-executed (they only copy or
    # resume a workspace-level URL cache, which is cheap). See
    # WorkflowExecutor._executor_cache_policy: "always_run" forces a fresh
    # cache key (None) every run.
    EXECUTOR_CACHE_POLICY = "always_run"

    SOURCE_KEYS: ClassVar[tuple[str, ...]] = ()
    OUTPUT_KEYS: ClassVar[tuple[str, ...]] = ()
    ALLOW_MULTIPLE: ClassVar[bool] = False
    ALLOW_EMPTY: ClassVar[bool] = False
    MISSING_INPUT_MESSAGE: ClassVar[str] = "No input provided"
    EXPECTED_KIND: ClassVar[str] = "any"
    DECOMPRESS_GZIP: ClassVar[bool] = False
    VERSION = "2.1.0"
    GIT_URL = "https://github.com/Classacre/BioNodulo.git"
    PRODUCT_SOURCE_COMMIT = "a32a426c03ce4c925bf7dcdbd2cf08fbdedd55e9"
    FOCUSED_OWNERSHIP_COMMIT = "827ffffc57530d60becfc66f190c35e79d2df7fc"
    PYTHON_VERSION = "3.12.13"
    PYTHON_SOURCE_COMMIT = "3bb231a6a5dc02b95658877318bf61501a7209e9"
    GIT_COMMIT = PRODUCT_SOURCE_COMMIT
    SOURCE_URL = (
        "https://github.com/Classacre/BioNodulo/blob/"
        f"{PRODUCT_SOURCE_COMMIT}/bionodulo/nodes/builtin/inputs.py"
    )
    UPSTREAM_SOURCE = "bionodulo/nodes/builtin/inputs.py"
    SOURCE_AUTHORITIES = {
        "product_contract": SOURCE_URL,
        "focused_ownership": (
            "https://github.com/Classacre/BioNodulo/blob/"
            f"{FOCUSED_OWNERSHIP_COMMIT}/bionodulo/nodes/builtin/input_family/adapter.py"
        ),
        "python_copy_runtime": (
            "https://github.com/python/cpython/blob/"
            f"{PYTHON_SOURCE_COMMIT}/Lib/shutil.py"
        ),
        "python_url_runtime": (
            "https://github.com/python/cpython/blob/"
            f"{PYTHON_SOURCE_COMMIT}/Lib/urllib/request.py"
        ),
        "python_gzip_runtime": (
            "https://github.com/python/cpython/blob/"
            f"{PYTHON_SOURCE_COMMIT}/Lib/gzip.py"
        ),
        "ncbi_efetch_contract": "https://www.ncbi.nlm.nih.gov/books/NBK25499/",
    }
    AUDIT_STATUS = "contract-checked-no-external-network-execution"
    EXIT_SEMANTICS = (
        "This in-process node has no subprocess exit code. Missing inputs, failed downloads, "
        "invalid source modes, duplicate destination names, and staging failures raise before "
        "an output is returned; downloads and staged artifacts are promoted atomically."
    )

    @classmethod
    def _source_value(cls, kwargs: dict[str, Any]) -> Any:
        for key in cls.SOURCE_KEYS:
            value = kwargs.get(key)
            if value:
                return value
        return [] if cls.ALLOW_MULTIPLE else None

    @staticmethod
    def _output_dir(context: Any, output_dir: Any) -> Path:
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        if output_dir is None:
            output_dir = "."
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    @classmethod
    def _resolve_source(
        cls,
        source: Any,
        context: Any,
        mode: str = "auto",
        *,
        ncbi_email: Any = "",
    ) -> Path:
        """Resolve a source path, URL, or NCBI accession to a concrete file.

        ``mode`` selects how *source* is interpreted:
        - ``"auto"`` (default): a string that looks like an http(s)/ftp URL is
          downloaded; anything else is treated as a local path.
        - ``"url"``: *source* is always downloaded as a URL.
        - ``"ncbi"``: *source* is one or more NCBI accessions, fetched via the
          E-utilities efetch endpoint (FASTA by default).
        - ``"local"``: *source* is always treated as a local path.

        URLs are downloaded into a workspace-scoped cache directory on first
        use; the cached path is returned. Relative paths are resolved against
        the run workspace directory. Absolute local paths pass through
        unchanged. Missing ``examples/data/<category>/<file>`` paths fall back
        to the ``EXAMPLE_DATA_MANIFEST`` so templates that ship synthetic
        example data keep working without an up-front bulk download.
        """
        if mode != "local" and isinstance(source, str) and "://" in source:
            parsed = urllib.parse.urlparse(source)
            if parsed.scheme.lower() not in URL_SCHEMES:
                supported = ", ".join(sorted(URL_SCHEMES))
                raise ValueError(
                    f"Unsupported URL scheme '{parsed.scheme}'; supported schemes: {supported}"
                )
        if mode == "ncbi" and isinstance(source, str) and source.strip():
            from bionodulo.nodes.builtin.ncbi_family.adapter import (
                resolve_email,
                validate_email,
            )

            email = resolve_email(ncbi_email)
            if not email:
                raise ValueError(
                    "Input 'email' is required for source=ncbi; alternatively use ncbi_efetch"
                )
            validation = validate_email(email)
            if validation is not True:
                raise ValueError(str(validation))
            return _download_to_cache(
                _ncbi_efetch_url(source, email=email),
                context,
                decompress_gzip=cls.DECOMPRESS_GZIP,
            )
        if mode == "url" and isinstance(source, str) and source.strip():
            if cls.EXPECTED_KIND == "directory" and _looks_like_archive(_safe_filename(source)):
                return _download_archive_to_cache(source, context)
            downloaded = _download_to_cache(
                source,
                context,
                decompress_gzip=cls.DECOMPRESS_GZIP,
            )
            if cls.EXPECTED_KIND == "directory" and downloaded.is_file():
                return _wrap_file_in_directory(downloaded)
            return downloaded
        if mode in ("auto", "") and isinstance(source, str) and _looks_like_url(source):
            # A directory input pointed at a .tar.gz means "unpack this and give
            # me the tree" — reference bundles (kraken2 DBs, Space Ranger
            # references) are only published as archives.
            if cls.EXPECTED_KIND == "directory" and _looks_like_archive(_safe_filename(source)):
                return _download_archive_to_cache(source, context)
            downloaded = _download_to_cache(
                source,
                context,
                decompress_gzip=cls.DECOMPRESS_GZIP,
            )
            if cls.EXPECTED_KIND == "directory" and downloaded.is_file():
                return _wrap_file_in_directory(downloaded)
            return downloaded
        src = Path(source)
        if not src.is_absolute() and context is not None:
            workspace = getattr(context, "workspace_dir", Path("."))
            src = (workspace / src).resolve()
        if not src.exists():
            fallback = _resolve_example_data_fallback(source, context)
            if fallback is not None:
                return fallback
        return src

    @classmethod
    def _validate_resolved_source(cls, src: Path) -> None:
        if not src.exists():
            raise FileNotFoundError(f"Source not found: {src}")
        if cls.EXPECTED_KIND == "file" and not src.is_file():
            raise ValueError(f"Expected a file input, got directory: {src}")
        if cls.EXPECTED_KIND == "directory" and not src.is_dir():
            raise ValueError(f"Expected a directory input, got file: {src}")

    @staticmethod
    def _remove_path(path: Path) -> None:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)

    @classmethod
    def _promote_staged_path(cls, staged: Path, destination: Path) -> None:
        destination_exists = destination.exists() or destination.is_symlink()
        if not destination_exists or (staged.is_file() and destination.is_file()):
            os.replace(staged, destination)
            return

        backup = Path(
            tempfile.mkdtemp(
                prefix=f".{destination.name}.backup-",
                dir=destination.parent,
            )
        )
        backup.rmdir()
        os.replace(destination, backup)
        try:
            os.replace(staged, destination)
        except Exception:
            os.replace(backup, destination)
            raise
        else:
            cls._remove_path(backup)

    @classmethod
    def _promote_staged_bundle(
        cls,
        staged_destinations: list[tuple[Path, Path]],
    ) -> list[Path]:
        """Promote a related artifact bundle with rollback on any failure."""

        backups: list[tuple[Path, Path]] = []
        promoted: list[Path] = []
        try:
            for _staged, destination in staged_destinations:
                if not (destination.exists() or destination.is_symlink()):
                    continue
                backup = Path(
                    tempfile.mkdtemp(
                        prefix=f".{destination.name}.backup-",
                        dir=destination.parent,
                    )
                )
                backup.rmdir()
                os.replace(destination, backup)
                backups.append((backup, destination))

            for staged, destination in staged_destinations:
                os.replace(staged, destination)
                promoted.append(destination)
        except Exception:
            for destination in reversed(promoted):
                cls._remove_path(destination)
            for backup, destination in reversed(backups):
                if backup.exists() or backup.is_symlink():
                    os.replace(backup, destination)
            raise
        else:
            for backup, _destination in backups:
                cls._remove_path(backup)
        return [destination.resolve() for _staged, destination in staged_destinations]

    @classmethod
    def _stage_resolved_source(
        cls,
        src: Path,
        out_dir: Path,
        *,
        destination_name: str | None = None,
    ) -> Path:
        cls._validate_resolved_source(src)
        dst = out_dir / (destination_name or src.name)
        if src.resolve() == dst.resolve():
            return src.resolve()

        if src.is_dir():
            staged = Path(
                tempfile.mkdtemp(prefix=f".{dst.name}.staging-", dir=out_dir)
            )
            try:
                shutil.copytree(src, staged, dirs_exist_ok=True)
                cls._promote_staged_path(staged, dst)
            finally:
                if staged.exists():
                    cls._remove_path(staged)
        else:
            staged = _temporary_path(
                out_dir,
                prefix=f".{dst.name}.staging-",
                suffix=".part",
            )
            try:
                shutil.copy2(src, staged)
                cls._promote_staged_path(staged, dst)
            finally:
                staged.unlink(missing_ok=True)
        return dst.resolve()

    @classmethod
    def _copy_one(cls, source: Any, out_dir: Path, context: Any, mode: str = "auto") -> Path:
        src = cls._resolve_source(source, context, mode)
        return cls._stage_resolved_source(src, out_dir)

    @classmethod
    def _format_outputs(cls, copied: list[Path]) -> dict[str, Any]:
        if cls.ALLOW_MULTIPLE:
            return {cls.OUTPUT_KEYS[0]: [str(path) for path in copied]}
        copied_path = str(copied[0])
        return {key: copied_path for key in cls.OUTPUT_KEYS}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Copy input path(s) into the node directory and return copied paths."""
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        value = self.__class__._source_value(kwargs)
        if not value and not self.__class__.ALLOW_EMPTY:
            raise ValueError(self.__class__.MISSING_INPUT_MESSAGE)

        values = value if self.__class__.ALLOW_MULTIPLE else [value]
        if isinstance(values, str):
            values = [values]

        # How to interpret the source string: local path, URL, or NCBI
        # accession. "auto" keeps the historical behaviour (download when it
        # looks like a URL, else local), so existing templates are unaffected.
        mode = str(kwargs.get("source") or "auto").strip().lower()
        context = kwargs.get("context")
        out_dir = self.__class__._output_dir(context, kwargs.get("output_dir"))
        resolved = [
            self.__class__._resolve_source(
                src,
                context,
                mode,
                ncbi_email=kwargs.get("email", ""),
            )
            for src in values
        ]
        for source in resolved:
            self.__class__._validate_resolved_source(source)

        normalized_names = [source.name.casefold() for source in resolved]
        duplicates = sorted(
            name for name in set(normalized_names) if normalized_names.count(name) > 1
        )
        if duplicates:
            rendered = ", ".join(duplicates)
            raise ValueError(
                "Input sources resolve to duplicate destination basenames; "
                f"rename them before staging: {rendered}"
            )

        copied = [
            self.__class__._stage_resolved_source(source, out_dir)
            for source in resolved
        ]
        return {"outputs": self.__class__._format_outputs(copied)}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        value = cls._source_value(inputs)
        if not value and not cls.ALLOW_EMPTY:
            return cls.MISSING_INPUT_MESSAGE
        mode = str(inputs.get("source") or "auto").strip().lower()
        if mode not in {"auto", "local", "url", "ncbi"}:
            return "Input 'source' must be one of: auto, local, url, ncbi"
        if mode == "ncbi":
            from bionodulo.nodes.builtin.ncbi_family.adapter import (
                resolve_email,
                validate_email,
            )

            email = resolve_email(inputs.get("email", ""))
            if not email:
                return "Input 'email' is required for source=ncbi; alternatively use ncbi_efetch"
            return validate_email(email)
        return True


class _InputFASTQContract(CopyInputNode):
    """Input FASTQ read files (single or paired-end)."""
    LEGACY_NODE_ID = "input_fastq"
    DISPLAY_NAME = "Input FASTQ"
    CATEGORY = "input"
    DESCRIPTION = "Import single-end or paired-end FASTQ read files"
    SEARCH_ALIASES = ["reads", "fastq", "input", "import reads"]
    RETURN_TYPES = ("FASTQ_LIST", "FASTQ", "FASTQ")
    RETURN_NAMES = ("reads", "read1", "read2")
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://en.wikipedia.org/wiki/FASTQ_format"
    COMMAND = ["cp", "-r", "{inputs.reads}", "{output}"]
    SOURCE_KEYS = ("reads",)
    OUTPUT_KEYS = ("reads",)
    ALLOW_MULTIPLE = True
    MISSING_INPUT_MESSAGE = (
        "Input 'reads' must contain one single-end file or two paired-end files"
    )
    EXPECTED_KIND = "file"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {
                    "description": "Path(s) or URL(s) to FASTQ file(s). For paired-end, provide two. URLs (http/https/ftp) are downloaded to the workspace cache on first run.",
                }),
            },
            "optional": {
                "sample_name": ("STRING", {"default": "sample"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Copy reads and expose both collection and scalar mate ports."""
        reads = kwargs.get("reads", [])
        if isinstance(reads, str):
            reads = [reads]

        # Paired-end naming validation (lenient — warns but doesn't block)
        if len(reads) == 2:
            names = [Path(r).name for r in reads]
            lower_names = [n.lower() for n in names]
            has_r1 = any(marker in n for n in lower_names for marker in ("r1", "_1", "forward", "read1"))
            has_r2 = any(marker in n for n in lower_names for marker in ("r2", "_2", "reverse", "read2"))
            if not (has_r1 and has_r2):
                logger.warning(
                    "Paired-end reads filenames don't follow typical naming (R1/R2, _1/_2, "
                    "forward/reverse, read1/read2). Got: %s",
                    names,
                )

        result = await super().run(**kwargs)
        copied = result["outputs"]["reads"]
        result["outputs"]["read1"] = copied[0]
        if len(copied) == 2:
            result["outputs"]["read2"] = copied[1]
        return result

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        reads = inputs.get("reads", [])
        if isinstance(reads, str):
            reads = [reads]
        if len(reads) not in {1, 2}:
            return "Input 'reads' must contain one single-end file or two paired-end files"
        return True


class _InputFASTAContract(CopyInputNode):
    """Input FASTA reference or sequence file."""
    LEGACY_NODE_ID = "input_fasta"
    DISPLAY_NAME = "Input FASTA"
    CATEGORY = "input"
    DESCRIPTION = "Import a FASTA reference or sequence file"
    SEARCH_ALIASES = ["reference", "fasta", "genome", "input ref"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("reference",)
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://en.wikipedia.org/wiki/FASTA_format"
    COMMAND = ["cp", "-r", "{inputs.reference}", "{output}"]
    SOURCE_KEYS = ("reference", "file_path")
    OUTPUT_KEYS = ("reference",)
    MISSING_INPUT_MESSAGE = "No reference or file_path provided"
    EXPECTED_KIND = "file"
    DECOMPRESS_GZIP = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Local path, URL, or NCBI accession for the FASTA. With source=auto, http(s)/ftp URLs are downloaded (gzip auto-decompressed) and everything else is a local path."}),
            },
            "optional": {
                "source": ("STRING", {
                    "default": "auto",
                    "options": ["auto", "local", "url", "ncbi"],
                    "description": "How to interpret the value: auto (URL or local), local file, URL download, or NCBI accession (efetch).",
                }),
                "email": (
                    "STRING",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "NCBI contact email required when source=ncbi",
                    },
                ),
            },
            "hidden": {
                "file_path": ("STRING", {"description": "Alias for reference (backward compatibility)"}),
            },
        }


class _InputFileContract(CopyInputNode):
    """Input a generic file."""
    LEGACY_NODE_ID = "input_file"
    DISPLAY_NAME = "Input File"
    CATEGORY = "input"
    DESCRIPTION = "Import any file into the workflow"
    SEARCH_ALIASES = ["file", "input", "import file"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("file",)
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://en.wikipedia.org/wiki/Computer_file"
    COMMAND = ["cp", "-r", "{inputs.file}", "{output}"]
    SOURCE_KEYS = ("file", "file_path")
    OUTPUT_KEYS = ("file",)
    MISSING_INPUT_MESSAGE = "No file or file_path provided"
    EXPECTED_KIND = "file"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"description": "Local path, URL, or NCBI accession for the file. With source=auto, http(s)/ftp URLs are downloaded byte-for-byte and everything else is a local path."}),
            },
            "optional": {
                "source": ("STRING", {
                    "default": "auto",
                    "options": ["auto", "local", "url", "ncbi"],
                    "description": "How to interpret the value: auto (URL or local), local file, URL download, or NCBI accession (efetch).",
                }),
                "email": (
                    "STRING",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "NCBI contact email required when source=ncbi",
                    },
                ),
            },
            "hidden": {
                "file_path": ("STRING", {"description": "Alias for file (backward compatibility)"}),
            },
        }


class _InputDirectoryContract(CopyInputNode):
    """Input a directory."""
    LEGACY_NODE_ID = "input_directory"
    DISPLAY_NAME = "Input Directory"
    CATEGORY = "input"
    DESCRIPTION = "Import a directory into the workflow"
    SEARCH_ALIASES = ["directory", "folder", "input dir"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("directory",)
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://en.wikipedia.org/wiki/Directory_(computing)"
    COMMAND = ["cp", "-r", "{inputs.directory}", "{output}"]
    SOURCE_KEYS = ("directory", "dir_path")
    OUTPUT_KEYS = ("directory",)
    MISSING_INPUT_MESSAGE = "No directory or dir_path provided"
    EXPECTED_KIND = "directory"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "directory": ("DIRECTORY", {"description": "Path to directory"}),
            },
            "optional": {},
            "hidden": {},
        }


class _InputVCFContract(CopyInputNode):
    """Input VCF variant file."""
    LEGACY_NODE_ID = "input_vcf"
    DISPLAY_NAME = "Input VCF"
    CATEGORY = "input"
    DESCRIPTION = "Import a VCF variant call file"
    SEARCH_ALIASES = ["vcf", "variants", "input variants"]
    RETURN_TYPES = ("VCF", "VCF_GZ", "VCF_INDEX")
    RETURN_NAMES = ("vcf", "vcf_gz", "vcf_index")
    REQUIRES_EXTERNAL_TOOLS = False
    FORMAT_SPEC_GIT_COMMIT = "da617203a9527537746e200abda2885bec3a822c"
    DOCUMENTATION_URL = (
        "https://github.com/samtools/hts-specs/blob/"
        f"{FORMAT_SPEC_GIT_COMMIT}/VCFv4.5.tex"
    )
    SOURCE_AUTHORITIES = {
        **CopyInputNode.SOURCE_AUTHORITIES,
        "vcf_format_and_indexing": DOCUMENTATION_URL,
    }
    COMMAND = ["cp", "-r", "{inputs.vcf}", "{output}"]
    SOURCE_KEYS = ("vcf", "file_path")
    OUTPUT_KEYS = ("vcf", "vcf_gz", "vcf_index")
    MISSING_INPUT_MESSAGE = "No vcf or file_path provided"
    EXPECTED_KIND = "file"
    DECOMPRESS_GZIP = False
    SIDECAR_SEMANTICS = (
        "A supplied TBI or CSI is staged as the exact <vcf>.tbi or <vcf>.csi sibling. "
        "The index is optional because sequential consumers do not require random access."
    )

    @classmethod
    def _format_outputs(cls, copied: list[Path]) -> dict[str, Any]:
        copied_path = str(copied[0])
        index_path = str(copied[1]) if len(copied) == 2 else ""
        if _is_compressed_vcf(copied[0]):
            return {"vcf": "", "vcf_gz": copied_path, "vcf_index": index_path}
        return {"vcf": copied_path, "vcf_gz": "", "vcf_index": ""}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": (
                    ("VCF", "VCF_GZ"),
                    {
                        "description": (
                            "Path or URL to a VCF file; remote bgzip bytes are preserved"
                        )
                    },
                ),
            },
            "optional": {
                "vcf_index": (
                    "VCF_INDEX",
                    {
                        "default": "",
                        "description": (
                            "Optional TBI or CSI staged as an exact compressed-VCF sibling"
                        ),
                    },
                ),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation

        vcf = cls._source_value(inputs)
        index = inputs.get("vcf_index")
        if index in (None, ""):
            return True
        if not _is_compressed_vcf(vcf):
            return "Input 'vcf_index' is only valid with a bgzip-compressed VCF"
        if not _vcf_index_suffix(index):
            return "Input 'vcf_index' must end in .tbi or .csi"
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))

        cls = self.__class__
        context = kwargs.get("context")
        out_dir = cls._output_dir(context, kwargs.get("output_dir"))
        mode = str(kwargs.get("source") or "auto").strip().lower()

        vcf_source = cls._resolve_source(
            cls._source_value(kwargs),
            context,
            mode,
            ncbi_email=kwargs.get("email", ""),
        )
        cls._validate_resolved_source(vcf_source)
        index_value = kwargs.get("vcf_index")
        index_source: Path | None = None
        index_suffix = ""
        if index_value not in (None, ""):
            index_source = cls._resolve_source(
                index_value,
                context,
                mode,
                ncbi_email=kwargs.get("email", ""),
            )
            cls._validate_resolved_source(index_source)
            index_suffix = _vcf_index_suffix(index_value)

        if index_source is None:
            staged_vcf = cls._stage_resolved_source(vcf_source, out_dir)
            return {"outputs": cls._format_outputs([staged_vcf])}

        bundle_dir = Path(tempfile.mkdtemp(prefix=".vcf-bundle-", dir=out_dir))
        try:
            bundled_vcf = cls._stage_resolved_source(vcf_source, bundle_dir)
            bundled_index = cls._stage_resolved_source(
                index_source,
                bundle_dir,
                destination_name=f"{vcf_source.name}{index_suffix}",
            )
            copied = cls._promote_staged_bundle(
                [
                    (bundled_vcf, out_dir / vcf_source.name),
                    (
                        bundled_index,
                        out_dir / f"{vcf_source.name}{index_suffix}",
                    ),
                ]
            )
        finally:
            if bundle_dir.exists():
                cls._remove_path(bundle_dir)
        return {"outputs": cls._format_outputs(copied)}


class _InputGFFContract(CopyInputNode):
    """Input GFF/GTF annotation file."""
    LEGACY_NODE_ID = "input_gff"
    DISPLAY_NAME = "Input GFF/GTF"
    CATEGORY = "input"
    DESCRIPTION = "Import a GFF3 or GTF annotation file"
    SEARCH_ALIASES = ["gff", "gtf", "annotation", "input annotation"]
    RETURN_TYPES = ("GFF_GTF",)
    RETURN_NAMES = ("annotation",)
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://github.com/The-Sequence-Ontology/Specifications/blob/master/gff3.md"
    COMMAND = ["cp", "-r", "{inputs.annotation}", "{output}"]
    SOURCE_KEYS = ("annotation", "file_path")
    OUTPUT_KEYS = ("annotation",)
    MISSING_INPUT_MESSAGE = "No annotation or file_path provided"
    EXPECTED_KIND = "file"
    DECOMPRESS_GZIP = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "annotation": ("GFF_GTF", {"description": "Path or URL to a GFF3/GTF file. http(s)/ftp URLs are downloaded on first use (gzip auto-decompressed)."}),
            },
            "optional": {},
            "hidden": {
                "file_path": ("STRING", {"description": "Alias for annotation (backward compatibility)"}),
            },
        }


class _SampleSheetContract(CopyInputNode):
    """Input sample sheet / metadata CSV."""
    LEGACY_NODE_ID = "input_sample_sheet"
    DISPLAY_NAME = "Sample Sheet"
    CATEGORY = "input"
    DESCRIPTION = "Import a sample sheet CSV with sample metadata"
    SEARCH_ALIASES = ["sample sheet", "metadata", "samples", "csv"]
    RETURN_TYPES = ("SAMPLE_SHEET",)
    RETURN_NAMES = ("sample_sheet",)
    REQUIRES_EXTERNAL_TOOLS = False
    COMMAND = ["cp", "-r", "{inputs.sample_sheet}", "{output}"]
    SOURCE_KEYS = ("sample_sheet", "file_path")
    OUTPUT_KEYS = ("sample_sheet",)
    MISSING_INPUT_MESSAGE = "No sample_sheet or file_path provided"
    EXPECTED_KIND = "file"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sample_sheet": ("SAMPLE_SHEET", {
                    "description": "Path or URL to sample sheet CSV (columns: sample, fastq_1, fastq_2, condition). http(s) URLs are downloaded on first use.",
                }),
            },
            "optional": {},
            "hidden": {},
        }
