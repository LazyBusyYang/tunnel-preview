from pathlib import Path

import pytest

from tunnel_preview.config import load_config
from tunnel_preview.security import (
    NotFoundPath,
    is_hidden,
    resolve_request_path,
    visible_directory_entries,
)


def test_resolve_rejects_path_traversal(tmp_path: Path) -> None:
    config = load_config(root=tmp_path)

    with pytest.raises(NotFoundPath):
        resolve_request_path("../outside.txt", config)


def test_hidden_patterns_match_any_level_and_directories(tmp_path: Path) -> None:
    nested = tmp_path / "a" / ".env"
    nested.parent.mkdir()
    nested.write_text("secret", encoding="utf-8")
    git_dir = tmp_path / "sub" / ".git"
    git_dir.mkdir(parents=True)
    config = load_config(root=tmp_path)

    assert is_hidden(nested, config)
    assert is_hidden(git_dir, config)


def test_visible_entries_filter_unsupported_and_hidden(tmp_path: Path) -> None:
    (tmp_path / "ok.html").write_text("<h1>ok</h1>", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("no", encoding="utf-8")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    (tmp_path / "dir").mkdir()
    config = load_config(root=tmp_path)

    assert [path.name for path in visible_directory_entries(tmp_path, config)] == ["dir", "ok.html"]


def test_symlink_outside_root_is_hidden(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-preview-secret.html"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.html"
    link.symlink_to(outside)
    config = load_config(root=tmp_path)

    assert link.resolve() not in visible_directory_entries(tmp_path, config)
    with pytest.raises(NotFoundPath):
        resolve_request_path("link.html", config)
