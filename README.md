# tunnel-preview

`tunnel-preview` is a small, restricted file preview server for remote
development. It is designed for SSH tunnels, Cursor/VS Code port forwarding, and
other cases where files live on a remote machine but you want to inspect HTML,
images, video, Markdown, JSON/YAML, or PDF through a browser.

It is intentionally not a general static file server: it only exposes supported
file types, applies root path checks, hides configured paths such as `.git/` and
`.env`, and returns a uniform `404` for unsupported or hidden files.

## Install

For local development, create a virtual environment with `uv`, install the
project in editable mode, then run the CLI from that environment:

```bash
uv venv
source .venv/bin/activate
uv pip install -e '.[dev]'
tunnel-preview
```

The `source .venv/bin/activate` step matters: `uv pip install -e '.[dev]'`
installs the `tunnel-preview` console script into `.venv/bin/`, not into your
global shell `PATH`.

To verify where the command comes from after activation:

```bash
which tunnel-preview
# /path/to/tunnel-preview/.venv/bin/tunnel-preview
```

If you do not want to activate the environment, run the CLI by path:

```bash
.venv/bin/tunnel-preview
```

Or let `uv` run it inside the project environment:

```bash
uv run tunnel-preview
```

To make the project CLI available whenever you open a shell, add the local
virtualenv `bin` directory to your shell profile. For Bash:

```bash
echo 'export PATH="/path/to/tunnel-preview/.venv/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Replace `/path/to/tunnel-preview` with the absolute path to this repository.
This is convenient on a dedicated development machine, but remember that it
points to this checkout's virtual environment.

## Quick Start

Run it from the project directory you want to preview:

```bash
tunnel-preview
```

By default the CLI uses the current working directory as the preview root,
listens on `127.0.0.1`, and chooses an available port for quick startup. The
terminal prints the URL:

```text
Serving /workspace/project
Local URL: http://127.0.0.1:58231/
Press Ctrl-C to stop.
```

Common options:

```bash
# Preview a specific directory
tunnel-preview /workspace/project

# Bind a fixed port
tunnel-preview --port 5500

# Bind all interfaces, useful when you explicitly want LAN/container access
tunnel-preview --host 0.0.0.0

# Use an explicit config file
tunnel-preview --config tunnel-preview.toml
```

## Configuration

Optional project config lives in `tunnel-preview.toml`:

```toml
[server]
host = "127.0.0.1"
port = 5500
page_size = 100

[files]
direct = [".html", ".jpg", ".jpeg", ".png", ".webp", ".mp4"]
rendered = [".md", ".pdf", ".json", ".yaml", ".yml"]

[hide]
patterns = [".git/", ".env"]
```

See `docs/` for the detailed CLI, config, security, renderer, and testing
contracts.

## Docker

Build and run locally:

```bash
docker build -t tunnel-preview:local .
docker run --rm -p 5500:5500 -v "$PWD:/workspace:ro" tunnel-preview:local \
  --host 0.0.0.0 --port 5500
```

## Development Checks

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest tests/unit tests/integration
```
