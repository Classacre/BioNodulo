"""Pinned Pixi manifest dependency parsing and display projection."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import quote, urlsplit, urlunsplit

from packaging.markers import InvalidMarker, Marker
from packaging.specifiers import InvalidSpecifier, Specifier
from packaging.utils import InvalidName, canonicalize_name
from packaging.version import InvalidVersion, Version


# Pixi 0.68.1 commit a2453cacd4a02bc99ee84b5e6015ec83bbb2d397:
# pixi_spec/src/{lib,detailed,url,git,path,subdirectory,toml}.rs and
# pixi_pypi_spec/src/{lib,toml,version_or_star}.rs.
_CONDA_FIELDS = frozenset(
    (
        "version",
        "url",
        "git",
        "path",
        "branch",
        "rev",
        "tag",
        "subdirectory",
        "build",
        "build-number",
        "file-name",
        "channel",
        "subdir",
        "license",
        "md5",
        "sha256",
    )
)
_PYPI_FIELDS = frozenset(
    (
        "version",
        "extras",
        "path",
        "editable",
        "git",
        "branch",
        "tag",
        "rev",
        "url",
        "subdirectory",
        "index",
        "env-markers",
    )
)
_SOURCE_FIELDS = ("url", "path", "git")
_GIT_REFS = ("branch", "rev", "tag")
_URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*$")
_CONDA_VERSION = re.compile(r"^[A-Za-z0-9_!+.*<>=~|,()\-\s]+$")
_CONDA_VERSION_LITERAL = re.compile(r"^[A-Za-z0-9_!+.\-]+$")
_BUILD_NUMBER = re.compile(r"^(==|!=|<=|>=|<|>)?([0-9]+)$")
_MD5 = re.compile(r"^[0-9a-fA-F]{32}$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class _RenderedSpec:
    """A Pixi Display value paired with the equality identity used by OrderSet."""

    identity: tuple[object, ...]
    display: str


@dataclass(frozen=True)
class _MarkerNode:
    kind: str
    atom: tuple[str, str, str] | None = None
    children: tuple[_MarkerNode, ...] = ()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ValueError(f"{label} must be a string-keyed TOML table")
    return value


def _text(
    value: object,
    *,
    label: str,
    maximum: int = 4096,
    allow_empty: bool = False,
) -> str:
    if type(value) is not str or (not value and not allow_empty) or len(value) > maximum:
        qualifier = "a string" if allow_empty else "a nonempty string"
        raise ValueError(f"{label} must be {qualifier} of at most {maximum} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{label} must not contain control characters")
    return value


def _string_list(value: object, *, label: str) -> tuple[str, ...]:
    if type(value) is not list or len(value) > 256:
        raise ValueError(f"{label} must be a bounded string array")
    return tuple(_text(item, label=f"{label} item", maximum=128) for item in value)


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _inline_table(fields: list[tuple[str, str]]) -> str:
    return "{ " + ", ".join(f"{name} = {value}" for name, value in fields) + " }"


def _normalize_url(value: object, *, label: str) -> str:
    raw = _text(value, label=label)
    if any(character.isspace() for character in raw):
        raise ValueError(f"{label} URL must not contain whitespace")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as error:
        raise ValueError(f"{label} URL is malformed") from error
    if _URL_SCHEME.fullmatch(parsed.scheme) is None:
        raise ValueError(f"{label} URL must contain a valid scheme")
    scheme = parsed.scheme.lower()
    if scheme in ("http", "https", "ftp", "git", "git+http", "git+https", "ssh") and not parsed.hostname:
        raise ValueError(f"{label} URL must contain a host")

    netloc = parsed.netloc
    if parsed.hostname is not None:
        before_host = ""
        if "@" in netloc:
            before_host = netloc.rsplit("@", 1)[0] + "@"
        host = parsed.hostname
        try:
            host = host.encode("idna").decode("ascii").lower()
        except UnicodeError as error:
            raise ValueError(f"{label} URL host is malformed") from error
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        default_port = (scheme in ("http", "git+http") and port == 80) or (
            scheme in ("https", "git+https") and port == 443
        )
        port_text = "" if port is None or default_port else f":{port}"
        netloc = f"{before_host}{host}{port_text}"

    path_parts: list[str] = []
    raw_path_parts = parsed.path.split("/")
    for position, component in enumerate(raw_path_parts):
        if component == ".":
            if position == len(raw_path_parts) - 1:
                path_parts.append("")
            continue
        if component == "..":
            if path_parts and path_parts[-1]:
                path_parts.pop()
            if position == len(raw_path_parts) - 1:
                path_parts.append("")
            continue
        path_parts.append(component)
    path = quote("/".join(path_parts), safe="/%:@!$&'()*+,;=-._~")
    if netloc and not path:
        path = "/"
    query = quote(parsed.query, safe="!$&'()*+,;=:/?@-._~%")
    fragment = quote(parsed.fragment, safe="!$&'()*+,;=:/?@-._~%")
    return urlunsplit((scheme, netloc, path, query, fragment))


def _normalize_subdirectory(value: object, *, label: str) -> str:
    raw = _text(value, label=label, allow_empty=True)
    if raw.startswith(("/", "\\")):
        raise ValueError(f"{label} must be relative")
    components: list[str] = []
    for component in raw.replace("\\", "/").split("/"):
        if component in ("", "."):
            continue
        if component == "..":
            if not components:
                raise ValueError(f"{label} must not escape its root")
            components.pop()
            continue
        components.append(component)
    return "/".join(components)


def _normalize_hash(value: object, *, label: str, pattern: re.Pattern[str]) -> str:
    digest = _text(value, label=label, maximum=64)
    if pattern.fullmatch(digest) is None:
        raise ValueError(f"{label} must be a hexadecimal digest of the exact length")
    return digest.lower()


def _normalize_conda_version(value: object, *, label: str) -> str:
    raw = _text(value, label=label)
    if _CONDA_VERSION.fullmatch(raw) is None:
        raise ValueError(f"{label} version requirement is malformed")
    compact = re.sub(r"\s*([,|()])\s*", r"\1", raw.strip())
    compact = re.sub(r"(<=|>=|==|!=|~=|!~=|<|>)\s+", r"\1", compact)
    if not compact:
        raise ValueError(f"{label} version requirement is malformed")

    def normalize_literal(literal: str) -> str:
        if _CONDA_VERSION_LITERAL.fullmatch(literal) is None:
            raise ValueError(f"{label} version requirement is malformed")
        if literal.count("!") > 1 or literal.count("+") > 1:
            raise ValueError(f"{label} version requirement is malformed")

        def normalize_component(match: re.Match[str]) -> str:
            component = match.group(0)
            return str(int(component)) if component[0].isdigit() else component.lower()

        return re.sub(r"[0-9]+|[A-Za-z]+", normalize_component, literal)

    rendered: list[str] = []
    for term in re.split(r"([,|()])", compact):
        if not term:
            continue
        if term in (",", "|", "(", ")"):
            rendered.append(term)
            continue
        operator = ""
        for candidate in ("!=startswith", "!~=", "~=", "==", "!=", "<=", ">=", "=", "<", ">"):
            if term.startswith(candidate):
                operator = candidate
                term = term[len(candidate) :]
                break
        if term == "*" and operator in ("", "=", "==", "<=", ">="):
            rendered.append("*")
            continue
        wildcard = term.endswith("*")
        if wildcard:
            term = term[:-1].removesuffix(".")
        literal = normalize_literal(term)
        if operator == "":
            rendered.append(f"{literal}.*" if wildcard else f"=={literal}")
        elif operator == "=":
            rendered.append(f"{literal}.*")
        elif wildcard and operator == "!=":
            rendered.append(f"!={literal}.*")
        elif wildcard:
            raise ValueError(f"{label} version wildcard is incompatible with its operator")
        else:
            rendered.append(f"{operator}{literal}")
    return "".join(rendered)


def _normalize_build_number(value: object, *, label: str) -> str:
    raw = _text(value, label=label, maximum=32)
    match = _BUILD_NUMBER.fullmatch(raw)
    if match is None:
        raise ValueError(f"{label} build-number requirement is malformed")
    operator, number = match.groups()
    return f"{operator or '=='}{int(number)}"


def _normalize_channel(value: object, *, label: str) -> str:
    channel = _text(value, label=label)
    if "://" in channel:
        return _normalize_url(channel, label=label).rstrip("/")
    return channel


def _build_matcher_identity(value: str) -> tuple[str, str]:
    if value.startswith("^") and value.endswith("$"):
        return ("regex", value)
    if "*" in value:
        return ("glob", value)
    return ("exact", value)


def _render_conda_table(table: dict[str, object], *, label: str) -> _RenderedSpec:
    unknown = tuple(key for key in table if key not in _CONDA_FIELDS)
    if unknown:
        raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
    sources = tuple(field for field in _SOURCE_FIELDS if field in table)
    if len(sources) > 1:
        raise ValueError(f"{label} must specify only one of url, path, or git")
    refs = tuple(field for field in _GIT_REFS if field in table)
    if refs and sources != ("git",):
        raise ValueError(f"{label} branch, rev, and tag require git")
    if len(refs) > 1:
        raise ValueError(f"{label} must specify only one of branch, rev, or tag")
    if sources and any(
        field in table for field in ("version", "build", "build-number", "file-name", "channel", "subdir")
    ):
        raise ValueError(f"{label} source specifications cannot contain binary match fields")
    if sources and sources != ("url",) and any(field in table for field in ("md5", "sha256")):
        raise ValueError(f"{label} hashes can only accompany a URL or detailed version")

    md5 = _normalize_hash(table["md5"], label=f"{label} md5", pattern=_MD5) if "md5" in table else None
    sha256 = _normalize_hash(table["sha256"], label=f"{label} sha256", pattern=_SHA256) if "sha256" in table else None
    if "subdirectory" in table:
        _text(table["subdirectory"], label=f"{label} subdirectory", allow_empty=True)

    if sources == ("url",):
        url = _normalize_url(table["url"], label=f"{label} url")
        subdirectory = (
            _normalize_subdirectory(table["subdirectory"], label=f"{label} subdirectory")
            if "subdirectory" in table
            else ""
        )
        display = url
        if md5 is not None:
            display += f" md5={md5}"
        if sha256 is not None:
            display += f" sha256={sha256}"
        return _RenderedSpec(("url", url, md5, sha256, subdirectory), display)
    if sources == ("git",):
        git = _normalize_url(table["git"], label=f"{label} git")
        subdirectory = (
            _normalize_subdirectory(table["subdirectory"], label=f"{label} subdirectory")
            if "subdirectory" in table
            else ""
        )
        reference: tuple[str, str] | None = None
        display = git
        if refs:
            reference_value = _text(table[refs[0]], label=f"{label} {refs[0]}")
            reference = (refs[0], reference_value)
            display += f" @ {reference_value}"
        if subdirectory:
            display += f" in {subdirectory}"
        return _RenderedSpec(("git", git, reference, subdirectory), display)
    if sources == ("path",):
        path = _text(table["path"], label=f"{label} path")
        return _RenderedSpec(("path", path), path)

    ordered: list[tuple[str, str]] = []
    identity_fields: list[tuple[str, object]] = []
    if "version" in table:
        version = _normalize_conda_version(table["version"], label=f"{label} version")
        ordered.append(("version", version))
        identity_fields.append(("version", version))
    if "build" in table:
        build = _text(table["build"], label=f"{label} build")
        ordered.append(("build", build))
        identity_fields.append(("build", _build_matcher_identity(build)))
    if "build-number" in table:
        build_number = _normalize_build_number(table["build-number"], label=f"{label} build-number")
        ordered.append(("build_number", build_number))
        identity_fields.append(("build-number", build_number))
    for source_name, display_name in (
        ("file-name", "file_name"),
        ("channel", "channel"),
        ("subdir", "subdir"),
        ("license", "license"),
    ):
        if source_name not in table:
            continue
        item = (
            _normalize_channel(table[source_name], label=f"{label} {source_name}")
            if source_name == "channel"
            else _text(table[source_name], label=f"{label} {source_name}")
        )
        ordered.append((display_name, item))
        identity_fields.append((source_name, item))
    if md5 is not None:
        ordered.append(("md5", md5))
        identity_fields.append(("md5", md5))
    if sha256 is not None:
        ordered.append(("sha256", sha256))
        identity_fields.append(("sha256", sha256))
    if not ordered:
        raise ValueError(f"{label} detailed specification must contain an identifying field")
    display = " ".join(f"{name}={item}" for name, item in ordered)
    return _RenderedSpec(("detailed", *identity_fields), display)


def _render_conda_spec(value: object, *, label: str) -> _RenderedSpec:
    if type(value) is str:
        version = _normalize_conda_version(value, label=label)
        return _RenderedSpec(("version", version), version)
    return _render_conda_table(_mapping(value, label=label), label=label)


def _normalize_pypi_version(value: object, *, label: str) -> str:
    raw = _text(value, label=label)
    if raw == "*":
        return raw
    normalized: list[tuple[Version, str]] = []
    for item in raw.split(","):
        candidate = item.strip()
        if not candidate:
            raise ValueError(f"{label} version requirement is malformed")
        try:
            specifier = Specifier(candidate)
            version_text = specifier.version
            wildcard = version_text.endswith(".*")
            parsed_version = Version(version_text[:-2] if wildcard else version_text)
        except (InvalidSpecifier, InvalidVersion) as error:
            raise ValueError(f"{label} version requirement is malformed") from error
        canonical_version = str(parsed_version) + (".*" if wildcard else "")
        normalized.append((parsed_version, f"{specifier.operator}{canonical_version}"))
    normalized.sort(key=lambda item: item[0])
    return ", ".join(item[1] for item in normalized)


def _normalize_extra(value: str, *, label: str) -> str:
    try:
        return str(canonicalize_name(value, validate=True))
    except InvalidName as error:
        raise ValueError(f"{label} is not a valid extra name") from error


def _normalize_marker(value: object, *, label: str) -> str | None:
    raw = _text(value, label=label)
    try:
        marker = Marker(raw)
    except InvalidMarker as error:
        raise ValueError(f"{label} is malformed") from error

    def marker_operand(item: object) -> tuple[str, bool]:
        operand = getattr(item, "value", None)
        if type(operand) is not str:
            raise ValueError(f"{label} contains a malformed marker operand")
        return operand, type(item).__name__ == "Value"

    def marker_value(value: str) -> str:
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"

    def display_node(node: _MarkerNode, *, parent: str | None = None) -> str:
        if node.kind == "atom":
            assert node.atom is not None
            variable, operator, marker_literal = node.atom
            return f"{variable} {operator} {marker_value(marker_literal)}"
        if node.kind == "true":
            return ""
        if node.kind == "false":
            return "python_version < '0'"
        rendered_children = f" {node.kind} ".join(display_node(child, parent=node.kind) for child in node.children)
        if parent == "and" and node.kind == "or":
            return f"({rendered_children})"
        return rendered_children

    def combine(kind: str, children: list[_MarkerNode]) -> _MarkerNode:
        flattened: list[_MarkerNode] = []
        for child in children:
            if child.kind == "true":
                if kind == "or":
                    return child
                continue
            if child.kind == "false":
                if kind == "and":
                    return child
                continue
            flattened.extend(child.children if child.kind == kind else (child,))
        unique = {child: child for child in flattened}
        atoms = {child.atom for child in unique if child.kind == "atom" and child.atom is not None}
        if kind == "or":
            complements = {"==": "!=", "!=": "==", "<": ">=", ">=": "<", "<=": ">", ">": "<="}
            for variable, operator, marker_literal in atoms:
                if (variable, complements.get(operator), marker_literal) in atoms:
                    return _MarkerNode("true")
        else:
            complements = {"==": "!=", "!=": "==", "<": ">=", ">=": "<", "<=": ">", ">": "<="}
            for variable, operator, marker_literal in atoms:
                if (variable, complements.get(operator), marker_literal) in atoms:
                    return _MarkerNode("false")
        if kind in ("and", "or"):
            bounds: dict[tuple[str, str], tuple[Version, _MarkerNode]] = {}
            retained: list[_MarkerNode] = []
            for child in unique:
                if child.kind != "atom" or child.atom is None:
                    retained.append(child)
                    continue
                variable, operator, marker_literal = child.atom
                if variable != "python_full_version" or operator not in (">", ">=", "<", "<="):
                    retained.append(child)
                    continue
                try:
                    parsed = Version(marker_literal)
                except InvalidVersion:
                    retained.append(child)
                    continue
                direction = "lower" if operator in (">", ">=") else "upper"
                previous = bounds.get((variable, direction))
                if previous is None:
                    bounds[(variable, direction)] = (parsed, child)
                    continue
                previous_version, previous_child = previous
                if direction == "lower":
                    replace = (
                        parsed > previous_version
                        or (
                            parsed == previous_version
                            and operator == ">"
                            and previous_child.atom is not None
                            and previous_child.atom[1] == ">="
                        )
                        if kind == "and"
                        else parsed < previous_version
                        or (
                            parsed == previous_version
                            and operator == ">="
                            and previous_child.atom is not None
                            and previous_child.atom[1] == ">"
                        )
                    )
                else:
                    replace = (
                        parsed < previous_version
                        or (
                            parsed == previous_version
                            and operator == "<"
                            and previous_child.atom is not None
                            and previous_child.atom[1] == "<="
                        )
                        if kind == "and"
                        else parsed > previous_version
                        or (
                            parsed == previous_version
                            and operator == "<="
                            and previous_child.atom is not None
                            and previous_child.atom[1] == "<"
                        )
                    )
                if replace:
                    bounds[(variable, direction)] = (parsed, child)
            retained.extend(child for _, child in bounds.values())
            unique = {child: child for child in retained}
        if kind == "and":
            bound_atoms = [child.atom for child in unique if child.kind == "atom" and child.atom is not None]
            exact_versions = [
                Version(marker_literal.removesuffix(".*"))
                for variable, operator, marker_literal in bound_atoms
                if variable == "python_full_version" and operator == "=="
            ]
            for exact in exact_versions:
                for variable, operator, marker_literal in bound_atoms:
                    if variable != "python_full_version" or operator not in (">", ">=", "<", "<="):
                        continue
                    bound = Version(marker_literal)
                    if (operator == "<" and exact >= bound) or (operator == "<=" and exact > bound):
                        return _MarkerNode("false")
                    if (operator == ">" and exact <= bound) or (operator == ">=" and exact < bound):
                        return _MarkerNode("false")
        opposite = "and" if kind == "or" else "or"
        direct_children = set(unique)
        unique = {
            child: child
            for child in unique
            if child.kind != opposite or not any(grandchild in direct_children for grandchild in child.children)
        }

        def node_sort_key(node: _MarkerNode) -> tuple[object, ...]:
            if node.kind != "atom" or node.atom is None:
                return (1, display_node(node))
            variable, operator, marker_literal = node.atom
            if kind == "and":
                operator_rank = {">": 0, ">=": 0, "==": 1, "!=": 1, "<": 2, "<=": 2}.get(operator, 3)
            else:
                operator_rank = {"<": 0, "<=": 0, "==": 1, "!=": 1, ">": 2, ">=": 2}.get(operator, 3)
            try:
                version = Version(marker_literal.removesuffix(".*"))
            except InvalidVersion:
                return (0, variable, operator_rank, 1, Version("0"), marker_literal)
            return (0, variable, operator_rank, 0, version, "")

        ordered = tuple(sorted(unique, key=node_sort_key))
        if not ordered:
            return _MarkerNode("true")
        return ordered[0] if len(ordered) == 1 else _MarkerNode(kind, children=ordered)

    def parse_node(item: object) -> _MarkerNode:
        if type(item) is tuple and len(item) == 3:
            left, operator, right = item
            left_value, left_is_literal = marker_operand(left)
            operator_value, operator_is_literal = marker_operand(operator)
            right_value, right_is_literal = marker_operand(right)
            if operator_is_literal or left_is_literal == right_is_literal:
                raise ValueError(f"{label} contains a malformed marker comparison")
            if left_is_literal:
                reverse = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "==": "==", "!=": "!="}
                if operator_value not in reverse:
                    raise ValueError(f"{label} contains a marker operator that cannot be reversed")
                left_value, right_value = right_value, left_value
                operator_value = reverse[operator_value]
            if left_value == "python_version":
                left_value = "python_full_version"
                if operator_value in ("in", "not in"):
                    version_groups = [group.split(".") for group in right_value.split()]
                    if not version_groups or any(
                        len(group) != 2 or any(not component.isdigit() for component in group)
                        for group in version_groups
                    ):
                        raise ValueError(f"{label} contains an unsupported python_version membership marker")
                    versions = sorted({(int(group[0]), int(group[1])) for group in version_groups})
                    if operator_value == "in":
                        if len(versions) > 1 and all(
                            major == versions[0][0] and minor == versions[0][1] + position
                            for position, (major, minor) in enumerate(versions)
                        ):
                            major = versions[0][0]
                            return combine(
                                "and",
                                [
                                    _MarkerNode(
                                        "atom",
                                        atom=("python_full_version", ">=", f"{major}.{versions[0][1]}"),
                                    ),
                                    _MarkerNode(
                                        "atom",
                                        atom=("python_full_version", "<", f"{major}.{versions[-1][1] + 1}"),
                                    ),
                                ],
                            )
                        return combine(
                            "or",
                            [
                                _MarkerNode(
                                    "atom",
                                    atom=("python_full_version", "==", f"{major}.{minor}.*"),
                                )
                                for major, minor in versions
                            ],
                        )
                    if any(major != versions[0][0] for major, _ in versions):
                        raise ValueError(f"{label} contains an unsupported cross-major python_version marker")
                    major = versions[0][0]
                    allowed = [_MarkerNode("atom", atom=("python_full_version", "<", f"{major}.{versions[0][1]}"))]
                    for minor in range(versions[0][1] + 1, versions[-1][1]):
                        if (major, minor) not in versions:
                            allowed.append(
                                _MarkerNode("atom", atom=("python_full_version", "==", f"{major}.{minor}.*"))
                            )
                    allowed.append(
                        _MarkerNode("atom", atom=("python_full_version", ">=", f"{major}.{versions[-1][1] + 1}"))
                    )
                    return combine("or", allowed)
                version_parts = right_value.split(".")
                simple_version = all(part.isdigit() for part in version_parts)
                if simple_version and operator_value in ("==", "!="):
                    if any(int(part) != 0 for part in version_parts[2:]):
                        return _MarkerNode("false" if operator_value == "==" else "true")
                    right_value = ".".join(version_parts[:2]) + ".*"
                elif simple_version and operator_value in ("<=", ">"):
                    numbers = [int(part) for part in version_parts[:2]]
                    if len(numbers) == 1:
                        numbers.append(0)
                    numbers[-1] += 1
                    right_value = ".".join(str(number) for number in numbers)
                    operator_value = "<" if operator_value == "<=" else ">="
            return _MarkerNode("atom", atom=(left_value, operator_value, right_value))
        if type(item) is not list or not item:
            raise ValueError(f"{label} contains a malformed marker tree")
        nodes = [parse_node(item[position]) for position in range(0, len(item), 2)]
        operators = [item[position] for position in range(1, len(item), 2)]
        if any(operator not in ("and", "or") for operator in operators):
            raise ValueError(f"{label} contains a malformed marker operator")
        position = 0
        while position < len(operators):
            if operators[position] == "and":
                nodes[position : position + 2] = [combine("and", nodes[position : position + 2])]
                operators.pop(position)
            else:
                position += 1
        return combine("or", nodes) if operators else nodes[0]

    normalized = parse_node(marker._markers)
    return None if normalized.kind == "true" else display_node(normalized)


def _render_pypi_spec(value: object, *, label: str) -> _RenderedSpec:
    if type(value) is str:
        version = _normalize_pypi_version(value, label=label)
        return _RenderedSpec(("registry", version, None, (), None), _toml_string(version))

    table = _mapping(value, label=label)
    unknown = tuple(key for key in table if key not in _PYPI_FIELDS)
    if unknown:
        raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
    refs = tuple(field for field in _GIT_REFS if field in table)
    if refs and "git" not in table:
        raise ValueError(f"{label} branch, rev, and tag require git")
    if len(refs) > 1:
        raise ValueError(f"{label} must specify only one of branch, rev, or tag")
    sources = tuple(field for field in _SOURCE_FIELDS if field in table)
    if len(sources) > 1 or (sources and "index" in table):
        raise ValueError(f"{label} must specify exactly one package source")
    if sources and "version" in table:
        raise ValueError(f"{label} version cannot accompany a source dependency")
    if "subdirectory" in table:
        _text(table["subdirectory"], label=f"{label} subdirectory", allow_empty=True)
    editable_value = table.get("editable")
    if editable_value is not None and type(editable_value) is not bool:
        raise ValueError(f"{label} editable must be a boolean")

    extras = tuple(
        _normalize_extra(extra, label=f"{label} extras item")
        for extra in _string_list(table.get("extras", []), label=f"{label} extras")
    )
    marker = _normalize_marker(table["env-markers"], label=f"{label} env-markers") if "env-markers" in table else None
    fields: list[tuple[str, str]] = []
    if sources == ("git",):
        git = _normalize_url(table["git"], label=f"{label} git")
        subdirectory = (
            _normalize_subdirectory(table["subdirectory"], label=f"{label} subdirectory")
            if "subdirectory" in table
            else ""
        )
        fields.append(("git", _toml_string(git)))
        reference: tuple[str, str] | None = None
        if refs:
            reference_value = _text(table[refs[0]], label=f"{label} {refs[0]}")
            reference = (refs[0], reference_value)
            fields.append((refs[0], _toml_string(reference_value)))
        if subdirectory:
            fields.append(("subdirectory", _toml_string(subdirectory)))
        identity: tuple[object, ...] = ("git", git, reference, subdirectory, extras, marker)
    elif sources == ("path",):
        path = _text(table["path"], label=f"{label} path")
        fields.append(("path", _toml_string(path)))
        if editable_value is True:
            fields.append(("editable", "true"))
        identity = ("path", path, editable_value, extras, marker)
    elif sources == ("url",):
        url = _normalize_url(table["url"], label=f"{label} url")
        subdirectory = (
            _normalize_subdirectory(table["subdirectory"], label=f"{label} subdirectory")
            if "subdirectory" in table
            else ""
        )
        fields.append(("url", _toml_string(url)))
        if subdirectory:
            fields.append(("subdirectory", _toml_string(subdirectory)))
        identity = ("url", url, subdirectory, extras, marker)
    else:
        version = _normalize_pypi_version(table.get("version", "*"), label=f"{label} version")
        index = _normalize_url(table["index"], label=f"{label} index") if "index" in table else None
        if not extras and index is None and marker is None:
            return _RenderedSpec(("registry", version, None, (), None), _toml_string(version))
        fields.append(("version", _toml_string(version)))
        identity = ("registry", version, index, extras, marker)

    if extras:
        fields.append(("extras", "[" + ", ".join(_toml_string(extra) for extra in extras) + "]"))
    if not sources and "index" in table:
        assert index is not None
        fields.append(("index", _toml_string(index)))
    if marker is not None:
        fields.append(("env-markers", _toml_string(marker)))
    return _RenderedSpec(identity, _inline_table(fields))
