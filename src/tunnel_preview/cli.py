from __future__ import annotations

import argparse
import socket
from pathlib import Path

import uvicorn

from .app import create_app
from .config import load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tunnel-preview")
    parser.add_argument("path", nargs="?", help="Project root to preview.")
    parser.add_argument("--root", help="Project root to preview.")
    parser.add_argument("--host", help="Host address to bind.")
    parser.add_argument("--port", type=int, help="Port to bind. Omit for an OS-assigned port.")
    parser.add_argument("--config", type=Path, help="Explicit tunnel-preview.toml path.")
    parser.add_argument("--page-size", type=int, help="Directory entries per page.")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    root_arg = args.root or args.path or "."
    config = load_config(
        root=Path(root_arg),
        config_path=args.config,
        host=args.host,
        port=args.port,
        page_size=args.page_size,
    )
    port = config.server.port if config.port_was_explicit else 0
    try:
        sock = socket.create_server((config.server.host, port))
    except OSError as exc:
        raise SystemExit(f"Failed to bind {config.server.host}:{port}: {exc}") from exc
    actual_port = sock.getsockname()[1]
    app = create_app(config)

    print(f"Serving {config.root}", flush=True)
    print(f"Local URL: http://{config.server.host}:{actual_port}/", flush=True)
    print("Press Ctrl-C to stop.", flush=True)
    server_config = uvicorn.Config(app)
    uvicorn.Server(server_config).run(sockets=[sock])


if __name__ == "__main__":
    main()
