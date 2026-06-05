from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import quote, urlsplit

SAFE_EXTERNAL_SCHEMES = {"http", "https", "mailto"}


def quote_path(path: str) -> str:
    return quote(path, safe="/")


def public_path_url(path: str) -> str:
    stripped = path.strip("/")
    return "/" if not stripped else f"/{quote_path(stripped)}"


def raw_pdf_url(request_path: str) -> str:
    return f"/__raw__/{quote_path(request_path.lstrip('/'))}"


def markdown_link_url(href: str, request_path: str) -> str | None:
    split = urlsplit(href)
    if split.scheme:
        return href if split.scheme.lower() in SAFE_EXTERNAL_SCHEMES else None
    if split.netloc:
        return None
    if href.startswith("#"):
        return href
    if href.startswith("/"):
        return public_path_url(href)

    target_path = split.path
    base = PurePosixPath(request_path).parent
    normalized = (base / target_path).as_posix()
    encoded = public_path_url(normalized)
    if split.query:
        encoded = f"{encoded}?{quote(split.query, safe='=&;:,')}"
    if split.fragment:
        encoded = f"{encoded}#{quote(split.fragment)}"
    return encoded
