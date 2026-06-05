from pathlib import Path

import pytest

from tunnel_preview.config import load_config


def test_default_without_config_keeps_config_port_contract(tmp_path: Path) -> None:
    config = load_config(root=tmp_path)

    assert config.server.host == "127.0.0.1"
    assert config.server.port == 5500
    assert config.server.page_size == 100
    assert not config.port_was_explicit


def test_config_file_replaces_arrays_and_marks_port_explicit(tmp_path: Path) -> None:
    (tmp_path / "tunnel-preview.toml").write_text(
        """
[server]
port = 5501
page_size = 2

[files]
direct = [".html"]
rendered = [".md"]

[hide]
patterns = ["secret/"]
""",
        encoding="utf-8",
    )

    config = load_config(root=tmp_path)

    assert config.server.port == 5501
    assert config.port_was_explicit
    assert config.files.direct == (".html",)
    assert config.files.rendered == (".md",)
    assert config.hide.patterns == ("secret/",)


def test_direct_and_rendered_may_not_overlap(tmp_path: Path) -> None:
    (tmp_path / "tunnel-preview.toml").write_text(
        """
[files]
direct = [".html"]
rendered = [".html"]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="overlap"):
        load_config(root=tmp_path)


def test_hide_negation_is_invalid(tmp_path: Path) -> None:
    (tmp_path / "tunnel-preview.toml").write_text(
        """
[hide]
patterns = ["!public.env"]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="negation"):
        load_config(root=tmp_path)
