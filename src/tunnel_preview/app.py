from __future__ import annotations

import html
import mimetypes
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response

from .config import AppConfig
from .renderers import render_file
from .security import NotFoundPath, file_kind, resolve_request_path, visible_directory_entries
from .urls import public_path_url


def create_app(config: AppConfig) -> FastAPI:
    app = FastAPI(title="tunnel-preview")
    app.state.config = config

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        return response

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "root": config.root.name}

    @app.get("/__raw__/{request_path:path}")
    def raw_rendered_asset(request_path: str) -> Response:
        path = _resolve_public_path(request_path, config)
        if path.suffix.lower() != ".pdf":
            raise HTTPException(status_code=404)
        return FileResponse(path, media_type="application/pdf")

    @app.get("/{request_path:path}")
    def preview(request_path: str = "", page: int = 1) -> Response:
        path = _resolve_public_path(request_path, config)
        if path.is_dir():
            return _directory_page(path, request_path, page, config)
        kind = file_kind(path, config)
        if kind == "direct":
            media_type = mimetypes.guess_type(path.name)[0]
            return FileResponse(path, media_type=media_type)
        if kind == "rendered":
            return render_file(path, request_path, config)
        raise HTTPException(status_code=404)

    return app


def _resolve_public_path(request_path: str, config: AppConfig) -> Path:
    try:
        path = resolve_request_path(request_path, config)
    except NotFoundPath as exc:
        raise HTTPException(status_code=404) from exc
    if not path.is_dir() and file_kind(path, config) is None:
        raise HTTPException(status_code=404)
    return path


def _directory_page(path: Path, request_path: str, page: int, config: AppConfig) -> HTMLResponse:
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    entries = visible_directory_entries(path, config)
    page_size = config.server.page_size
    start = (page - 1) * page_size
    page_entries = entries[start : start + page_size]
    total_pages = max(1, (len(entries) + page_size - 1) // page_size)
    if page > total_pages:
        page_entries = []

    title = "/" + request_path.strip("/")
    rows = []
    if path != config.root:
        parent = _href_for(path.parent, config)
        rows.append(f'<li class="dir"><a href="{html.escape(parent, quote=True)}">../</a></li>')
    for entry in page_entries:
        href = _href_for(entry, config)
        label = entry.name + ("/" if entry.is_dir() else "")
        css = "dir" if entry.is_dir() else "file"
        escaped_href = html.escape(href, quote=True)
        escaped_label = html.escape(label)
        rows.append(f'<li class="{css}"><a href="{escaped_href}">{escaped_label}</a></li>')

    pagination = ""
    if total_pages > 1:
        links = []
        if page > 1:
            links.append(f'<a href="?page={page - 1}">上一页</a>')
        links.append(f"<span>第 {page} / {total_pages} 页</span>")
        if page < total_pages:
            links.append(f'<a href="?page={page + 1}">下一页</a>')
        pagination = f'<nav class="pager">{" ".join(links)}</nav>'

    body = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{
      margin: 0;
      background: #f7f8fa;
      color: #17202a;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.6;
    }}
    main {{ max-width: 960px; margin: 0 auto; padding: 28px 20px 56px; }}
    h1 {{ font-size: 24px; margin: 0 0 18px; }}
    ul {{
      list-style: none;
      padding: 0;
      margin: 0;
      border: 1px solid #dbe2eb;
      border-radius: 8px;
      background: white;
      overflow: hidden;
    }}
    li + li {{ border-top: 1px solid #dbe2eb; }}
    a {{ display: block; color: #176b87; text-decoration: none; padding: 10px 14px; }}
    a:hover {{ background: #e8f5f3; }}
    .dir a {{ font-weight: 650; }}
    .pager {{ display: flex; gap: 12px; align-items: center; margin-top: 14px; }}
    .pager a {{ display: inline; padding: 0; }}
  </style>
</head>
<body><main><h1>{html.escape(title)}</h1><ul>{"".join(rows)}</ul>{pagination}</main></body>
</html>"""
    return HTMLResponse(body)


def _href_for(path: Path, config: AppConfig) -> str:
    relative = path.relative_to(config.root).as_posix()
    return public_path_url(relative)
