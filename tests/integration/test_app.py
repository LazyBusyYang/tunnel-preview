from pathlib import Path

from fastapi.testclient import TestClient

from tunnel_preview.app import create_app
from tunnel_preview.config import load_config


def client_for(root: Path, page_size: int | None = None) -> TestClient:
    return TestClient(create_app(load_config(root=root, page_size=page_size)))


def test_directory_lists_supported_entries_only(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>Hello</h1>", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Read me", encoding="utf-8")
    (tmp_path / "private.txt").write_text("no", encoding="utf-8")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")

    response = client_for(tmp_path).get("/")

    assert response.status_code == 200
    assert "index.html" in response.text
    assert "README.md" in response.text
    assert "private.txt" not in response.text
    assert ".env" not in response.text


def test_healthz_returns_root_basename(tmp_path: Path) -> None:
    response = client_for(tmp_path).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "root": tmp_path.name}


def test_directory_links_percent_encode_special_characters(tmp_path: Path) -> None:
    (tmp_path / "hello #?.html").write_text("<h1>Hello</h1>", encoding="utf-8")

    listing = client_for(tmp_path).get("/")
    direct = client_for(tmp_path).get("/hello%20%23%3F.html")

    assert "hello%20%23%3F.html" in listing.text
    assert direct.status_code == 200
    assert "<h1>Hello</h1>" in direct.text


def test_direct_file_is_returned_with_content_type(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>Hello</h1>", encoding="utf-8")

    response = client_for(tmp_path).get("/index.html")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<h1>Hello</h1>" in response.text


def test_rendered_markdown_escapes_html(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Title\n<script>alert(1)</script>", encoding="utf-8")

    response = client_for(tmp_path).get("/README.md")

    assert response.status_code == 200
    assert "Content-Security-Policy" in response.headers
    assert "<h1>Title</h1>" in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text


def test_rendered_markdown_links_and_tables(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text(
        "\n".join(
            [
                "# Docs",
                "[Guide](guide.html)",
                "| Name | Value |",
                "| --- | --- |",
                "| [Local](guide.html) | [External](https://example.com) |",
            ]
        ),
        encoding="utf-8",
    )
    (docs / "guide.html").write_text("<h1>Guide</h1>", encoding="utf-8")

    response = client_for(tmp_path).get("/docs/README.md")

    assert response.status_code == 200
    assert '<a href="/docs/guide.html">Guide</a>' in response.text
    assert "<table>" in response.text
    assert "<th>Name</th>" in response.text
    assert '<td><a href="/docs/guide.html">Local</a></td>' in response.text
    assert '<td><a href="https://example.com">External</a></td>' in response.text


def test_rendered_markdown_drops_unsafe_link_schemes(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "[Bad](javascript:alert(1)) [Data](data:text/html,hi) [Ok](https://example.com)",
        encoding="utf-8",
    )

    response = client_for(tmp_path).get("/README.md")

    assert response.status_code == 200
    assert "javascript:" not in response.text
    assert "data:text" not in response.text
    assert ">Bad<" not in response.text
    assert "<p>Bad Data " in response.text
    assert '<a href="https://example.com">Ok</a>' in response.text


def test_pdf_wrapper_percent_encodes_raw_url(tmp_path: Path) -> None:
    (tmp_path / "report #1.pdf").write_bytes(b"%PDF-1.4\n")

    response = client_for(tmp_path).get("/report%20%231.pdf")

    assert response.status_code == 200
    assert "/__raw__/report%20%231.pdf" in response.text


def test_unsupported_hidden_and_traversal_are_404(tmp_path: Path) -> None:
    (tmp_path / "private.txt").write_text("no", encoding="utf-8")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    client = client_for(tmp_path)

    assert client.get("/private.txt").status_code == 404
    assert client.get("/.env").status_code == 404
    assert client.get("/../LICENSE").status_code == 404


def test_directory_pagination(tmp_path: Path) -> None:
    for index in range(3):
        (tmp_path / f"{index}.html").write_text(str(index), encoding="utf-8")

    first = client_for(tmp_path, page_size=2).get("/")
    second = client_for(tmp_path, page_size=2).get("/?page=2")

    assert "0.html" in first.text
    assert "2.html" not in first.text
    assert "2.html" in second.text
