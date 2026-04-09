"""Tests for tool security enforcement — path traversal, shell allowlist, web_fetch."""
from __future__ import annotations

import os
import tempfile
import pytest

from ..schemas.tools import FilesystemReadInput, FilesystemWriteInput, FilesystemListInput, ShellInput, WebFetchInput
from ..tools.filesystem import FilesystemTool, _resolve_safe
from ..tools.shell import ShellTool, _get_command_name, _check_compound_command, SHELL_ALLOWLIST, SHELL_ELEVATED_ALLOWLIST
from ..tools.web_fetch import WebFetchTool


class TestFilesystemTool:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        from ..core.config import get_settings
        get_settings().workspace_root = self.tmpdir
        self.tool = FilesystemTool()
        self.tool.settings.workspace_root = self.tmpdir

    def test_read_within_workspace(self):
        path = os.path.join(self.tmpdir, "test.txt")
        with open(path, "w") as f:
            f.write("hello")
        result = self.tool.read(FilesystemReadInput(path="test.txt"))
        assert result.success
        assert result.output == "hello"

    def test_read_path_traversal_denied(self):
        result = self.tool.read(FilesystemReadInput(path="../../../etc/passwd"))
        assert not result.success
        assert "traversal" in (result.error or "").lower() or "denied" in (result.error or "").lower()

    def test_write_within_workspace(self):
        result = self.tool.write(FilesystemWriteInput(path="output.txt", content="world"))
        assert result.success
        with open(os.path.join(self.tmpdir, "output.txt")) as f:
            assert f.read() == "world"

    def test_write_path_traversal_denied(self):
        result = self.tool.write(FilesystemWriteInput(path="../../evil.txt", content="bad"))
        assert not result.success
        assert "traversal" in (result.error or "").lower() or "denied" in (result.error or "").lower()

    def test_absolute_path_outside_workspace_denied(self):
        result = self.tool.read(FilesystemReadInput(path="/etc/passwd"))
        assert not result.success
        assert "traversal" in (result.error or "").lower() or "denied" in (result.error or "").lower()

    def test_sibling_path_attack_denied(self):
        """Ensure ../workspace_evil/ sibling path is rejected (not just prefix match)."""
        sibling = self.tmpdir + "_evil"
        result = self.tool.read(FilesystemReadInput(path=f"../{os.path.basename(sibling)}/secret.txt"))
        assert not result.success
        assert "traversal" in (result.error or "").lower() or "denied" in (result.error or "").lower()

    def test_dry_run_read(self):
        result = self.tool.read(FilesystemReadInput(path="anything.txt", dry_run=True))
        assert result.success
        assert result.dry_run
        assert "DRY RUN" in result.output

    def test_dry_run_write(self):
        result = self.tool.write(FilesystemWriteInput(path="test.txt", content="x", dry_run=True))
        assert result.success
        assert result.dry_run
        assert not os.path.exists(os.path.join(self.tmpdir, "test.txt"))

    def test_list_directory(self):
        os.makedirs(os.path.join(self.tmpdir, "subdir"), exist_ok=True)
        with open(os.path.join(self.tmpdir, "file.txt"), "w") as f:
            f.write("")
        result = self.tool.list_dir(FilesystemListInput(path="."))
        assert result.success
        assert "file.txt" in result.output

    def test_resolve_safe_blocks_traversal(self):
        with pytest.raises(ValueError, match="traversal"):
            _resolve_safe("../../../etc/passwd", self.tmpdir)

    def test_resolve_safe_blocks_sibling(self):
        sibling = self.tmpdir + "_evil"
        with pytest.raises(ValueError, match="traversal"):
            _resolve_safe(f"../{os.path.basename(sibling)}/secret.txt", self.tmpdir)

    def test_resolve_safe_blocks_absolute_outside(self):
        with pytest.raises(ValueError, match="traversal"):
            _resolve_safe("/etc/passwd", self.tmpdir)

    def test_resolve_safe_allows_nested(self):
        path = _resolve_safe("subdir/file.txt", self.tmpdir)
        assert str(path).startswith(self.tmpdir)


class TestShellTool:
    def setup_method(self):
        self.tool = ShellTool()

    def test_allowed_command(self):
        result = self.tool.execute(ShellInput(command="echo test_value"))
        assert result.success
        assert "test_value" in result.output

    def test_denied_command(self):
        result = self.tool.execute(ShellInput(command="rm -rf /tmp/test"))
        assert not result.success
        assert "allowlist" in (result.error or "").lower()

    def test_denied_dangerous_command(self):
        result = self.tool.execute(ShellInput(command="bash -c 'id'"))
        assert not result.success

    def test_command_chaining_semicolon_rejected(self):
        """Ensure echo ok; uname -s does NOT execute uname via metachar detection."""
        result = self.tool.execute(ShellInput(command="echo ok; uname -s"))
        assert not result.success
        assert "metachar" in (result.error or "").lower()

    def test_command_chaining_pipe_rejected(self):
        result = self.tool.execute(ShellInput(command="echo hello | cat"))
        assert not result.success
        assert "metachar" in (result.error or "").lower()

    def test_command_chaining_ampersand_rejected(self):
        result = self.tool.execute(ShellInput(command="echo hello && ls"))
        assert not result.success
        assert "metachar" in (result.error or "").lower()

    def test_subshell_rejected(self):
        result = self.tool.execute(ShellInput(command="echo $(id)"))
        assert not result.success
        assert "metachar" in (result.error or "").lower()

    def test_backtick_rejected(self):
        result = self.tool.execute(ShellInput(command="echo `id`"))
        assert not result.success
        assert "metachar" in (result.error or "").lower()

    def test_dry_run(self):
        result = self.tool.execute(ShellInput(command="echo hello", dry_run=True))
        assert result.success
        assert "DRY RUN" in result.output

    def test_command_name_extraction(self):
        assert _get_command_name("echo hello world") == "echo"
        assert _get_command_name("/usr/bin/ls -la") == "ls"
        assert _get_command_name("python3 script.py") == "python3"

    def test_metachar_detection(self):
        assert _check_compound_command("echo ok; uname") is not None
        assert _check_compound_command("echo ok | cat") is not None
        assert _check_compound_command("echo ok && ls") is not None
        assert _check_compound_command("echo $(id)") is not None
        assert _check_compound_command("echo `id`") is not None
        assert _check_compound_command("echo hello world") is None

    def test_allowlist_contains_expected(self):
        for cmd in ["echo", "ls", "cat", "grep"]:
            assert cmd in SHELL_ALLOWLIST, f"{cmd} should be in standard allowlist"
        for cmd in ["python3", "git", "curl", "wget"]:
            assert cmd in SHELL_ELEVATED_ALLOWLIST, f"{cmd} should be in elevated allowlist"
        for cmd in ["python3", "git", "curl", "wget"]:
            assert cmd not in SHELL_ALLOWLIST, f"{cmd} should NOT be in standard allowlist (elevated only)"


class TestWebFetchTool:
    def setup_method(self):
        self.tool = WebFetchTool()

    def test_invalid_scheme_rejected(self):
        result = self.tool.fetch(WebFetchInput(url="ftp://evil.com/file"))
        assert not result.success
        assert "scheme" in (result.error or "").lower()

    def test_file_scheme_rejected(self):
        result = self.tool.fetch(WebFetchInput(url="file:///etc/passwd"))
        assert not result.success

    def test_dry_run(self):
        result = self.tool.fetch(WebFetchInput(url="https://example.com", dry_run=True))
        assert result.success
        assert result.dry_run
        assert "DRY RUN" in result.output
