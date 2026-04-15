from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class SearchHit:
    path: str
    line_no: int
    line: str


def search_workspace(workspace_root: Path, query: str, max_hits: int = 20) -> list[SearchHit]:
    root = workspace_root.resolve()
    hits: list[SearchHit] = []
    query_lower = query.lower()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.stat().st_size > 512_000:
            continue
        rel = str(path.relative_to(root))
        if query_lower in rel.lower():
            hits.append(SearchHit(path=rel, line_no=0, line="<filename match>"))
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, start=1):
            if query_lower in line.lower():
                hits.append(SearchHit(path=rel, line_no=idx, line=line.strip()))
                if len(hits) >= max_hits:
                    return hits
        if len(hits) >= max_hits:
            break
    return hits[:max_hits]
