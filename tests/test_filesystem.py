from __future__ import annotations

import pytest

from grokenstein.tools.filesystem import FilesystemTool


def test_filesystem_blocks_path_escape(tmp_path):
    tool = FilesystemTool(str(tmp_path / "workspace"))
    (tmp_path / "workspace").mkdir()

    with pytest.raises(ValueError):
        tool.read_file("../secret.txt")
