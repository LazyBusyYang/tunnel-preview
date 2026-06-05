from __future__ import annotations

import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

DEFAULT_CONFIG_FILE = "tunnel-preview.toml"
MAX_PAGE_SIZE = 1000


@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int | None = 5500
    page_size: int = 100


@dataclass(frozen=True)
class RendererConfig:
    max_file_bytes: int = 5_242_880


@dataclass(frozen=True)
class FilesConfig:
    direct: tuple[str, ...] = (".html", ".jpg", ".jpeg", ".png", ".webp", ".mp4")
    rendered: tuple[str, ...] = (".md", ".pdf", ".json", ".yaml", ".yml")


@dataclass(frozen=True)
class HideConfig:
    patterns: tuple[str, ...] = (".git/", ".env")


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig = ServerConfig()
    renderers: RendererConfig = RendererConfig()
    files: FilesConfig = FilesConfig()
    hide: HideConfig = HideConfig()
    root: Path = Path.cwd()
    port_was_explicit: bool = False


def load_config(
    *,
    root: Path,
    config_path: Path | None = None,
    host: str | None = None,
    port: int | None = None,
    page_size: int | None = None,
) -> AppConfig:
    root = root.resolve()
    config = AppConfig(root=root)
    data: dict[str, object] = {}

    if config_path is not None:
        if not config_path.exists():
            raise ValueError(f"Config file does not exist: {config_path}")
        data = _read_toml(config_path)
        config = _apply_data(config, data)
        config = replace(config, port_was_explicit="server" in data and "port" in data["server"])
    else:
        discovered = root / DEFAULT_CONFIG_FILE
        if discovered.exists():
            data = _read_toml(discovered)
            config = _apply_data(config, data)
            config = replace(
                config,
                port_was_explicit="server" in data and "port" in data["server"],
            )
        else:
            config = replace(config, port_was_explicit=False)

    if host is not None:
        config = replace(config, server=replace(config.server, host=host))
    if port is not None:
        config = replace(config, server=replace(config.server, port=port), port_was_explicit=True)
    if page_size is not None:
        config = replace(config, server=replace(config.server, page_size=page_size))

    _validate(config)
    return config


def _read_toml(path: Path) -> dict[str, object]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid TOML config: {path}: {exc}") from exc


def _apply_data(config: AppConfig, data: dict[str, object]) -> AppConfig:
    server = data.get("server", {})
    renderers = data.get("renderers", {})
    files = data.get("files", {})
    hide = data.get("hide", {})

    if not isinstance(server, dict):
        raise ValueError("server config must be a table")
    if not isinstance(renderers, dict):
        raise ValueError("renderers config must be a table")
    if not isinstance(files, dict):
        raise ValueError("files config must be a table")
    if not isinstance(hide, dict):
        raise ValueError("hide config must be a table")

    server_config = replace(
        config.server,
        host=server.get("host", config.server.host),
        port=server.get("port", config.server.port),
        page_size=server.get("page_size", config.server.page_size),
    )
    renderer_config = replace(
        config.renderers,
        max_file_bytes=renderers.get("max_file_bytes", config.renderers.max_file_bytes),
    )
    files_config = replace(
        config.files,
        direct=tuple(files.get("direct", config.files.direct)),
        rendered=tuple(files.get("rendered", config.files.rendered)),
    )
    hide_config = replace(config.hide, patterns=tuple(hide.get("patterns", config.hide.patterns)))
    return replace(
        config,
        server=server_config,
        renderers=renderer_config,
        files=files_config,
        hide=hide_config,
    )


def _validate(config: AppConfig) -> None:
    if not isinstance(config.server.host, str) or not config.server.host:
        raise ValueError("server.host must be a non-empty string")
    if config.server.port is not None and (
        not isinstance(config.server.port, int) or not 1 <= config.server.port <= 65535
    ):
        raise ValueError("server.port must be an integer from 1 to 65535")
    if (
        not isinstance(config.server.page_size, int)
        or config.server.page_size <= 0
        or config.server.page_size > MAX_PAGE_SIZE
    ):
        raise ValueError(f"server.page_size must be an integer from 1 to {MAX_PAGE_SIZE}")
    if not isinstance(config.renderers.max_file_bytes, int) or config.renderers.max_file_bytes <= 0:
        raise ValueError("renderers.max_file_bytes must be a positive integer")

    direct = _validate_extensions(config.files.direct, "files.direct")
    rendered = _validate_extensions(config.files.rendered, "files.rendered")
    overlap = direct & rendered
    if overlap:
        raise ValueError(f"files.direct and files.rendered overlap: {sorted(overlap)}")

    for pattern in config.hide.patterns:
        if not isinstance(pattern, str) or not pattern:
            raise ValueError("hide.patterns entries must be non-empty strings")
        if pattern.startswith("!"):
            raise ValueError("hide.patterns does not support negation")


def _validate_extensions(values: tuple[str, ...], name: str) -> set[str]:
    extensions: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.startswith(".") or value != value.lower():
            raise ValueError(f"{name} entries must be lower-case extensions beginning with '.'")
        extensions.add(value)
    return extensions
