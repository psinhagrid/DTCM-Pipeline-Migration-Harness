from pathlib import Path


def read_file_tool(path: str) -> dict:
    """
    Read a source file for repair. Returns full content and line count.
    path: absolute path to the file.
    """
    p = Path(path)
    if not p.exists():
        return {"error": f"File not found: {path}"}
    content = p.read_text(encoding="utf-8")
    lines   = content.splitlines()
    return {
        "path":       str(p),
        "filename":   p.name,
        "content":    content,
        "line_count": len(lines),
        "lines":      {i + 1: l for i, l in enumerate(lines)},
    }
