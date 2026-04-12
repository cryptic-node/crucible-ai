"""Filesystem tool for Grokenstein.

This tool provides read, write and directory listing operations scoped to
a specific root directory.  All paths are resolved relative to this
directory and attempts to traverse outside of it will raise an error.
This constraint helps enforce the least‑privilege principle and prevent
accidental or malicious modifications to the rest of the filesystem【315594017234579†L69-L82】.
"""

from __future__ import annotations

import os
from typing import List


class FilesystemTool:
    """Perform safe file operations within a configured workspace."""

    def __init__(self, root_path: str) -> None:
        # Store absolute canonical root
        self.root_path = os.path.abspath(root_path)

    def _resolve(self, rel_path: str) -> str:
        """Resolve a relative path to an absolute path within the workspace.

        Args:
            rel_path: a path relative to the workspace root

        Returns:
            The absolute path under the workspace root

        Raises:
            ValueError: if the resolved path escapes the workspace root
        """
        # Default to current directory if no path provided
        rel_path = rel_path or "."
        full_path = os.path.abspath(os.path.join(self.root_path, rel_path))
        # Ensure the resolved path is within the workspace
        if not full_path.startswith(self.root_path):
            raise ValueError("Access outside of workspace is not permitted.")
        return full_path

    def list_dir(self, rel_path: str = ".") -> List[str]:
        """List the contents of a directory relative to the workspace root.

        Args:
            rel_path: directory to list

        Returns:
            A list of file and directory names
        """
        path = self._resolve(rel_path)
        if not os.path.isdir(path):
            raise FileNotFoundError(f"No such directory: {rel_path}")
        return sorted(os.listdir(path))

    def read_file(self, rel_path: str) -> str:
        """Read the contents of a file relative to the workspace root.

        Args:
            rel_path: file to read

        Returns:
            The content of the file as a string
        """
        path = self._resolve(rel_path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"No such file: {rel_path}")
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    def write_file(self, rel_path: str, content: str) -> None:
        """Write content to a file relative to the workspace root.

        The directory structure is created if it does not already exist.

        Args:
            rel_path: path to the file to write
            content: text to write into the file
        """
        path = self._resolve(rel_path)
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)