from __future__ import annotations

from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from .config import AppConfig


class NotFoundPath(ValueError):
    """Raised when a path must be hidden behind a uniform 404."""


def resolve_request_path(raw_path: str, config: AppConfig) -> Path:
    if "\x00" in raw_path:
        raise NotFoundPath
    try:
        decoded = unquote(raw_path)
    except UnicodeDecodeError as exc:
        raise NotFoundPath from exc
    if "\x00" in decoded:
        raise NotFoundPath

    relative = PurePosixPath(decoded.lstrip("/"))
    if relative.is_absolute():
        raise NotFoundPath

    target = (config.root / Path(*relative.parts)).resolve()
    if not _is_relative_to(target, config.root):
        raise NotFoundPath
    if not target.exists():
        raise NotFoundPath
    if is_hidden(target, config):
        raise NotFoundPath
    return target


def is_hidden(path: Path, config: AppConfig) -> bool:
    try:
        relative = path.resolve().relative_to(config.root)
    except ValueError:
        return True

    parts = relative.parts
    rel_posix = relative.as_posix()
    is_dir = path.is_dir()
    for pattern in config.hide.patterns:
        if _matches_pattern(pattern, parts, rel_posix, is_dir):
            return True
    return False


def is_supported_file(path: Path, config: AppConfig) -> bool:
    suffix = path.suffix.lower()
    return suffix in config.files.direct or suffix in config.files.rendered


def file_kind(path: Path, config: AppConfig) -> str | None:
    suffix = path.suffix.lower()
    if suffix in config.files.direct:
        return "direct"
    if suffix in config.files.rendered:
        return "rendered"
    return None


def visible_directory_entries(path: Path, config: AppConfig) -> list[Path]:
    entries: list[Path] = []
    for child in path.iterdir():
        try:
            resolved = child.resolve()
        except OSError:
            continue
        if not _is_relative_to(resolved, config.root):
            continue
        if is_hidden(resolved, config):
            continue
        if resolved.is_dir() or is_supported_file(resolved, config):
            entries.append(resolved)
    return sorted(entries, key=lambda item: (not item.is_dir(), item.name.lower(), item.name))


def _matches_pattern(pattern: str, parts: tuple[str, ...], rel_posix: str, is_dir: bool) -> bool:
    directory_only = pattern.endswith("/")
    normalized = pattern.rstrip("/")
    if directory_only and not is_dir:
        return False
    if "/" in normalized:
        return rel_posix == normalized or rel_posix.startswith(f"{normalized}/")
    if normalized.startswith("*."):
        return any(PurePosixPath(part).match(normalized) for part in parts)
    return normalized in parts


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
