from __future__ import annotations

import os
from typing import List


class FilesystemTool:
    def __init__(self, root_path: str) -> None:
        self.root_path = os.path.abspath(root_path)

    def _resolve(self, rel_path: str) -> str:
        rel_path = rel_path or "."
        candidate = os.path.abspath(os.path.join(self.root_path, rel_path))
        if os.path.commonpath([self.root_path, candidate]) != self.root_path:
            raise ValueError("Access outside of workspace is not permitted.")
        return candidate

    def list_dir(self, rel_path: str = ".") -> List[str]:
        path = self._resolve(rel_path)
        if not os.path.isdir(path):
            raise FileNotFoundError(f"No such directory: {rel_path}")
        return sorted(os.listdir(path))

    def read_file(self, rel_path: str) -> str:
        path = self._resolve(rel_path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"No such file: {rel_path}")
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    def write_file(self, rel_path: str, content: str) -> None:
        path = self._resolve(rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
