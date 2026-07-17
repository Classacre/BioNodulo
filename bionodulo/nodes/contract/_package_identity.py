"""Pure standards-backed package identity validation."""

from packaging.utils import InvalidName, InvalidWheelFilename, canonicalize_name, parse_wheel_filename
from packaging.version import InvalidVersion, Version


def validate_pypi_package_name(name: str) -> None:
    try:
        normalized_name = canonicalize_name(name, validate=True)
    except InvalidName as error:
        raise ValueError("PyPI artifact name must be a valid Python project name") from error
    if normalized_name != name:
        raise ValueError("PyPI artifact name must use canonical normalized spelling")


def validate_pypi_wheel_identity(*, name: str, version: str, filename: str) -> None:
    try:
        wheel_name, wheel_version, _, _ = parse_wheel_filename(filename)
    except InvalidWheelFilename as error:
        raise ValueError("PyPI artifact must be a valid wheel filename") from error
    if wheel_name != name:
        raise ValueError("PyPI wheel name does not match the locked package name")
    try:
        declared_version = Version(version)
    except InvalidVersion as error:
        raise ValueError("PyPI artifact version must be a valid PEP 440 version") from error
    if str(declared_version) != version:
        raise ValueError("PyPI artifact version must use canonical PEP 440 spelling")
    if str(wheel_version) != version:
        raise ValueError("PyPI wheel version does not match the locked package version")


def parse_pypi_wheel_tags(filename: str) -> tuple[tuple[str, str, str], ...]:
    """Return normalized wheel tag triples through the standards-backed parser."""

    try:
        _, _, _, tags = parse_wheel_filename(filename)
    except InvalidWheelFilename as error:
        raise ValueError("PyPI artifact must be a valid wheel filename") from error
    return tuple(sorted((tag.interpreter, tag.abi, tag.platform) for tag in tags))


def parse_python_runtime_release(version: str) -> tuple[int, ...]:
    """Return the PEP 440 release tuple for a locked Python runtime version."""

    try:
        return Version(version).release
    except InvalidVersion as error:
        raise ValueError("locked Python runtime version must be valid PEP 440") from error
