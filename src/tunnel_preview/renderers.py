from __future__ import annotations

import html
import json
from pathlib import Path

from fastapi.responses import HTMLResponse

from .config import AppConfig
from .urls import markdown_link_url, raw_pdf_url

CSP = (
    "default-src 'none'; "
    "img-src 'self' data:; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "frame-src 'self'; "
    "media-src 'self'; "
    "object-src 'self'; "
    "base-uri 'none'"
)


def render_file(path: Path, request_path: str, config: AppConfig) -> HTMLResponse:
    if path.stat().st_size > config.renderers.max_file_bytes:
        return _page(path.name, "<p>文件过大，请用 SSH/编辑器查看</p>", status_code=413)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        escaped_src = html.escape(raw_pdf_url(request_path), quote=True)
        body = f'<iframe class="pdf" src="{escaped_src}" title="{html.escape(path.name)}"></iframe>'
        return _page(path.name, body)
    if suffix == ".md":
        text = path.read_text(encoding="utf-8", errors="replace")
        return _page(path.name, _render_markdown(text, request_path))
    if suffix == ".json":
        return _page(path.name, _render_json(path.read_text(encoding="utf-8", errors="replace")))
    if suffix in {".yaml", ".yml"}:
        return _page(path.name, _render_text(path.read_text(encoding="utf-8", errors="replace")))
    return _page(path.name, "<p>渲染失败：没有可用 renderer。</p>", status_code=500)


def _render_json(text: str) -> str:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return _render_text(text)
    return _render_text(json.dumps(parsed, ensure_ascii=False, indent=2))


def _render_markdown(text: str, request_path: str = "") -> str:
    blocks: list[str] = []
    in_code = False
    code_lines: list[str] = []
    paragraph: list[str] = []
    table_rows: list[list[str]] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(f"<p>{_render_inline(' '.join(paragraph), request_path)}</p>")
            paragraph.clear()

    def flush_table() -> None:
        if table_rows:
            blocks.append(_render_table(table_rows, request_path))
            table_rows.clear()

    for line in text.splitlines():
        if line.startswith("```"):
            if in_code:
                blocks.append(
                    _copyable_pre(f"<code>{html.escape(chr(10).join(code_lines))}</code>")
                )
                code_lines.clear()
                in_code = False
            else:
                flush_paragraph()
                flush_table()
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_table()
        elif stripped.startswith("#"):
            flush_paragraph()
            flush_table()
            level = min(len(stripped) - len(stripped.lstrip("#")), 3)
            title = stripped[level:].strip()
            blocks.append(f"<h{level}>{html.escape(title)}</h{level}>")
        elif _looks_like_table_row(stripped):
            flush_paragraph()
            if _is_table_separator(stripped):
                continue
            table_rows.append(_parse_table_row(stripped))
        else:
            flush_table()
            paragraph.append(stripped)
    if in_code:
        blocks.append(_copyable_pre(f"<code>{html.escape(chr(10).join(code_lines))}</code>"))
    flush_table()
    flush_paragraph()
    return "\n".join(blocks) or "<p></p>"


def _render_inline(text: str, request_path: str) -> str:
    rendered: list[str] = []
    position = 0
    while position < len(text):
        link_start = text.find("[", position)
        if link_start == -1:
            rendered.append(html.escape(text[position:]))
            break
        label_end = text.find("]", link_start + 1)
        if label_end == -1 or label_end + 1 >= len(text) or text[label_end + 1] != "(":
            rendered.append(html.escape(text[position : link_start + 1]))
            position = link_start + 1
            continue
        href_start = label_end + 2
        href_end = _find_markdown_href_end(text, href_start)
        if href_end == -1:
            rendered.append(html.escape(text[position : link_start + 1]))
            position = link_start + 1
            continue
        href_text = text[href_start:href_end]
        if not href_text or any(char.isspace() for char in href_text):
            rendered.append(html.escape(text[position : href_end + 1]))
            position = href_end + 1
            continue
        rendered.append(html.escape(text[position:link_start]))
        label = html.escape(text[link_start + 1 : label_end])
        href = markdown_link_url(href_text, request_path)
        if href is None:
            rendered.append(label)
        else:
            rendered.append(f'<a href="{html.escape(href, quote=True)}">{label}</a>')
        position = href_end + 1
    return "".join(rendered)


def _find_markdown_href_end(text: str, start: int) -> int:
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                return index
            depth -= 1
    return -1


def _looks_like_table_row(line: str) -> bool:
    return "|" in line and line.count("|") >= 2


def _is_table_separator(line: str) -> bool:
    cells = _parse_table_row(line)
    return bool(cells) and all(set(cell.strip()) <= {"-", ":"} and "-" in cell for cell in cells)


def _parse_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def _render_table(rows: list[list[str]], request_path: str = "") -> str:
    if not rows:
        return ""
    header = rows[0]
    body_rows = rows[1:]
    header_html = "".join(f"<th>{_render_inline(cell, request_path)}</th>" for cell in header)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{_render_inline(cell, request_path)}</td>" for cell in row) + "</tr>"
        for row in body_rows
    )
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"


def _render_text(text: str) -> str:
    lines = html.escape(text).splitlines() or [""]
    rows = "\n".join(
        f'<span class="line"><span class="num">{number}</span>{line}</span>'
        for number, line in enumerate(lines, start=1)
    )
    return _copyable_pre(rows)


def _copyable_pre(content: str) -> str:
    return (
        '<div class="copy-block">'
        '<button class="copy-button" type="button" aria-label="Copy block">Copy</button>'
        f"<pre>{content}</pre>"
        "</div>"
    )


def _page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    escaped_title = html.escape(title)
    html_body = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    body {{
      margin: 0;
      background: #f7f8fa;
      color: #17202a;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.6;
    }}
    main {{ max-width: 1080px; margin: 0 auto; padding: 28px 20px 56px; }}
    h1 {{ font-size: 24px; margin: 0 0 18px; }}
    h2 {{ font-size: 20px; margin-top: 24px; }}
    h3 {{ font-size: 17px; margin-top: 20px; }}
    a {{ color: #176b87; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0;
      background: white;
    }}
    th, td {{
      border: 1px solid #dbe2eb;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #eef2f6; }}
    .copy-block {{
      position: relative;
      margin: 16px 0;
    }}
    .copy-button {{
      position: absolute;
      top: 8px;
      right: 8px;
      border: 1px solid #314050;
      border-radius: 6px;
      padding: 4px 8px;
      background: #f7f8fa;
      color: #17202a;
      cursor: pointer;
      font: inherit;
      font-size: 12px;
      line-height: 1.2;
    }}
    .copy-button:hover {{ background: #e8f5f3; }}
    .copy-button:focus {{ outline: 2px solid #68b0ab; outline-offset: 2px; }}
    pre {{
      overflow: auto;
      background: #101820;
      color: #e8eef4;
      border-radius: 8px;
      padding: 16px 64px 16px 16px;
      line-height: 1.5;
    }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .line {{ display: block; white-space: pre; }}
    .num {{
      display: inline-block;
      min-width: 3em;
      padding-right: 1em;
      color: #9aa8b6;
      user-select: none;
      text-align: right;
    }}
    .pdf {{
      width: 100%;
      height: calc(100vh - 120px);
      border: 1px solid #dbe2eb;
      border-radius: 8px;
      background: white;
    }}
  </style>
</head>
<body><main><h1>{escaped_title}</h1>{body}</main>
<script src="/__assets__/copy.js" defer></script></body>
</html>"""
    return HTMLResponse(
        html_body,
        status_code=status_code,
        headers={"Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff"},
    )
